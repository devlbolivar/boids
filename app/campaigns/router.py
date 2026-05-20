from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_tenant_db, get_current_tenant
from app.campaigns.service import CampaignService
from app.campaigns.schemas import CampaignCreate, CampaignUpdate, CampaignResponse

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
