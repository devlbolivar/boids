import asyncio
import logging
import uuid

from sqlalchemy import select, text
from datetime import datetime, timezone

from app.workers.celery_app import celery
from app.core.database import AsyncSessionLocal
from app.agents.scheduler.agent import SchedulerAgent
from app.leads.models import Lead
from app.outreach.models import OutreachEmail
from app.meetings.models import Meeting

logger = logging.getLogger(__name__)


@celery.task(
    name="scheduler.handle_reply",
    queue="delivery",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def handle_reply(
    self,
    lead_email: str,
    reply_body: str,
    instantly_id: str,
    thread_id: str = "",
) -> dict:
    try:
        return asyncio.run(
            _handle_reply_async(lead_email, reply_body, instantly_id, thread_id)
        )
    except Exception as exc:
        raise self.retry(exc=exc)


async def _handle_reply_async(
    lead_email: str,
    reply_body: str,
    instantly_id: str,
    thread_id: str,
) -> dict:
    """
    1. Busca el lead por email (sin RLS — el webhook no tiene tenant_id)
    2. Recupera tenant y configura RLS
    3. Ejecuta SchedulerAgent
    4. Persiste resultado (meeting, status, replied_at)
    """
    async with AsyncSessionLocal() as db:

        # Buscar el outreach_email por instantly_id para conseguir tenant_id
        email_record = None
        if instantly_id:
            result = await db.execute(
                select(OutreachEmail).where(
                    OutreachEmail.instantly_id == instantly_id
                )
            )
            email_record = result.scalar_one_or_none()

        # Fallback: buscar lead por email si no hay instantly_id o registro
        if not email_record:
            result = await db.execute(
                select(Lead).where(Lead.email == lead_email)
            )
            lead = result.scalar_one_or_none()
            if not lead:
                logger.warning("Lead not found for email %s", lead_email)
                return {"status": "skipped", "reason": "lead_not_found"}
            tenant_id = str(lead.tenant_id)
        else:
            tenant_id = str(email_record.tenant_id)

        # Configurar RLS
        await db.execute(
            text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id}
        )

        # Cargar lead con RLS activo
        result = await db.execute(
            select(Lead).where(Lead.email == lead_email)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return {"status": "skipped", "reason": "lead_not_found"}

        # Cargar tenant (sin RLS — tabla de tenants no tiene RLS)
        from app.tenants.models import Tenant
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            return {"status": "skipped", "reason": "tenant_not_found"}

        # Actualizar replied_at en outreach_email
        if email_record:
            email_record.replied_at = datetime.now(timezone.utc)
            email_record.reply_body = reply_body[:2000]

        # Ejecutar Scheduler Agent
        agent = SchedulerAgent()
        agent_result = await agent.process_reply(
            reply_body, lead, tenant, thread_id
        )

        # Persistir resultado según la acción
        action = agent_result.get("action")

        if action == "meeting_booked" and agent_result.get("meeting"):
            meeting_data = agent_result["meeting"]
            meeting = Meeting(
                tenant_id=tenant_id,
                lead_id=str(lead.id),
                outreach_email_id=str(email_record.id) if email_record else None,
                scheduled_at=datetime.fromisoformat(meeting_data["scheduled_at"]),
                calendar_event_id=meeting_data["calendar_event_id"],
                meet_link=meeting_data["meet_link"],
                status="scheduled",
            )
            db.add(meeting)
            lead.status = "meeting"

        elif action == "rejected":
            lead.status = "rejected"

        elif action not in ("ignored", "no_calendar", "no_slots", "calendar_error"):
            lead.status = "replied"

        await db.commit()

        logger.info(
            "Reply processed | lead=%s | intent=%s | action=%s",
            lead.id, agent_result["intent"], action,
        )
        return {
            "status": "ok",
            "intent": agent_result["intent"],
            "action": action,
            "lead_id": str(lead.id),
        }
