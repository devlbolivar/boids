from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.tenants.models import Tenant
from app.tenants.schemas import TenantUpdate


async def get_tenant_me(db: AsyncSession, tenant_id: str) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def update_tenant_me(db: AsyncSession, tenant_id: str, update_data: TenantUpdate) -> Tenant | None:
    tenant = await get_tenant_me(db, tenant_id)
    if not tenant:
        return None
        
    if update_data.name is not None:
        tenant.name = update_data.name
    if update_data.icp_config is not None:
        tenant.icp_config = update_data.icp_config
        
    await db.commit()
    await db.refresh(tenant)
    return tenant


