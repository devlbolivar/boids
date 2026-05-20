from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.auth.schemas import TenantRegister
from app.tenants.models import Tenant
from app.core.security import get_password_hash, verify_password

async def authenticate_tenant(
    db: AsyncSession,
    email: str,
    password: str
) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.email == email))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        return None
        
    if not verify_password(password, tenant.password_hash):
        return None
        
    return tenant

async def register_tenant(
    db: AsyncSession,
    reg_data: TenantRegister
) -> Tenant:
    existing = await db.execute(
        select(Tenant).where(Tenant.email == reg_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{reg_data.email}' is already registered."
        )

    hashed_pwd = get_password_hash(reg_data.password)
    new_tenant = Tenant(
        name=reg_data.name,
        email=reg_data.email,
        password_hash=hashed_pwd,
        is_active=True
    )
    
    db.add(new_tenant)
    await db.commit()
    await db.refresh(new_tenant)
    
    return new_tenant
