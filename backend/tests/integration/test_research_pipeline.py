import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient
from sqlalchemy import text

MOCK_RESEARCH_RESPONSE = {
    "summary": "Startup de SaaS con funding reciente — están escalando su equipo técnico",
    "signals": [
        {
            "type": "hiring",
            "description": "Publicaron 3 posiciones de ingeniería en enero 2025",
            "relevance": "Crecimiento activo del equipo técnico",
            "date": "2025-01",
        },
        {
            "type": "funding",
            "description": "Serie A de $2M cerrada en diciembre 2024",
            "relevance": "Tienen presupuesto disponible para herramientas",
            "date": "2024-12",
        },
    ],
    "pain_points": [
        "Escalar infraestructura rápidamente con equipo pequeño",
        "Coordinación de ventas con crecimiento acelerado",
    ],
    "company_context": {
        "website": "https://saas-startup.cl",
        "founded": "2022",
        "size_estimate": "20-50 employees",
        "recent_news": "Levantaron Serie A, expandiendo a Colombia",
        "description": "Plataforma SaaS de gestión de proyectos para PYMEs",
    },
    "data_quality": "high",
    "limited_data": False,
}


def make_mock_claude_response(save_input: dict) -> MagicMock:
    def _block(block_type, name, input_data):
        b = MagicMock()
        b.type = block_type
        b.name = name
        b.input = input_data
        return b

    mock_response = MagicMock()
    mock_response.content = [
        _block("tool_use", "web_search", {"query": "Startup Chile CTO funding 2025"}),
        _block("tool_use", "save_research", save_input),
    ]
    return mock_response


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
async def test_research_endpoint_dispatches_task(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={"name": "Research Test"}, headers=auth_headers)
    campaign_id = r.json()["id"]

    await client.post(
        f"/campaigns/{campaign_id}/leads",
        json={"email": "cto@startup.cl", "company": "Startup", "title": "CTO"},
        headers=auth_headers,
    )

    with patch("app.campaigns.router.research_campaign_leads") as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-research-123")

        r = await client.post(
            f"/campaigns/{campaign_id}/run/research",
            headers=auth_headers,
        )

    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "queued"
    assert data["leads_queued"] == 1
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_research_endpoint_rejects_empty_campaign(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={"name": "Empty Campaign"}, headers=auth_headers)
    campaign_id = r.json()["id"]

    r = await client.post(
        f"/campaigns/{campaign_id}/run/research",
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "new" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_research_endpoint_404_unknown_campaign(client: AsyncClient, auth_headers):
    import uuid
    fake_id = str(uuid.uuid4())
    r = await client.post(f"/campaigns/{fake_id}/run/research", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_research_pipeline_end_to_end(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    _, session_factory = test_engine

    r = await client.post("/campaigns", json={"name": "E2E Research"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    r = await client.post(
        f"/campaigns/{campaign_id}/leads",
        json={
            "email": "cto@saas.cl",
            "full_name": "Ana Torres",
            "company": "SaaS Chile",
            "title": "CTO",
        },
        headers=auth_headers,
    )
    lead_id = r.json()["id"]

    rls_factory = make_rls_factory(session_factory, tenant_id)

    with patch("app.workers.tasks.research.AsyncSessionLocal", rls_factory), \
         patch("app.agents.research.agent.anthropic.Anthropic") as mock_claude:

        mock_claude.return_value.messages.create.return_value = \
            make_mock_claude_response(MOCK_RESEARCH_RESPONSE)

        from app.workers.tasks.research import _research_lead_async
        result = await _research_lead_async(lead_id, tenant_id)

    assert result["status"] == "ok"
    assert result["data_quality"] == "high"
    assert result["signals_found"] == 2

    r = await client.get(f"/campaigns/{campaign_id}/leads", headers=auth_headers)
    leads = r.json()
    assert len(leads) == 1
    lead = leads[0]
    assert lead["status"] == "researched"
    assert lead["research_ctx"]["data_quality"] == "high"
    assert len(lead["research_ctx"]["signals"]) == 2
    assert lead["research_ctx"]["signals"][0]["type"] == "hiring"


@pytest.mark.asyncio
async def test_failed_research_marks_lead_as_needs_review(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    _, session_factory = test_engine

    r = await client.post("/campaigns", json={"name": "Failure Test"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    r = await client.post(
        f"/campaigns/{campaign_id}/leads",
        json={"email": "fail@test.cl", "company": "Fail Corp"},
        headers=auth_headers,
    )
    lead_id = r.json()["id"]

    rls_factory = make_rls_factory(session_factory, tenant_id)

    with patch("app.workers.tasks.research.AsyncSessionLocal", rls_factory), \
         patch("app.agents.research.agent.anthropic.Anthropic") as mock_claude:

        mock_claude.return_value.messages.create.side_effect = Exception("API error")

        from app.workers.tasks.research import _research_lead_async
        try:
            await _research_lead_async(lead_id, tenant_id)
        except Exception:
            pass

    r = await client.get(f"/campaigns/{campaign_id}/leads", headers=auth_headers)
    lead = r.json()[0]
    assert lead["status"] == "needs_review"


@pytest.mark.asyncio
async def test_parallel_research_isolates_failures(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    _, session_factory = test_engine

    r = await client.post("/campaigns", json={"name": "Parallel Test"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    lead_ids = []
    for i in range(3):
        r = await client.post(
            f"/campaigns/{campaign_id}/leads",
            json={"email": f"lead{i}@test.cl", "company": f"Corp {i}"},
            headers=auth_headers,
        )
        lead_ids.append(r.json()["id"])

    call_count = 0
    rls_factory = make_rls_factory(session_factory, tenant_id)

    def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("Simulated API failure")
        return make_mock_claude_response(MOCK_RESEARCH_RESPONSE)

    with patch("app.workers.tasks.research.AsyncSessionLocal", rls_factory), \
         patch("app.agents.research.agent.anthropic.Anthropic") as mock_claude:

        mock_claude.return_value.messages.create.side_effect = mock_create

        from app.workers.tasks.research import _research_lead_async
        results = []
        for lead_id in lead_ids:
            try:
                r = await _research_lead_async(lead_id, tenant_id)
                results.append(r)
            except Exception:
                results.append({"status": "error"})

    successful = [r for r in results if r.get("status") == "ok"]
    failed = [r for r in results if r.get("status") == "error"]

    assert len(successful) == 2
    assert len(failed) == 1
