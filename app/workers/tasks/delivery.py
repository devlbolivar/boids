import asyncio
import logging
import uuid

from celery import group
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.integrations.instantly.client import InstantlyClient
from app.leads.models import Lead
from app.outreach.models import OutreachEmail
from app.workers.celery_app import celery
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@celery.task(
    name="delivery.send_email",
    queue="delivery",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_email(self, outreach_email_id: str, tenant_id: str) -> dict:
    try:
        return asyncio.run(_send_email_async(outreach_email_id, tenant_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _send_email_async(outreach_email_id: str, tenant_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id}
        )

        # Fetch email draft
        result = await db.execute(
            select(OutreachEmail).where(
                OutreachEmail.id == outreach_email_id
            )
        )
        email = result.scalar_one_or_none()
        if not email:
            return {"status": "error", "reason": "email_not_found"}

        # Fetch lead
        result = await db.execute(
            select(Lead).where(Lead.id == email.lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return {"status": "error", "reason": "lead_not_found"}

        # Obtener tenant para el campaign_id de Instantly
        from app.tenants.models import Tenant
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            return {"status": "error", "reason": "tenant_not_found"}

        instantly_campaign_id = (tenant.api_keys_enc or {}).get(
            "instantly_campaign_id"
        )
        if not instantly_campaign_id:
            logger.error("No Instantly campaign_id for tenant %s", tenant_id)
            return {"status": "error", "reason": "no_instantly_campaign_id"}

        try:
            instantly_key = (tenant.api_keys_enc or {}).get("instantly")
            client = InstantlyClient(api_key=instantly_key)

            response = await client.add_lead_to_campaign(
                campaign_id=instantly_campaign_id,
                email=lead.email,
                first_name=(
                    lead.full_name.split()[0] if lead.full_name else ""
                ),
                subject=email.subject,
                body=email.body,
            )

            # Actualizar email con instantly_id y sent_at
            email.instantly_id = response.get("id") or response.get("lead_id")
            email.sent_at = datetime.now(timezone.utc)

            # Actualizar status del lead a "sent"
            lead.status = "sent"
            await db.commit()

            logger.info(
                "Email sent | lead=%s | instantly_id=%s",
                lead.id, email.instantly_id,
            )
            return {"status": "ok", "instantly_id": email.instantly_id}

        except Exception as exc:
            logger.error(
                "Instantly delivery failed for %s: %s", outreach_email_id, exc
            )
            raise


@celery.task(
    name="delivery.send_campaign_emails",
    queue="orchestrator",
)
def send_campaign_emails(campaign_id: str, tenant_id: str) -> dict:
    """Envía todos los emails aprobados (status='emailed') de una campaña."""
    return asyncio.run(_send_campaign_async(campaign_id, tenant_id))


async def _send_campaign_async(campaign_id: str, tenant_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id}
        )

        # Fetch outreach_emails de leads en status "emailed"
        result = await db.execute(
            select(OutreachEmail)
            .join(Lead, Lead.id == OutreachEmail.lead_id)
            .where(
                Lead.campaign_id == campaign_id,
                Lead.status == "emailed",
                OutreachEmail.sent_at.is_(None),  # no enviados aún
            )
        )
        emails = result.scalars().all()

        if not emails:
            return {"status": "ok", "dispatched": 0}

        job = group(
            send_email.s(str(e.id), tenant_id)
            for e in emails
        )
        job.apply_async()

        return {"status": "ok", "dispatched": len(emails)}
