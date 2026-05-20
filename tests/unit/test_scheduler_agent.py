import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.scheduler.agent import SchedulerAgent
from app.leads.models import Lead
from app.tenants.models import Tenant


def make_lead():
    lead = Lead()
    lead.id = str(uuid.uuid4())
    lead.tenant_id = str(uuid.uuid4())
    lead.email = "cto@startup.cl"
    lead.full_name = "Carlos Vega"
    lead.company = "Startup Chile"
    lead.status = "sent"
    return lead


def make_tenant(with_calendar: bool = True):
    tenant = Tenant()
    tenant.id = str(uuid.uuid4())
    tenant.name = "Boids Demo"
    if with_calendar:
        tenant.api_keys_enc = {
            "google_calendar": {
                "access_token": "mock_token",
                "refresh_token": "mock_refresh",
            }
        }
    else:
        tenant.api_keys_enc = {}
    return tenant


@pytest.mark.asyncio
async def test_scheduler_ignores_auto_reply():
    agent = SchedulerAgent()

    with patch.object(
        agent.classifier,
        "classify",
        new_callable=AsyncMock,
        return_value={"intent": "auto_reply", "confidence": 0.99, "key_phrase": ""},
    ):
        result = await agent.process_reply(
            "Estoy de vacaciones hasta junio.", make_lead(), make_tenant()
        )

    assert result["action"] == "ignored"
    assert result["intent"] == "auto_reply"


@pytest.mark.asyncio
async def test_scheduler_marks_negative_as_rejected():
    agent = SchedulerAgent()

    with (
        patch.object(
            agent.classifier,
            "classify",
            new_callable=AsyncMock,
            return_value={"intent": "negative", "confidence": 0.95, "key_phrase": "no"},
        ),
        patch.object(
            agent,
            "_generate_decline_response",
            new_callable=AsyncMock,
            return_value="Gracias por tu respuesta, entendemos tu posición.",
        ),
    ):
        result = await agent.process_reply("No gracias.", make_lead(), make_tenant())

    assert result["action"] == "rejected"
    assert result["message"] != ""


@pytest.mark.asyncio
async def test_scheduler_books_meeting_on_positive_intent():
    lead = make_lead()
    tenant = make_tenant()

    mock_slots = [
        {
            "start": "2025-06-02T10:00:00+00:00",
            "end": "2025-06-02T10:30:00+00:00",
            "label": "Monday 02 Jun, 10:00",
        }
    ]
    mock_event = {
        "event_id": "gcal_event_123",
        "meet_link": "https://meet.google.com/abc-def-ghi",
        "start": "2025-06-02T10:00:00+00:00",
        "html_link": "https://calendar.google.com/...",
    }

    with (
        patch("app.integrations.google.calendar.GoogleCalendarClient") as mock_cal_class,
        patch("app.agents.scheduler.agent.anthropic.Anthropic") as mock_claude,
    ):
        # Calendar mock
        mock_cal = MagicMock()
        mock_cal.get_available_slots.return_value = mock_slots
        mock_cal.create_event.return_value = mock_event
        mock_cal_class.return_value = mock_cal

        # Claude mock para book_meeting
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="tool_use",
                input={
                    "selected_slot_start": mock_slots[0]["start"],
                    "selected_slot_end": mock_slots[0]["end"],
                    "confirmation_message": "Perfecto Carlos, quedamos el lunes 2 de junio a las 10am.",
                },
            )
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = SchedulerAgent()
        with patch.object(
            agent.classifier,
            "classify",
            new_callable=AsyncMock,
            return_value={"intent": "positive", "confidence": 0.93, "key_phrase": "interesante"},
        ):
            result = await agent.process_reply(
                "Sí, me interesa mucho, ¿cuándo podemos hablar?", lead, tenant
            )

    assert result["action"] == "meeting_booked"
    assert result["meeting"]["meet_link"] == "https://meet.google.com/abc-def-ghi"
    assert result["meeting"]["calendar_event_id"] == "gcal_event_123"
    assert result["message"] != ""


@pytest.mark.asyncio
async def test_scheduler_handles_no_calendar_credentials():
    agent = SchedulerAgent()
    lead = make_lead()
    tenant = make_tenant(with_calendar=False)  # sin credenciales de Calendar

    with patch.object(
        agent.classifier,
        "classify",
        new_callable=AsyncMock,
        return_value={"intent": "positive", "confidence": 0.9, "key_phrase": "sí"},
    ):
        result = await agent.process_reply("Sí quiero reunirme", lead, tenant)

    assert result["action"] == "no_calendar"


@pytest.mark.asyncio
async def test_scheduler_handles_question_intent():
    lead = make_lead()
    tenant = make_tenant()

    mock_slots = [
        {
            "start": "2025-06-03T14:00:00+00:00",
            "end": "2025-06-03T14:30:00+00:00",
            "label": "Tuesday 03 Jun, 14:00",
        }
    ]
    mock_event = {
        "event_id": "gcal_q_123",
        "meet_link": "https://meet.google.com/xyz-abc",
        "start": "2025-06-03T14:00:00+00:00",
        "html_link": "https://calendar.google.com/q",
    }

    with (
        patch("app.integrations.google.calendar.GoogleCalendarClient") as mock_cal_class,
        patch("app.agents.scheduler.agent.anthropic.Anthropic") as mock_claude,
    ):
        mock_cal = MagicMock()
        mock_cal.get_available_slots.return_value = mock_slots
        mock_cal.create_event.return_value = mock_event
        mock_cal_class.return_value = mock_cal

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="tool_use",
                input={
                    "selected_slot_start": mock_slots[0]["start"],
                    "selected_slot_end": mock_slots[0]["end"],
                    "confirmation_message": "Con gusto te explico más, agendemos una llamada.",
                },
            )
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        agent = SchedulerAgent()
        with patch.object(
            agent.classifier,
            "classify",
            new_callable=AsyncMock,
            return_value={"intent": "question", "confidence": 0.80, "key_phrase": "¿cuánto cuesta?"},
        ):
            result = await agent.process_reply("¿Cuánto cuesta la plataforma?", lead, tenant)

    assert result["action"] == "meeting_booked"
    assert result["intent"] == "question"
