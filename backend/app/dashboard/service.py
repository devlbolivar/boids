from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func


FUNNEL_ORDER = [
    "new", "researched", "emailed", "sent",
    "replied", "meeting", "rejected", "needs_review",
]

AGENT_PRICES = {
    "lead_finder": {"input": 1.0,  "output": 5.0,  "cache": 0.1},
    "researcher":  {"input": 3.0,  "output": 15.0, "cache": 0.3},
    "copywriter":  {"input": 3.0,  "output": 15.0, "cache": 0.3},
    "qa":          {"input": 1.0,  "output": 5.0,  "cache": 0.1},
    "intent":      {"input": 1.0,  "output": 5.0,  "cache": 0.1},
    "scheduler":   {"input": 3.0,  "output": 15.0, "cache": 0.3},
}


class DashboardService:

    async def get_summary(self, db: AsyncSession) -> dict:
        from app.leads.models import Lead
        from app.outreach.models import OutreachEmail
        from app.meetings.models import Meeting

        leads_result = await db.execute(
            select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
        )
        leads_by_status: dict = dict(leads_result.all())
        total_leads = sum(leads_by_status.values())

        email_result = await db.execute(
            select(
                func.count(OutreachEmail.id).label("sent"),
                func.count(OutreachEmail.opened_at).label("opened"),
                func.count(OutreachEmail.replied_at).label("replied"),
            )
        )
        email_stats = email_result.one()

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        meetings_month = (await db.execute(
            select(func.count(Meeting.id)).where(Meeting.created_at >= month_start)
        )).scalar_one()

        meetings_total = (await db.execute(
            select(func.count(Meeting.id))
        )).scalar_one()

        sent = email_stats.sent or 0
        opened = email_stats.opened or 0
        replied = email_stats.replied or 0

        return {
            "leads": {
                "total": total_leads,
                "by_status": leads_by_status,
                "needs_review": leads_by_status.get("needs_review", 0),
            },
            "emails": {
                "sent": sent,
                "opened": opened,
                "replied": replied,
                "open_rate": round(opened / sent, 3) if sent else 0,
                "reply_rate": round(replied / sent, 3) if sent else 0,
            },
            "meetings": {
                "this_month": meetings_month,
                "total": meetings_total,
            },
        }

    async def get_funnel(self, db: AsyncSession, campaign_id: str | None = None) -> list:
        from app.leads.models import Lead

        query = select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
        if campaign_id:
            query = query.where(Lead.campaign_id == campaign_id)

        result = await db.execute(query)
        counts: dict = dict(result.all())

        return [{"status": s, "count": counts.get(s, 0)} for s in FUNNEL_ORDER]

    async def get_upcoming_meetings(self, db: AsyncSession, limit: int = 10) -> list:
        from app.meetings.models import Meeting
        from app.leads.models import Lead

        result = await db.execute(
            select(Meeting, Lead)
            .join(Lead, Lead.id == Meeting.lead_id)
            .where(
                Meeting.status == "scheduled",
                Meeting.scheduled_at >= datetime.now(timezone.utc),
            )
            .order_by(Meeting.scheduled_at.asc())
            .limit(limit)
        )

        return [
            {
                "id": str(m.id),
                "scheduled_at": m.scheduled_at.isoformat(),
                "meet_link": m.meet_link,
                "lead": {
                    "name": l.full_name,
                    "company": l.company,
                    "email": l.email,
                    "title": l.title,
                },
            }
            for m, l in result.all()
        ]

    async def get_cost_summary(self, db: AsyncSession) -> dict:
        from app.tenants.models import AgentRun

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(
                AgentRun.agent_type,
                func.sum(AgentRun.input_tokens).label("input_tokens"),
                func.sum(AgentRun.output_tokens).label("output_tokens"),
                func.sum(AgentRun.cache_read_tokens).label("cache_read_tokens"),
                func.count(AgentRun.id).label("runs"),
            )
            .where(AgentRun.created_at >= month_start)
            .group_by(AgentRun.agent_type)
        )

        breakdown = []
        total_cost = 0.0

        for row in result.all():
            prices = AGENT_PRICES.get(row.agent_type, {"input": 3.0, "output": 15.0, "cache": 0.3})
            cost = round(
                (row.input_tokens or 0) / 1_000_000 * prices["input"]
                + (row.output_tokens or 0) / 1_000_000 * prices["output"]
                + (row.cache_read_tokens or 0) / 1_000_000 * prices["cache"],
                4,
            )
            total_cost += cost
            breakdown.append({
                "agent_type": row.agent_type,
                "runs": row.runs,
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "cache_read_tokens": row.cache_read_tokens or 0,
                "cost_usd": cost,
            })

        return {
            "period": now.strftime("%B %Y"),
            "total_usd": round(total_cost, 4),
            "breakdown": breakdown,
        }
