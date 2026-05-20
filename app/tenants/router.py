from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_tenant_db, get_current_tenant
from app.tenants.schemas import TenantResponse, TenantUpdate
from app.tenants.service import get_tenant_me, update_tenant_me

router = APIRouter()

@router.get("/me", response_model=TenantResponse)
async def read_tenant_me(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db)
):
    tenant = await get_tenant_me(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    return tenant

@router.patch("/me", response_model=TenantResponse)
async def patch_tenant_me(
    update_data: TenantUpdate,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_tenant_db)
):
    tenant = await update_tenant_me(db, tenant_id, update_data)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    return tenant
