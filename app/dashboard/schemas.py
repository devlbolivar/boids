from pydantic import BaseModel


class LeadCounts(BaseModel):
    total:        int
    new:          int
    researched:   int
    emailed:      int
    replied:      int
    meeting:      int
    rejected:     int
    needs_review: int


class DashboardSummary(BaseModel):
    active_campaigns: int
    leads:            LeadCounts
