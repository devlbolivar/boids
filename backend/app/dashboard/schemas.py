from pydantic import BaseModel
from typing import Dict, List, Optional


class LeadSummary(BaseModel):
    total: int
    by_status: Dict[str, int]
    needs_review: int


class EmailSummary(BaseModel):
    sent: int
    opened: int
    replied: int
    open_rate: float
    reply_rate: float


class MeetingSummary(BaseModel):
    this_month: int
    total: int


class DashboardSummary(BaseModel):
    leads: LeadSummary
    emails: EmailSummary
    meetings: MeetingSummary


class FunnelStep(BaseModel):
    status: str
    count: int


class LeadInfo(BaseModel):
    name: str
    company: str
    email: str
    title: str


class UpcomingMeeting(BaseModel):
    id: str
    scheduled_at: str
    meet_link: Optional[str] = None
    lead: LeadInfo


class CostEntry(BaseModel):
    agent_type: str
    runs: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float


class CostSummary(BaseModel):
    period: str
    total_usd: float
    breakdown: List[CostEntry]
