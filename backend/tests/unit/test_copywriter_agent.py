import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.agents.copywriter.agent import CopywriterAgent
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
        "signals": [
            {
                "type": "funding",
                "description": "$2M enero 2025",
                "relevance": "Tienen presupuesto",
                "date": "2025-01",
            }
        ],
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
async def test_copywriter_calls_claude_with_cached_system_prompt():
    lead = make_lead()
    tenant = make_tenant()

    with patch("app.agents.copywriter.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="tool_use",
                input={
                    "subject": "Vi que levantaron $2M — así podemos ayudar",
                    "body": "Hola Carlos, vi el funding reciente de SaaS Chile...",
                    "personalization_notes": "Usé la señal de funding de enero 2025",
                },
            )
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = CopywriterAgent()
        draft = await agent.run(lead, tenant, rag_context="", previous_issues=None)

    # Verificar que se usó cache_control en el system prompt
    call_kwargs = mock_claude.return_value.messages.create.call_args.kwargs
    system = call_kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}

    assert draft.subject == "Vi que levantaron $2M — así podemos ayudar"


@pytest.mark.asyncio
async def test_copywriter_includes_previous_issues_in_retry():
    lead = make_lead()
    tenant = make_tenant()
    issues = ["Primera línea muy genérica", "Falta CTA claro"]

    with patch("app.agents.copywriter.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="tool_use",
                input={
                    "subject": "Retry subject",
                    "body": "Retry body",
                    "personalization_notes": "Corregí los issues",
                },
            )
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = CopywriterAgent()
        await agent.run(lead, tenant, "", previous_issues=issues)

    # Verificar que los issues aparecen en el user message
    call_kwargs = mock_claude.return_value.messages.create.call_args.kwargs
    user_content = call_kwargs["messages"][0]["content"]
    assert "Primera línea muy genérica" in user_content
    assert "Falta CTA claro" in user_content
