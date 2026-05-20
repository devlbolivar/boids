from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LeadCreate(BaseModel):
    email:     str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    full_name: str = ""
    company:   str = ""
    title:     str = ""
    apollo_id: Optional[str] = None


class LeadUpdate(BaseModel):
    status:       Optional[str] = None
    research_ctx: Optional[dict] = None


class LeadResponse(BaseModel):
    id:           str
    tenant_id:    str
    campaign_id:  str
    email:        str
    full_name:    str
    company:      str
    title:        str
    status:       str
    research_ctx: dict
    apollo_id:    Optional[str]
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}
