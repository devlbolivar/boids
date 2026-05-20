import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy import text

VALUE_PROP_CONTENT = """
Boids AI ayuda a empresas SaaS y fintech a escalar sus ventas
con prospeccion autonoma. Nuestro enjambre de agentes analiza
el mercado, identifica señales de compra, y genera outreach
altamente personalizado.

Casos de exito: Fintual redujo su ciclo de ventas en 40%.
Kushki triplico su pipeline en 3 meses.
Betterfly consiguio 150 reuniones calificadas en su primer mes.

Nuestra propuesta de valor es simple: el equipo de ventas
solo aparece en el cierre — el resto lo hacemos nosotros.
"""


def make_rls_factory(session_factory, tenant_id: str):
    class _RLSCtx:
        def __init__(self):
            self._s = session_factory()

        async def __aenter__(self):
            s = await self._s.__aenter__()
            await s.execute(text("SET LOCAL ROLE boids_app"))
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
            return s

        async def __aexit__(self, *args):
            return await self._s.__aexit__(*args)

    class RLSSessionFactory:
        def __call__(self):
            return _RLSCtx()

    return RLSSessionFactory()


@pytest.mark.asyncio
async def test_upload_document_creates_pending_record(
    client: AsyncClient,
    auth_headers,
):
    with patch("app.workers.tasks.knowledge.index_document.delay"):
        r = await client.post(
            "/knowledge/documents",
            json={
                "title": "Propuesta de Valor",
                "doc_type": "value_prop",
                "content": VALUE_PROP_CONTENT,
            },
            headers=auth_headers,
        )

    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Propuesta de Valor"
    assert data["status"] == "pending"
    assert data["chunk_count"] == 0


@pytest.mark.asyncio
async def test_indexing_pipeline_updates_status(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    _, session_factory = test_engine

    with patch("app.workers.tasks.knowledge.index_document.delay"):
        r = await client.post(
            "/knowledge/documents",
            json={
                "title": "Value Prop Test",
                "doc_type": "value_prop",
                "content": VALUE_PROP_CONTENT,
            },
            headers=auth_headers,
        )

    doc_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    rls_factory = make_rls_factory(session_factory, tenant_id)

    with patch("app.workers.tasks.knowledge.AsyncSessionLocal", rls_factory), \
         patch(
             "app.integrations.embeddings.client.EmbeddingClient.embed_batch",
             new_callable=AsyncMock,
             return_value=[[0.1] * 1536, [0.2] * 1536],
         ), \
         patch(
             "app.integrations.qdrant.client.QdrantKnowledgeClient.ensure_collection",
             new_callable=AsyncMock,
         ), \
         patch(
             "app.integrations.qdrant.client.QdrantKnowledgeClient.upsert_chunks",
             new_callable=AsyncMock,
             return_value=2,
         ):
        from app.workers.tasks.knowledge import _index_document_async
        result = await _index_document_async(doc_id, tenant_id)

    assert result["status"] == "ok"
    assert result["chunks"] == 2

    r = await client.get("/knowledge/documents", headers=auth_headers)
    doc = next(d for d in r.json() if d["id"] == doc_id)
    assert doc["status"] == "indexed"
    assert doc["chunk_count"] == 2


@pytest.mark.asyncio
async def test_delete_document_removes_from_db_and_qdrant(
    client: AsyncClient,
    auth_headers,
):
    with patch("app.workers.tasks.knowledge.index_document.delay"):
        r = await client.post(
            "/knowledge/documents",
            json={
                "title": "To Delete",
                "doc_type": "other",
                "content": "x " * 30,
            },
            headers=auth_headers,
        )
    doc_id = r.json()["id"]

    with patch(
        "app.integrations.qdrant.client.QdrantKnowledgeClient.delete_document_chunks",
        new_callable=AsyncMock,
    ):
        r = await client.delete(f"/knowledge/documents/{doc_id}", headers=auth_headers)

    assert r.status_code == 204

    r = await client.get("/knowledge/documents", headers=auth_headers)
    ids = [d["id"] for d in r.json()]
    assert doc_id not in ids


@pytest.mark.asyncio
async def test_tenant_isolation_in_search(
    client: AsyncClient,
    auth_headers,
    second_auth_headers,
):
    tenant_a_id = (await client.get("/tenants/me", headers=auth_headers)).json()["id"]
    tenant_b_id = (await client.get("/tenants/me", headers=second_auth_headers)).json()["id"]

    from app.integrations.qdrant.client import QdrantKnowledgeClient
    q = QdrantKnowledgeClient.__new__(QdrantKnowledgeClient)
    assert q._collection_name(tenant_a_id) != q._collection_name(tenant_b_id)


@pytest.mark.asyncio
async def test_content_too_short_returns_422(
    client: AsyncClient,
    auth_headers,
):
    r = await client.post(
        "/knowledge/documents",
        json={
            "title": "Short",
            "doc_type": "other",
            "content": "Muy corto",
        },
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_endpoint_returns_chunks(
    client: AsyncClient,
    auth_headers,
):
    mock_chunks = [
        {
            "text": "Resultado relevante",
            "doc_type": "value_prop",
            "doc_id": "abc",
            "title": "VP",
            "score": 0.85,
        }
    ]

    with patch(
        "app.knowledge.service.KnowledgeService.retrieve_context",
        new_callable=AsyncMock,
        return_value=mock_chunks,
    ):
        r = await client.get(
            "/knowledge/search?query=CTO+SaaS",
            headers=auth_headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["query"] == "CTO SaaS"
    assert len(data["chunks"]) == 1
    assert data["chunks"][0]["score"] == 0.85
