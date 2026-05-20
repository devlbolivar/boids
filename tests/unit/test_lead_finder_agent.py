import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.lead_finder.agent import LeadFinderAgent
from app.campaigns.schemas import ICPConfig


@pytest.fixture
def mock_apollo():
    apollo = AsyncMock()
    apollo.search_people = AsyncMock(return_value={
        "people": [
            {
                "id": "ap1",
                "name": "Ana Torres",
                "email": "ana@saas.cl",
                "title": "CTO",
                "organization": {"name": "SaaS Chile"},
            },
            {
                "id": "ap2",
                "email": "email_not_unlocked@domain.com",
                "name": "Unknown",
            },
        ]
    })
    return apollo


async def test_agent_calls_apollo_with_filters(mock_apollo):
    icp = ICPConfig(titles=["CTO"], locations=["Chile"])

    with patch("app.agents.lead_finder.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="tool_use",
                input={
                    "person_titles": ["CTO"],
                    "person_locations": ["Chile"],
                    "per_page": 25,
                },
            )
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = LeadFinderAgent(mock_apollo)
        contacts = await agent.run(icp, max_leads=25)

    mock_apollo.search_people.assert_awaited_once()
    call_kwargs = mock_apollo.search_people.call_args.kwargs
    assert call_kwargs["filters"]["person_titles"] == ["CTO"]
    assert call_kwargs["filters"]["person_locations"] == ["Chile"]
    assert len(contacts) == 2


async def test_agent_passes_max_leads_as_per_page(mock_apollo):
    icp = ICPConfig(titles=["CEO"])

    with patch("app.agents.lead_finder.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="tool_use", input={})]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = LeadFinderAgent(mock_apollo)
        await agent.run(icp, max_leads=10)

    call_kwargs = mock_apollo.search_people.call_args.kwargs
    assert call_kwargs["per_page"] == 10


async def test_agent_caps_per_page_at_25(mock_apollo):
    icp = ICPConfig(titles=["CEO"])

    with patch("app.agents.lead_finder.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="tool_use", input={})]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = LeadFinderAgent(mock_apollo)
        await agent.run(icp, max_leads=100)

    call_kwargs = mock_apollo.search_people.call_args.kwargs
    assert call_kwargs["per_page"] == 25


async def test_agent_uses_haiku_model(mock_apollo):
    icp = ICPConfig(titles=["CTO"])

    with patch("app.agents.lead_finder.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="tool_use", input={})]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = LeadFinderAgent(mock_apollo)
        await agent.run(icp)

    call_kwargs = mock_claude.return_value.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


async def test_agent_returns_people_list(mock_apollo):
    icp = ICPConfig()

    with patch("app.agents.lead_finder.agent.anthropic.Anthropic") as mock_claude:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="tool_use", input={})]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = LeadFinderAgent(mock_apollo)
        contacts = await agent.run(icp)

    assert isinstance(contacts, list)
    assert len(contacts) == 2
