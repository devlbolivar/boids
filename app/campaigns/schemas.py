from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ICPConfig(BaseModel):
    industries:    list[str] = []
    company_sizes: list[str] = []
    titles:        list[str] = []
    locations:     list[str] = []
    keywords:      list[str] = []


class CampaignCreate(BaseModel):
    name:            str = Field(..., min_length=1, max_length=200)
    icp_override:    ICPConfig = ICPConfig()
    target_meetings: int = Field(default=10, ge=1, le=500)


class CampaignUpdate(BaseModel):
    name:            Optional[str] = Field(None, min_length=1, max_length=200)
    status:          Optional[str] = None
    icp_override:    Optional[ICPConfig] = None
    target_meetings: Optional[int] = Field(None, ge=1, le=500)


class CampaignResponse(BaseModel):
    id:              str
    tenant_id:       str
    name:            str
    status:          str
    icp_override:    dict
    target_meetings: int
    created_at:      datetime
    updated_at:      datetime
    leads_count:     int = 0

    model_config = {"from_attributes": True}
