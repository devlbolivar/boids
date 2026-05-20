import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mock_claude_copywriter(
    subject="Email subject personalizado",
    body="Hola Carlos, vi que SaaS Chile levantó $2M...",
    notes="Usé señal de funding",
) -> MagicMock:
    mock = MagicMock()
    mock.content = [
        MagicMock(
            type="tool_use",
            input={"subject": subject, "body": body, "personalization_notes": notes},
        )
    ]
    return mock


def mock_claude_qa(
    personalization=0.85,
    spam_risk=0.05,
    tone_match=0.90,
    cta_clarity=0.90,
    issues=None,
) -> MagicMock:
    mock = MagicMock()
    mock.content = [
        MagicMock(
            type="tool_use",
            input={
                "personalization": personalization,
                "spam_risk": spam_risk,
                "tone_match": tone_match,
                "cta_clarity": cta_clarity,
                "issues": issues or [],
            },
        )
    ]
    return mock


def make_rls_factory(session_factory, tenant_id: str):
    """Creates an RLS-aware session factory that mimics what _override_get_tenant_db does."""
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


async def _put_lead_in_researched(session_factory, tenant_id, lead_id):
    """Helper: update a lead's status to 'researched' with some context."""
    async with session_factory() as db:
        await db.execute(text("SET LOCAL ROLE boids_app"))
        await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        from app.leads.service import LeadService
        svc = LeadService()
        await svc.update_research(
            db,
            lead_id=lead_id,
            research_ctx={
                "summary": "Empresa en crecimiento, levantaron $2M en enero",
                "signals": [
                    {
                        "type": "funding",
                        "description": "$2M enero 2025",
                        "relevance": "Tienen presupuesto",
                        "date": "2025-01",
                    }
                ],
            },
            status="researched",
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_pipeline_lead_becomes_emailed(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    """Test end-to-end: lead researched → email draft en DB."""
    _, session_factory = test_engine

    r = await client.post("/campaigns", json={"name": "Copywrite E2E"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    r = await client.post(
        f"/campaigns/{campaign_id}/leads",
        json={"email": "cto@saas.cl", "full_name": "Carlos", "company": "SaaS"},
        headers=auth_headers,
    )
    lead_id = r.json()["id"]

    # Simular que ya fue investigado
    await _put_lead_in_researched(session_factory, tenant_id, lead_id)

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Primero llama Copywriter (Sonnet), luego QA (Haiku)
        if call_count % 2 == 1:
            return mock_claude_copywriter()
        else:
            return mock_claude_qa()

    rls_factory = make_rls_factory(session_factory, tenant_id)

    from app.agents.copywriter.schemas import EmailDraft, QAScore

    good_draft = EmailDraft(
        subject="Vi que levantaron $2M — así podemos ayudar",
        body="Hola Carlos, vi el funding reciente de SaaS Chile...",
        personalization_notes="Usé la señal de funding de enero 2025",
    )
    good_score = QAScore(
        personalization=0.85,
        spam_risk=0.05,
        tone_match=0.90,
        cta_clarity=0.90,
        total=QAScore.compute_total(0.85, 0.05, 0.90, 0.90),
        issues=[],
        approved=True,
    )

    with patch("app.workers.tasks.copywriter.AsyncSessionLocal", rls_factory), \
         patch(
             "app.agents.copywriter.pipeline.CopywriterAgent"
         ) as mock_cw, \
         patch(
             "app.agents.copywriter.pipeline.QAAgent"
         ) as mock_qa, \
         patch(
             "app.agents.copywriter.pipeline.build_rag_context",
             new_callable=AsyncMock,
             return_value="",
         ):

        mock_cw.return_value.run = AsyncMock(return_value=good_draft)
        mock_qa.return_value.evaluate = AsyncMock(return_value=good_score)

        from app.workers.tasks.copywriter import _copywrite_lead_async
        result = await _copywrite_lead_async(lead_id, tenant_id, _session_factory=rls_factory)

    assert result["status"] == "ok"
    assert "email_id" in result
    assert result["quality_score"] >= 0.70

    # Lead debe estar en status "emailed"
    r = await client.get(f"/campaigns/{campaign_id}/leads", headers=auth_headers)
    lead = r.json()[0]
    assert lead["status"] == "emailed"


@pytest.mark.asyncio
async def test_pipeline_endpoint_rejects_non_researched_campaign(
    client: AsyncClient,
    auth_headers,
):
    r = await client.post("/campaigns", json={"name": "No Research"}, headers=auth_headers)
    campaign_id = r.json()["id"]

    r = await client.post(
        f"/campaigns/{campaign_id}/run/copywrite",
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_failed_qa_marks_lead_needs_review(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    _, session_factory = test_engine

    r = await client.post("/campaigns", json={"name": "QA Fail Test"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    r = await client.post(
        f"/campaigns/{campaign_id}/leads",
        json={"email": "fail@test.cl", "company": "Bad Corp"},
        headers=auth_headers,
    )
    lead_id = r.json()["id"]

    # Poner lead en researched
    await _put_lead_in_researched(session_factory, tenant_id, lead_id)

    rls_factory = make_rls_factory(session_factory, tenant_id)

    from app.agents.copywriter.schemas import EmailDraft, QAScore

    bad_draft = EmailDraft(
        subject="Oferta gratis garantizada",
        body="Estimado cliente, espero que esté bien...",
        personalization_notes="Sin personalización",
    )
    bad_score = QAScore(
        personalization=0.1,
        spam_risk=0.9,
        tone_match=0.2,
        cta_clarity=0.1,
        total=QAScore.compute_total(0.1, 0.9, 0.2, 0.1),
        issues=["Todo está mal"],
        approved=False,
    )

    with patch("app.workers.tasks.copywriter.AsyncSessionLocal", rls_factory), \
         patch(
             "app.agents.copywriter.pipeline.CopywriterAgent"
         ) as mock_cw, \
         patch(
             "app.agents.copywriter.pipeline.QAAgent"
         ) as mock_qa, \
         patch(
             "app.agents.copywriter.pipeline.build_rag_context",
             new_callable=AsyncMock,
             return_value="",
         ):

        mock_cw.return_value.run = AsyncMock(return_value=bad_draft)
        # QA siempre falla con score muy bajo (< RETRY_THRESHOLD 0.50)
        mock_qa.return_value.evaluate = AsyncMock(return_value=bad_score)

        from app.workers.tasks.copywriter import _copywrite_lead_async
        result = await _copywrite_lead_async(lead_id, tenant_id, _session_factory=rls_factory)

    assert result["status"] == "needs_review"

    r = await client.get(f"/campaigns/{campaign_id}/leads", headers=auth_headers)
    assert r.json()[0]["status"] == "needs_review"


@pytest.mark.asyncio
async def test_copywrite_endpoint_returns_202(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    """Endpoint returns 202 with leads_queued when there are researched leads."""
    _, session_factory = test_engine

    r = await client.post("/campaigns", json={"name": "Endpoint Test"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    r = await client.post(
        f"/campaigns/{campaign_id}/leads",
        json={"email": "endpoint@test.cl", "company": "Endpoint Corp"},
        headers=auth_headers,
    )
    lead_id = r.json()["id"]

    await _put_lead_in_researched(session_factory, tenant_id, lead_id)

    with patch("app.campaigns.router.copywrite_campaign_leads") as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-cw-123")

        r = await client.post(
            f"/campaigns/{campaign_id}/run/copywrite",
            headers=auth_headers,
        )

    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "queued"
    assert data["leads_queued"] == 1
    assert "task_id" in data
    mock_task.delay.assert_called_once()
