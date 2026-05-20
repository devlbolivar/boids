from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_tenant_db, get_current_tenant

router = APIRouter(prefix="/review", tags=["review"])


@router.get("")
async def get_review_queue(
    limit: int = 20,
    db: AsyncSession = Depends(get_tenant_db),
    _: str = Depends(get_current_tenant),
):
    from sqlalchemy import select
    from app.leads.models import Lead
    from app.outreach.models import OutreachEmail

    result = await db.execute(
        select(Lead, OutreachEmail)
        .outerjoin(OutreachEmail, OutreachEmail.lead_id == Lead.id)
        .where(Lead.status == "needs_review")
        .order_by(Lead.updated_at.desc())
        .limit(limit)
    )

    return [
        {
            "lead": {
                "id": str(l.id),
                "email": l.email,
                "full_name": l.full_name,
                "company": l.company,
                "title": l.title,
                "research_ctx": l.research_ctx,
            },
            "email_draft": {
                "id": str(e.id),
                "subject": e.subject,
                "body": e.body,
                "quality_score": e.quality_score,
                "qa_details": e.qa_details,
            } if e else None,
        }
        for l, e in result.all()
    ]


@router.post("/{lead_id}/approve", status_code=200)
async def approve_review(
    lead_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: str = Depends(get_current_tenant),
):
    import uuid as _uuid
    from sqlalchemy import select
    from app.leads.models import Lead
    from app.outreach.models import OutreachEmail

    try:
        _uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Lead not found in review queue")

    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead or lead.status != "needs_review":
        raise HTTPException(status_code=404, detail="Lead not found in review queue")

    result = await db.execute(
        select(OutreachEmail)
        .where(OutreachEmail.lead_id == lead.id)
        .order_by(OutreachEmail.created_at.desc())
        .limit(1)
    )
    email = result.scalar_one_or_none()

    if not email:
        raise HTTPException(status_code=400, detail="No email draft found for this lead")

    lead.status = "emailed"
    await db.commit()

    from app.workers.tasks.delivery import send_email
    send_email.delay(str(email.id), tenant_id)

    return {"status": "ok", "action": "approved", "lead_id": lead_id}


@router.post("/{lead_id}/reject", status_code=200)
async def reject_review(
    lead_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    _: str = Depends(get_current_tenant),
):
    import uuid as _uuid
    from sqlalchemy import select
    from app.leads.models import Lead

    try:
        _uuid.UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Lead not found in review queue")

    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead or lead.status != "needs_review":
        raise HTTPException(status_code=404, detail="Lead not found in review queue")

    lead.status = "rejected"
    await db.commit()

    return {"status": "ok", "action": "rejected", "lead_id": lead_id}
