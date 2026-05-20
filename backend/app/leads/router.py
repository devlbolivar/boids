from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_tenant_db, get_current_tenant
from app.leads.service import LeadService
from app.leads.schemas import LeadCreate, LeadResponse

router = APIRouter(prefix="/campaigns/{campaign_id}/leads", tags=["leads"])
service = LeadService()


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def add_lead(
    campaign_id: str,
    data: LeadCreate,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db),
):
    return await service.create(db, tenant_id, campaign_id, data)


@router.get("", response_model=list[LeadResponse])
async def list_leads(
    campaign_id: str,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_tenant_db),
):
    return await service.list_by_campaign(db, campaign_id, status, limit, offset)
