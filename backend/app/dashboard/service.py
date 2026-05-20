from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.campaigns.models import Campaign
from app.leads.models import Lead


class DashboardService:

    async def get_summary(self, db: AsyncSession) -> dict:
        campaigns_result = await db.execute(
            select(func.count(Campaign.id)).where(Campaign.status == "running")
        )
        active_campaigns = campaigns_result.scalar_one()

        leads_result = await db.execute(
            select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
        )
        leads_by_status = {row[0]: row[1] for row in leads_result.all()}

        return {
            "active_campaigns": active_campaigns,
            "leads": {
                "total":        sum(leads_by_status.values()),
                "new":          leads_by_status.get("new", 0),
                "researched":   leads_by_status.get("researched", 0),
                "emailed":      leads_by_status.get("emailed", 0),
                "replied":      leads_by_status.get("replied", 0),
                "meeting":      leads_by_status.get("meeting", 0),
                "rejected":     leads_by_status.get("rejected", 0),
                "needs_review": leads_by_status.get("needs_review", 0),
            },
        }
