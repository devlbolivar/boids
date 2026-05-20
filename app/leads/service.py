from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.leads.models import Lead
from app.leads.schemas import LeadCreate


class LeadService:

    async def create(
        self,
        db: AsyncSession,
        tenant_id: str,
        campaign_id: str,
        data: LeadCreate,
    ) -> Lead:
        existing = await self.get_by_email(db, data.email)
        if existing:
            return existing

        lead = Lead(tenant_id=tenant_id, campaign_id=campaign_id, **data.model_dump())
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        return lead

    async def get_by_email(self, db: AsyncSession, email: str) -> Lead | None:
        result = await db.execute(select(Lead).where(Lead.email == email))
        return result.scalar_one_or_none()

    async def list_by_campaign(
        self,
        db: AsyncSession,
        campaign_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Lead]:
        query = select(Lead).where(Lead.campaign_id == campaign_id)
        if status:
            query = query.where(Lead.status == status)
        query = query.order_by(Lead.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, lead_id: str) -> Lead | None:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        return result.scalar_one_or_none()

    async def update_status(self, db: AsyncSession, lead_id: str, status: str) -> Lead | None:
        lead = await self.get(db, lead_id)
        if not lead:
            return None
        lead.status = status
        await db.commit()
        await db.refresh(lead)
        return lead

    async def update_research(
        self,
        db: AsyncSession,
        lead_id: str,
        research_ctx: dict,
        status: str = "researched",
    ) -> Lead | None:
        lead = await self.get(db, lead_id)
        if not lead:
            return None
        lead.research_ctx = research_ctx
        lead.status = status
        await db.commit()
        await db.refresh(lead)
        return lead
