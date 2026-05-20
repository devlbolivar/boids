from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.campaigns.models import Campaign
from app.leads.models import Lead
from app.campaigns.schemas import CampaignCreate, CampaignUpdate


class CampaignService:

    async def create(self, db: AsyncSession, tenant_id: str, data: CampaignCreate) -> Campaign:
        campaign = Campaign(tenant_id=tenant_id, **data.model_dump())
        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)
        return campaign

    async def list(self, db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Campaign]:
        result = await db.execute(
            select(Campaign)
            .order_by(Campaign.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, campaign_id: str) -> Campaign | None:
        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def update(self, db: AsyncSession, campaign_id: str, data: CampaignUpdate) -> Campaign | None:
        campaign = await self.get(db, campaign_id)
        if not campaign:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(campaign, field, value)
        await db.commit()
        await db.refresh(campaign)
        return campaign

    async def delete(self, db: AsyncSession, campaign_id: str) -> bool:
        campaign = await self.get(db, campaign_id)
        if not campaign:
            return False
        await db.delete(campaign)
        await db.commit()
        return True

    async def get_leads_count(self, db: AsyncSession, campaign_id: str) -> int:
        result = await db.execute(
            select(func.count(Lead.id)).where(Lead.campaign_id == campaign_id)
        )
        return result.scalar_one()
