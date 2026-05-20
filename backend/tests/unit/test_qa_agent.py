import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.agents.copywriter.schemas import EmailDraft, QAScore
from app.agents.qa.agent import QAAgent
from app.tenants.models import Tenant


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
async def test_qa_agent_computes_total_from_tool_output():
    draft = EmailDraft(
        subject="Test subject",
        body="Test body con CTA claro",
        personalization_notes="Usé señal de funding",
    )
    tenant = make_tenant()

    with patch("app.agents.qa.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="tool_use",
                input={
                    "personalization": 0.85,
                    "spam_risk": 0.05,
                    "tone_match": 0.90,
                    "cta_clarity": 0.95,
                    "issues": [],
                },
            )
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        qa = QAAgent()
        score = await qa.evaluate(draft, tenant)

    expected_total = QAScore.compute_total(0.85, 0.05, 0.90, 0.95)
    assert score.total == expected_total
    assert score.approved is True


@pytest.mark.asyncio
async def test_qa_agent_marks_not_approved_when_below_threshold():
    draft = EmailDraft(
        subject="Gratis gratis GARANTIZADO!!!",
        body="Estimado cliente, espero que esté bien...",
        personalization_notes="Sin personalización",
    )
    tenant = make_tenant()

    with patch("app.agents.qa.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="tool_use",
                input={
                    "personalization": 0.10,
                    "spam_risk": 0.90,
                    "tone_match": 0.20,
                    "cta_clarity": 0.15,
                    "issues": ["Email genérico", "Alto riesgo de spam"],
                },
            )
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        qa = QAAgent()
        score = await qa.evaluate(draft, tenant)

    assert score.approved is False
    assert score.total < 0.70
    assert len(score.issues) > 0
