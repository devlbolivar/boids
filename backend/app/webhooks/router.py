import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.integrations.instantly.client import InstantlyClient
from app.workers.tasks.scheduler import handle_reply

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/instantly")
async def instantly_webhook(
    request: Request,
    x_instantly_signature: str | None = Header(None),
):
    """
    Recibe eventos de Instantly:
    - email_sent:     actualiza sent_at
    - email_opened:   actualiza opened_at
    - reply_received: dispara el Scheduler Agent
    """
    raw_body = await request.body()

    # Verificar firma si está configurada
    if x_instantly_signature:
        client = InstantlyClient()
        valid = await client.verify_webhook_signature(raw_body, x_instantly_signature)
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    event = payload.get("event_type", "")

    logger.info("Instantly webhook received | event=%s", event)

    if event == "email_opened":
        await _handle_email_opened(payload)

    elif event == "reply_received":
        # Procesamiento asíncrono — responder 200 de inmediato
        _dispatch_scheduler(payload)

    # Siempre responder 200 rápido — Instantly reintenta si no recibe respuesta
    return {"status": "ok"}


async def _handle_email_opened(payload: dict) -> None:
    """Actualiza opened_at en outreach_emails."""
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import update
    from datetime import datetime, timezone
    from app.outreach.models import OutreachEmail

    instantly_id = payload.get("lead_id") or payload.get("instantly_id")
    if not instantly_id:
        return

    async with AsyncSessionLocal() as db:
        # Sin RLS aquí — el webhook no tiene tenant_id en contexto
        # Usamos el instantly_id como clave global
        await db.execute(
            update(OutreachEmail)
            .where(OutreachEmail.instantly_id == instantly_id)
            .values(opened_at=datetime.now(timezone.utc))
        )
        await db.commit()


def _dispatch_scheduler(payload: dict) -> None:
    """Despacha el Scheduler Agent de forma async."""
    handle_reply.delay(
        lead_email=payload.get("lead_email", ""),
        reply_body=payload.get("reply_text", ""),
        instantly_id=payload.get("lead_id", ""),
        thread_id=payload.get("thread_id", ""),
    )
