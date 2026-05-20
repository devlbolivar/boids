import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.campaigns.schemas import CampaignCreate, CampaignUpdate, CampaignResponse
from app.campaigns.service import CampaignService
from app.dependencies import get_tenant_db, get_current_tenant
from app.workers.tasks.copywriter import copywrite_campaign_leads
from app.workers.tasks.lead_finder import find_leads_for_campaign
from app.workers.tasks.research import research_campaign_leads

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
service = CampaignService()


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    campaign = await service.create(db, tenant_id, data)
    count = await service.get_leads_count(db, campaign.id)
    return {**campaign.__dict__, "leads_count": count}


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_tenant_db),
):
    campaigns = await service.list(db, limit, offset)
    result = []
    for c in campaigns:
        count = await service.get_leads_count(db, c.id)
        result.append({**c.__dict__, "leads_count": count})
    return result


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_tenant_db),
):
    campaign = await service.get(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    count = await service.get_leads_count(db, campaign.id)
    return {**campaign.__dict__, "leads_count": count}


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    data: CampaignUpdate,
    db: AsyncSession = Depends(get_tenant_db),
):
    campaign = await service.update(db, campaign_id, data)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    count = await service.get_leads_count(db, campaign.id)
    return {**campaign.__dict__, "leads_count": count}


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_tenant_db),
):
    deleted = await service.delete(db, campaign_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")


@router.post("/{campaign_id}/run/find-leads", status_code=status.HTTP_202_ACCEPTED)
async def run_lead_finder(
    campaign_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Despacha el Lead Finder Agent de forma asíncrona. Retorna el task_id."""
    campaign = await service.get(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    if campaign.status == "done":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign already done")

    await service.update(db, campaign_id, CampaignUpdate(status="running"))

    task = find_leads_for_campaign.delay(campaign_id=campaign_id, tenant_id=tenant_id)

    return {"task_id": task.id, "status": "queued", "message": "Lead Finder Agent dispatched"}


@router.post("/{campaign_id}/run/research", status_code=status.HTTP_202_ACCEPTED)
async def run_research_agent(
    campaign_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Despacha el Research Agent para todos los leads 'new' de la campaña."""
    from sqlalchemy import func, select
    from app.leads.models import Lead

    campaign = await service.get(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    result = await db.execute(
        select(func.count(Lead.id))
        .where(Lead.campaign_id == campaign_id, Lead.status == "new")
    )
    new_leads_count = result.scalar_one()

    if new_leads_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No leads with status 'new' in this campaign. Run find-leads first.",
        )

    task = research_campaign_leads.delay(campaign_id=campaign_id, tenant_id=tenant_id)

    return {
        "task_id": task.id,
        "status": "queued",
        "leads_queued": new_leads_count,
        "message": f"Research Agent dispatched for {new_leads_count} leads",
    }




@router.get("/{campaign_id}/run/{task_id}/status")
async def get_task_status(
    campaign_id: str,
    task_id: str,
    _: str = Depends(get_current_tenant),
):
    """Polling del estado del task de Celery."""
    from app.workers.celery_app import celery
    task = celery.AsyncResult(task_id)

    return {
        "task_id": task_id,
        "state": task.state,
        "result": task.result if task.ready() else None,
    }


@router.post("/{campaign_id}/run/copywrite", status_code=status.HTTP_202_ACCEPTED)
async def run_copywriter(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: str = Depends(get_current_tenant),
):
    """Despacha el Copywriter + QA Agent para todos los leads 'researched' de la campaña."""
    from sqlalchemy import func, select
    from app.leads.models import Lead

    campaign = await service.get(db, str(campaign_id))
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    result = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.campaign_id == str(campaign_id),
            Lead.status == "researched",
        )
    )
    count = result.scalar_one()

    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No leads with status 'researched'. Run research first.",
        )

    task = copywrite_campaign_leads.delay(str(campaign_id), tenant_id)

    return {
        "task_id": task.id,
        "status": "queued",
        "leads_queued": count,
    }

