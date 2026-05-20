from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_tenant_db, get_current_tenant
from app.dashboard.service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
service = DashboardService()


@router.get("/summary")
async def get_summary(
    db: AsyncSession = Depends(get_tenant_db),
    _: str = Depends(get_current_tenant),
):
    return await service.get_summary(db)


@router.get("/funnel")
async def get_funnel(
    campaign_id: str | None = None,
    db: AsyncSession = Depends(get_tenant_db),
    _: str = Depends(get_current_tenant),
):
    return await service.get_funnel(db, campaign_id)


@router.get("/meetings/upcoming")
async def get_upcoming_meetings(
    limit: int = 10,
    db: AsyncSession = Depends(get_tenant_db),
    _: str = Depends(get_current_tenant),
):
    return await service.get_upcoming_meetings(db, limit)


@router.get("/cost")
async def get_cost_summary(
    db: AsyncSession = Depends(get_tenant_db),
    _: str = Depends(get_current_tenant),
):
    return await service.get_cost_summary(db)
