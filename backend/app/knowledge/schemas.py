from pydantic import BaseModel, UUID4, Field
from typing import Literal, Optional
from datetime import datetime

DocumentType = Literal[
    "value_prop",
    "case_study",
    "objections",
    "pain_points",
    "email_examples",
    "other",
]


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    doc_type: DocumentType
    content: str = Field(
        ..., min_length=50, description="Mínimo 50 caracteres para producir chunks útiles"
    )


class DocumentResponse(BaseModel):
    id: UUID4
    tenant_id: UUID4
    title: str
    doc_type: str
    chunk_count: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeChunk(BaseModel):
    text: str
    doc_type: str
    doc_id: str
    title: str
    score: float


class SearchResponse(BaseModel):
    query: str
    chunks: list[KnowledgeChunk]
