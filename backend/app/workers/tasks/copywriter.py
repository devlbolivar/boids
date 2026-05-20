import asyncio
import logging
import uuid

from celery import group
from sqlalchemy import select, text

from app.agents.copywriter.pipeline import run_copywriter_pipeline
from app.core.database import AsyncSessionLocal
from app.leads.models import Lead
from app.leads.service import LeadService
from app.outreach.models import OutreachEmail
from app.workers.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(
    name="copywriter.process_lead",
    queue="agents",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    rate_limit="8/m",  # Sonnet es más caro — rate limit más conservador
)
def copywrite_lead(self, lead_id: str, tenant_id: str) -> dict:
    try:
        return asyncio.run(_copywrite_lead_async(lead_id, tenant_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _copywrite_lead_async(
    lead_id: str,
    tenant_id: str,
    _session_factory=None,
) -> dict:
    sf = _session_factory or AsyncSessionLocal

    async with sf() as db:
        await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

        lead_svc = LeadService()
        lead = await lead_svc.get(db, lead_id)

        # Fetch tenant without RLS (tenants table has no RLS)
        from sqlalchemy import select as _select
        from app.tenants.models import Tenant

        tenant_result = await db.execute(
            _select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        if not lead or not tenant:
            return {"status": "error", "reason": "not_found"}

        if lead.status != "researched":
            return {"status": "skipped", "reason": f"status_is_{lead.status}"}

        try:
            draft, score = await run_copywriter_pipeline(lead, tenant)

            if draft and score and score.approved:
                # Persistir email draft
                email_record = OutreachEmail(
                    tenant_id=tenant_id,
                    lead_id=lead.id,
                    subject=draft.subject,
                    body=draft.body,
                    quality_score=score.total,
                    qa_details=score.model_dump(),
                )
                db.add(email_record)

                # Actualizar status del lead
                lead.status = "emailed"
                await db.commit()
                await db.refresh(email_record)

                return {
                    "status": "ok",
                    "lead_id": lead_id,
                    "quality_score": score.total,
                    "email_id": str(email_record.id),
                }
            else:
                lead.status = "needs_review"
                await db.commit()
                return {
                    "status": "needs_review",
                    "lead_id": lead_id,
                    "quality_score": score.total if score else 0,
                    "issues": score.issues if score else [],
                }

        except Exception as exc:
            logger.error("Copywriter failed for lead %s: %s", lead_id, exc)
            lead.status = "needs_review"
            await db.commit()
            raise


@celery.task(name="copywriter.process_campaign", queue="orchestrator")
def copywrite_campaign_leads(campaign_id: str, tenant_id: str) -> dict:
    return asyncio.run(_copywrite_campaign_async(campaign_id, tenant_id))


async def _copywrite_campaign_async(
    campaign_id: str,
    tenant_id: str,
    _session_factory=None,
) -> dict:
    sf = _session_factory or AsyncSessionLocal

    async with sf() as db:
        await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

        result = await db.execute(
            select(Lead).where(
                Lead.campaign_id == campaign_id,
                Lead.status == "researched",
            )
        )
        leads = result.scalars().all()

        if not leads:
            return {"status": "ok", "dispatched": 0}

        job = group(
            copywrite_lead.s(str(lead.id), tenant_id)
            for lead in leads
        )
        result = job.apply_async()

        logger.info(
            "Copywriter dispatched | campaign=%s | leads=%d",
            campaign_id, len(leads),
        )
        return {
            "status": "ok",
            "dispatched": len(leads),
            "group_id": result.id,
        }
