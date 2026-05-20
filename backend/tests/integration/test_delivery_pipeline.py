import pytest
import uuid as _uuid
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_send_endpoint_dispatches_task(client: AsyncClient, auth_headers, db_session):
    """POST /campaigns/{id}/run/send → 202 con emails_queued."""
    # Crear campaña
    r = await client.post("/campaigns", json={"name": "Send Test"}, headers=auth_headers)
    assert r.status_code == 201
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    # Setup directo en DB (simular output de M6)
    from sqlalchemy import text
    from app.leads.models import Lead
    from app.outreach.models import OutreachEmail

    await db_session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
    lead = Lead(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        email="send@test.cl",
        status="emailed",
    )
    db_session.add(lead)
    await db_session.flush()

    email = OutreachEmail(
        tenant_id=tenant_id,
        lead_id=str(lead.id),
        subject="Test Subject",
        body="Test Body",
        quality_score=0.85,
    )
    db_session.add(email)
    await db_session.commit()

    with patch("app.workers.tasks.delivery.send_campaign_emails") as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-send-1")
        r = await client.post(
            f"/campaigns/{campaign_id}/run/send",
            headers=auth_headers,
        )

    assert r.status_code == 202
    body = r.json()
    assert body["emails_queued"] == 1
    assert body["status"] == "queued"
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_send_endpoint_returns_400_when_no_emails(client: AsyncClient, auth_headers):
    """POST /campaigns/{id}/run/send → 400 si no hay emails emailed."""
    r = await client.post("/campaigns", json={"name": "Empty Campaign"}, headers=auth_headers)
    campaign_id = r.json()["id"]

    r = await client.post(
        f"/campaigns/{campaign_id}/run/send",
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_webhook_email_opened_returns_ok(client: AsyncClient):
    """Webhook email_opened → 200 ok."""
    with patch("app.webhooks.router._handle_email_opened", new_callable=AsyncMock):
        r = await client.post(
            "/webhooks/instantly",
            json={
                "event_type": "email_opened",
                "lead_id": "inst_lead_abc",
                "lead_email": "cto@test.cl",
            },
        )

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_reply_dispatches_scheduler(client: AsyncClient):
    """Webhook reply_received → Celery task del Scheduler."""
    with patch("app.webhooks.router.handle_reply") as mock_handle:
        mock_handle.delay.return_value = MagicMock(id="sched-task-1")
        r = await client.post(
            "/webhooks/instantly",
            json={
                "event_type": "reply_received",
                "lead_email": "cto@startup.cl",
                "lead_id": "inst_lead_xyz",
                "reply_text": "Sí me interesa, hablemos",
                "thread_id": "thread_abc",
            },
        )

    assert r.status_code == 200
    mock_handle.delay.assert_called_once_with(
        lead_email="cto@startup.cl",
        reply_body="Sí me interesa, hablemos",
        instantly_id="inst_lead_xyz",
        thread_id="thread_abc",
    )


@pytest.mark.asyncio
async def test_webhook_unknown_event_returns_ok(client: AsyncClient):
    """Webhook con evento desconocido → 200 ok (no rompe)."""
    r = await client.post(
        "/webhooks/instantly",
        json={"event_type": "email_bounced", "lead_id": "xyz"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_401(client: AsyncClient):
    """Webhook con firma inválida → 401."""
    r = await client.post(
        "/webhooks/instantly",
        json={"event_type": "reply_received"},
        headers={"x-instantly-signature": "bad_signature"},
    )
    assert r.status_code == 401
