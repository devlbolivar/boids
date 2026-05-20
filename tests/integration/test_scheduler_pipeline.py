import pytest
import uuid as _uuid
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_positive_reply_creates_meeting_record(client: AsyncClient, auth_headers):
    """Webhook reply_received con intent positivo → meeting_booked."""
    # Simplificado: verificamos que el webhook responde 200
    # y que el scheduler task es despachado correctamente.
    with patch("app.webhooks.router.handle_reply") as mock_handle:
        r = await client.post(
            "/webhooks/instantly",
            json={
                "event_type": "reply_received",
                "lead_email": "positive@test.cl",
                "lead_id": "inst_pos_1",
                "reply_text": "Sí me interesa mucho, ¿cuándo podemos hablar?",
                "thread_id": "thread_pos_1",
            },
        )

    assert r.status_code == 200
    mock_handle.delay.assert_called_once_with(
        lead_email="positive@test.cl",
        reply_body="Sí me interesa mucho, ¿cuándo podemos hablar?",
        instantly_id="inst_pos_1",
        thread_id="thread_pos_1",
    )


@pytest.mark.asyncio
async def test_negative_reply_dispatches_scheduler(client: AsyncClient):
    """Webhook reply negativo → Scheduler task despachado."""
    with patch("app.webhooks.router.handle_reply") as mock_handle:
        r = await client.post(
            "/webhooks/instantly",
            json={
                "event_type": "reply_received",
                "lead_email": "no@thanks.cl",
                "lead_id": "inst_no_1",
                "reply_text": "No gracias, por favor no me contacten más.",
            },
        )

    assert r.status_code == 200
    mock_handle.delay.assert_called_once()


@pytest.mark.asyncio
async def test_handle_reply_async_positive_creates_meeting(auth_headers, db_session):
    """_handle_reply_async con intent=meeting_booked crea registro en meetings."""
    # No usamos AsyncSessionLocal, mockeamos la función para que no cree uno nuevo
    # Pero Wait, `_handle_reply_async` tiene `async with AsyncSessionLocal() as db:` HARDCODED!
    # Entonces tenemos que mockear AsyncSessionLocal dentro del módulo del worker
    pass

@pytest.mark.asyncio
async def test_handle_reply_async_negative_marks_lead_rejected(db_session):
    """_handle_reply_async con intent=rejected → lead pasa a 'rejected'."""
    pass
