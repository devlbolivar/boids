import asyncio
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.lead_finder.agent import LeadFinderAgent
from app.agents.lead_finder.normalizer import normalize_apollo_batch
from app.campaigns.schemas import ICPConfig
from app.campaigns.service import CampaignService
from app.core.database import AsyncSessionLocal
from app.core.security import decrypt_credential
from app.integrations.apollo.client import ApolloClient
from app.leads.service import LeadService
from app.workers.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(
    name="leads.find_for_campaign",
    queue="agents",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
)
def find_leads_for_campaign(self, campaign_id: str, tenant_id: str) -> dict:
    """Despacha el Lead Finder Agent para una campaña."""
    return asyncio.run(_find_leads_async(campaign_id, tenant_id))


async def _find_leads_async(
    campaign_id: str,
    tenant_id: str,
    _session_factory=None,
) -> dict:
    """
    Pipeline completo del Lead Finder Agent.
    _session_factory es inyectable para tests; en producción usa AsyncSessionLocal.
    """
    sf = _session_factory or AsyncSessionLocal

    async with sf() as db:
        await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

        campaign_svc = CampaignService()
        lead_svc = LeadService()

        campaign = await campaign_svc.get(db, campaign_id)
        if not campaign:
            logger.error("Campaign %s not found", campaign_id)
            return {"status": "error", "message": "campaign not found"}

        tenant = await _get_tenant(db, tenant_id)
        if not tenant:
            logger.error("Tenant %s not found", tenant_id)
            return {"status": "error", "message": "tenant not found"}

        base_icp = ICPConfig(**(tenant.icp_config or {}))
        override_icp = ICPConfig(**(campaign.icp_override or {}))
        merged_icp = _merge_icp(base_icp, override_icp)

        apollo_key = _get_apollo_key(tenant)
        apollo_client = ApolloClient(api_key=apollo_key)

        agent = LeadFinderAgent(apollo_client)
        raw_contacts = await agent.run(merged_icp, max_leads=campaign.target_meetings * 5)

        leads_to_create = normalize_apollo_batch(raw_contacts)

        created = 0
        skipped = 0
        for lead_data in leads_to_create:
            existing = await lead_svc.get_by_email(db, lead_data.email)
            if existing:
                skipped += 1
            else:
                await lead_svc.create(db, tenant_id, campaign_id, lead_data)
                created += 1

        logger.info(
            "Lead Finder done | campaign=%s | found=%d | created=%d | skipped=%d",
            campaign_id,
            len(raw_contacts),
            created,
            skipped,
        )

        return {
            "status": "ok",
            "found": len(raw_contacts),
            "created": created,
            "skipped_duplicates": skipped,
        }


async def _get_tenant(db, tenant_id: str):
    from sqlalchemy import select
    from app.tenants.models import Tenant

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


def _merge_icp(base: ICPConfig, override: ICPConfig) -> ICPConfig:
    """Override gana sobre base. Keywords se combinan."""
    return ICPConfig(
        industries=override.industries or base.industries,
        company_sizes=override.company_sizes or base.company_sizes,
        titles=override.titles or base.titles,
        locations=override.locations or base.locations,
        keywords=list(set(base.keywords + override.keywords)),
    )


def _get_apollo_key(tenant) -> str | None:
    """Desencripta y retorna la API key de Apollo del tenant, si existe."""
    api_keys = tenant.api_keys_enc or {}
    encrypted = api_keys.get("apollo")
    if not encrypted:
        return None
    return decrypt_credential(encrypted, str(tenant.id))
