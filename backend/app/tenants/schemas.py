from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class TenantResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    plan: str
    is_active: bool
    icp_config: dict
    api_keys_enc: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    icp_config: Optional[dict] = None
