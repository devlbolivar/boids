import asyncio
import logging

from celery import group
from sqlalchemy import select, text

from app.agents.research.agent import ResearchAgent
from app.core.database import AsyncSessionLocal
from app.leads.models import Lead
from app.leads.service import LeadService
from app.workers.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(
    name="research.process_lead",
    queue="agents",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    rate_limit="10/m",
)
def research_lead(self, lead_id: str, tenant_id: str) -> dict:
    try:
        return asyncio.run(_research_lead_async(lead_id, tenant_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _research_lead_async(lead_id: str, tenant_id: str, _session_factory=None) -> dict:
    sf = _session_factory or AsyncSessionLocal

    async with sf() as db:
        await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

        lead_svc = LeadService()
        lead = await lead_svc.get(db, lead_id)

        if not lead:
            logger.warning("Lead %s not found — skipping", lead_id)
            return {"status": "skipped", "reason": "not_found"}

        if lead.status != "new":
            logger.info("Lead %s already %s — skipping", lead_id, lead.status)
            return {"status": "skipped", "reason": "already_processed"}

        try:
            agent = ResearchAgent()
            ctx = await agent.run(lead)

            await lead_svc.update_research(
                db,
                lead_id=lead_id,
                research_ctx=ctx.model_dump(),
                status="researched",
            )

            logger.info(
                "Lead researched | id=%s | quality=%s | signals=%d",
                lead_id, ctx.data_quality, len(ctx.signals),
            )
            return {
                "status": "ok",
                "lead_id": lead_id,
                "data_quality": ctx.data_quality,
                "signals_found": len(ctx.signals),
            }

        except Exception as exc:
            logger.error("Research failed for lead %s: %s", lead_id, exc)
            await lead_svc.update_status(db, lead_id, "needs_review")
            raise


@celery.task(
    name="research.process_campaign",
    queue="orchestrator",
)
def research_campaign_leads(campaign_id: str, tenant_id: str) -> dict:
    return asyncio.run(_research_campaign_async(campaign_id, tenant_id))


async def _research_campaign_async(campaign_id: str, tenant_id: str, _session_factory=None) -> dict:
    sf = _session_factory or AsyncSessionLocal

    async with sf() as db:
        await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

        result = await db.execute(
            select(Lead)
            .where(
                Lead.campaign_id == campaign_id,
                Lead.status == "new",
            )
        )
        leads = result.scalars().all()

        if not leads:
            logger.info("No new leads for campaign %s", campaign_id)
            return {"status": "ok", "dispatched": 0}

        job = group(
            research_lead.s(str(lead.id), tenant_id)
            for lead in leads
        )
        result = job.apply_async()

        logger.info(
            "Research dispatched | campaign=%s | leads=%d",
            campaign_id, len(leads),
        )
        return {
            "status": "ok",
            "dispatched": len(leads),
            "group_id": result.id,
        }
