import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.leads.models import Lead
from app.tenants.models import Tenant


def make_lead() -> Lead:
    lead = Lead()
    lead.id = str(uuid.uuid4())
    lead.tenant_id = str(uuid.uuid4())
    lead.full_name = "Carlos Vega"
    lead.title = "CTO"
    lead.company = "SaaS Chile"
    lead.email = "carlos@saas.cl"
    lead.status = "researched"
    lead.research_ctx = {
        "summary": "Empresa en crecimiento, levantaron $2M en enero",
        "signals": [],
    }
    return lead


def make_tenant() -> Tenant:
    tenant = Tenant()
    tenant.id = str(uuid.uuid4())
    tenant.name = "Boids Demo"
    tenant.icp_config = {
        "voice_guidelines": "Profesional pero cercano",
        "value_proposition": "Prospección B2B autónoma",
    }
    return tenant


@pytest.mark.asyncio
async def test_pipeline_approves_on_first_attempt():
    from app.agents.copywriter.pipeline import run_copywriter_pipeline

    lead = make_lead()
    tenant = make_tenant()

    good_draft = MagicMock()
    good_score = MagicMock()
    good_score.approved = True
    good_score.total = 0.87
    good_score.issues = []

    with patch("app.agents.copywriter.pipeline.CopywriterAgent") as mock_cw, \
         patch("app.agents.copywriter.pipeline.QAAgent") as mock_qa, \
         patch(
             "app.agents.copywriter.pipeline.build_rag_context",
             new_callable=AsyncMock,
             return_value="contexto rag",
         ):

        mock_cw.return_value.run = AsyncMock(return_value=good_draft)
        mock_qa.return_value.evaluate = AsyncMock(return_value=good_score)

        draft, score = await run_copywriter_pipeline(lead, tenant)

    assert draft == good_draft
    assert score.approved is True
    assert mock_cw.return_value.run.await_count == 1  # solo 1 intento


@pytest.mark.asyncio
async def test_pipeline_retries_with_qa_feedback():
    from app.agents.copywriter.pipeline import run_copywriter_pipeline

    lead = make_lead()
    tenant = make_tenant()

    fail_score = MagicMock()
    fail_score.approved = False
    fail_score.total = 0.60  # entre retry y approval threshold
    fail_score.issues = ["Primera línea genérica"]

    good_score = MagicMock()
    good_score.approved = True
    good_score.total = 0.82
    good_score.issues = []

    draft = MagicMock()

    with patch("app.agents.copywriter.pipeline.CopywriterAgent") as mock_cw, \
         patch("app.agents.copywriter.pipeline.QAAgent") as mock_qa, \
         patch(
             "app.agents.copywriter.pipeline.build_rag_context",
             new_callable=AsyncMock,
             return_value="",
         ):

        mock_cw.return_value.run = AsyncMock(return_value=draft)
        # Primer intento falla, segundo aprueba
        mock_qa.return_value.evaluate = AsyncMock(
            side_effect=[fail_score, good_score]
        )

        result_draft, result_score = await run_copywriter_pipeline(lead, tenant)

    assert result_score.approved is True
    assert mock_cw.return_value.run.await_count == 2  # 2 intentos

    # Verificar que el segundo intento recibió los issues como feedback
    second_call_kwargs = mock_cw.return_value.run.call_args_list[1][1]
    assert second_call_kwargs["previous_issues"] == ["Primera línea genérica"]


@pytest.mark.asyncio
async def test_pipeline_escalates_when_below_retry_threshold():
    from app.agents.copywriter.pipeline import run_copywriter_pipeline

    lead = make_lead()
    tenant = make_tenant()

    terrible_score = MagicMock()
    terrible_score.approved = False
    terrible_score.total = 0.35  # por debajo del retry threshold
    terrible_score.issues = ["Todo está mal"]

    with patch("app.agents.copywriter.pipeline.CopywriterAgent") as mock_cw, \
         patch("app.agents.copywriter.pipeline.QAAgent") as mock_qa, \
         patch(
             "app.agents.copywriter.pipeline.build_rag_context",
             new_callable=AsyncMock,
             return_value="",
         ):

        mock_cw.return_value.run = AsyncMock(return_value=MagicMock())
        mock_qa.return_value.evaluate = AsyncMock(return_value=terrible_score)

        result_draft, result_score = await run_copywriter_pipeline(lead, tenant)

    assert result_draft is None  # no hay draft aprobado
    assert result_score.total == 0.35
    assert mock_cw.return_value.run.await_count == 1  # no reintenta si < retry_threshold
