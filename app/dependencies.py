from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session without RLS scoping. For auth endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_current_tenant(token: str = Depends(oauth2_scheme)) -> str:
    """Extracts tenant_id from the JWT token."""
    payload = decode_access_token(token)
    if not payload or not payload.get("tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload["tenant_id"]

async def get_tenant_db(tenant_id: str = Depends(get_current_tenant)) -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session with RLS scoping via app.tenant_id."""
    # PostgreSQL SET LOCAL does not support bind parameters; tenant_id is a UUID
    # extracted from a signed JWT so direct interpolation is safe.
    async with AsyncSessionLocal() as session:
        await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        try:
            yield session
        finally:
            await session.close()
