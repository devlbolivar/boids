import asyncio
import logging
import uuid

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.knowledge.service import KnowledgeService
from app.workers.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(
    name="knowledge.index_document",
    queue="agents",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def index_document(self, doc_id: str, tenant_id: str) -> dict:
    try:
        return asyncio.run(_index_document_async(doc_id, tenant_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _index_document_async(
    doc_id: str, tenant_id: str, _session_factory=None
) -> dict:
    sf = _session_factory or AsyncSessionLocal

    async with sf() as db:
        await db.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        svc = KnowledgeService()
        chunk_count = await svc.index_document(db, uuid.UUID(doc_id), tenant_id)
        return {"status": "ok", "doc_id": doc_id, "chunks": chunk_count}
