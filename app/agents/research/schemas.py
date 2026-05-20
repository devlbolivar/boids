from pydantic import BaseModel, Field
from typing import Literal


class ResearchSignal(BaseModel):
    type: Literal[
        "hiring",
        "funding",
        "expansion",
        "tech_stack",
        "news",
        "pain_point",
        "award",
    ]
    description: str = Field(..., max_length=300)
    relevance:   str = Field(..., description="Por qué esto importa para el pitch")
    date:        str = ""


class CompanyContext(BaseModel):
    website:       str = ""
    founded:       str = ""
    size_estimate: str = ""
    recent_news:   str = ""
    description:   str = ""


class ResearchContext(BaseModel):
    summary:         str = Field(..., max_length=500,
                         description="Por qué este lead es un buen prospecto. Max 500 chars.")
    signals:         list[ResearchSignal] = Field(default_factory=list, max_length=5)
    pain_points:     list[str] = Field(default_factory=list, max_length=5)
    company_context: CompanyContext = Field(default_factory=CompanyContext)
    data_quality:    Literal["high", "medium", "low"] = "medium"
    limited_data:    bool = False
    researched_at:   str = ""
