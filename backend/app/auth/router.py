from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token
from app.dependencies import get_db
from app.auth.schemas import TenantRegister, RegisterResponse, Token
from app.auth.service import authenticate_tenant, register_tenant

router = APIRouter()

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    reg_data: TenantRegister,
    db: AsyncSession = Depends(get_db)
):
    tenant = await register_tenant(db, reg_data)
    access_token = create_access_token(
        data={"sub": tenant.email, "tenant_id": str(tenant.id)}
    )
    return RegisterResponse(tenant_id=str(tenant.id), access_token=access_token)

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    tenant = await authenticate_tenant(
        db=db,
        email=form_data.username,
        password=form_data.password
    )
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": tenant.email, "tenant_id": str(tenant.id)}
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer"
    )
