import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_tenant_db, get_current_tenant
from app.knowledge.models import KnowledgeDocument
from app.knowledge.schemas import DocumentCreate, DocumentResponse, SearchResponse
from app.knowledge.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
svc = KnowledgeService()


@router.post("/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: str = Depends(get_current_tenant),
):
    doc = await svc.create_document(db, uuid.UUID(tenant_id), data)

    from app.workers.tasks.knowledge import index_document
    index_document.delay(str(doc.id), tenant_id)

    return doc


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_tenant_db),
    _: str = Depends(get_current_tenant),
):
    result = await db.execute(
        select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_tenant_db),
    tenant_id: str = Depends(get_current_tenant),
):
    deleted = await svc.delete_document(db, doc_id, tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/search", response_model=SearchResponse)
async def search_knowledge(
    query: str,
    top_k: int = 3,
    tenant_id: str = Depends(get_current_tenant),
):
    chunks = await svc.retrieve_context(tenant_id, query, top_k=top_k)
    return SearchResponse(query=query, chunks=chunks)
