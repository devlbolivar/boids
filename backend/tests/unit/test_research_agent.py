import pytest
import uuid
from unittest.mock import MagicMock, patch
from app.agents.research.agent import ResearchAgent
from app.leads.models import Lead


def make_tool_block(block_type: str, name: str, input_data: dict) -> MagicMock:
    block = MagicMock()
    block.type = block_type
    block.name = name
    block.input = input_data
    return block


def make_lead(**kwargs) -> Lead:
    defaults = {
        "id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "campaign_id": str(uuid.uuid4()),
        "email": "cto@startup.cl",
        "full_name": "Carlos Vega",
        "company": "Startup Chile",
        "title": "CTO",
        "status": "new",
        "research_ctx": {},
    }
    defaults.update(kwargs)
    lead = Lead()
    for k, v in defaults.items():
        setattr(lead, k, v)
    return lead


@pytest.mark.asyncio
async def test_agent_returns_limited_data_when_no_save_block():
    lead = make_lead()

    with patch("app.agents.research.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="No encontré información relevante.")
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = ResearchAgent()
        ctx = await agent.run(lead)

    assert ctx.limited_data is True
    assert ctx.data_quality == "low"
    assert ctx.summary != ""


@pytest.mark.asyncio
async def test_agent_extracts_save_research_block():
    lead = make_lead()

    save_input = {
        "summary": "Startup en crecimiento con funding reciente",
        "signals": [
            {
                "type": "funding",
                "description": "Levantaron $3M en enero 2025",
                "relevance": "Tienen presupuesto para nuevas herramientas",
                "date": "2025-01",
            }
        ],
        "pain_points": ["Escalar infraestructura rápidamente"],
        "company_context": {
            "website": "https://startup.cl",
            "description": "Plataforma SaaS de gestión",
        },
        "data_quality": "high",
        "limited_data": False,
    }

    with patch("app.agents.research.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [
            make_tool_block("tool_use", "web_search", {"query": "Startup Chile funding"}),
            make_tool_block("tool_use", "save_research", save_input),
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = ResearchAgent()
        ctx = await agent.run(lead)

    assert ctx.data_quality == "high"
    assert len(ctx.signals) == 1
    assert ctx.signals[0].type == "funding"
    assert ctx.limited_data is False


@pytest.mark.asyncio
async def test_agent_uses_last_save_block_when_multiple():
    lead = make_lead()

    first_save = {
        "summary": "Primera versión",
        "signals": [],
        "pain_points": [],
        "company_context": {},
        "data_quality": "low",
        "limited_data": True,
    }
    final_save = {
        "summary": "Versión final con más contexto",
        "signals": [
            {"type": "news", "description": "Noticia reciente",
             "relevance": "Relevante", "date": "2025-04"}
        ],
        "pain_points": ["Escalar ventas"],
        "company_context": {"description": "Empresa de IA"},
        "data_quality": "medium",
        "limited_data": False,
    }

    with patch("app.agents.research.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [
            make_tool_block("tool_use", "save_research", first_save),
            make_tool_block("tool_use", "web_search", {"query": "más búsqueda"}),
            make_tool_block("tool_use", "save_research", final_save),
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = ResearchAgent()
        ctx = await agent.run(lead)

    assert ctx.summary == "Versión final con más contexto"
    assert ctx.data_quality == "medium"
