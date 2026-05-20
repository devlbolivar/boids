import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.knowledge.models import KnowledgeDocument
from app.knowledge.schemas import DocumentCreate
from app.knowledge.chunker import chunk_text
from app.integrations.embeddings.client import EmbeddingClient
from app.integrations.qdrant.client import QdrantKnowledgeClient

logger = logging.getLogger(__name__)


class KnowledgeService:

    def __init__(self) -> None:
        self.embedder = EmbeddingClient()
        self.qdrant = QdrantKnowledgeClient()

    async def create_document(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        data: DocumentCreate,
    ) -> KnowledgeDocument:
        doc = KnowledgeDocument(
            tenant_id=str(tenant_id),
            title=data.title,
            doc_type=data.doc_type,
            content=data.content,
            status="pending",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    async def index_document(
        self,
        db: AsyncSession,
        doc_id: uuid.UUID,
        tenant_id: str,
    ) -> int:
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == str(doc_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        try:
            chunks = chunk_text(doc.content)
            if not chunks:
                raise ValueError("Document produced no valid chunks after splitting")

            vectors = await self.embedder.embed_batch(chunks)

            chunk_payloads = [
                {
                    "text": chunk,
                    "vector": vector,
                    "doc_type": doc.doc_type,
                    "chunk_index": i,
                    "title": doc.title,
                }
                for i, (chunk, vector) in enumerate(zip(chunks, vectors))
            ]

            count = await self.qdrant.upsert_chunks(
                tenant_id=tenant_id,
                doc_id=str(doc.id),
                chunks=chunk_payloads,
            )

            doc.status = "indexed"
            doc.chunk_count = count
            await db.commit()

            logger.info("Document indexed | doc_id=%s | chunks=%d", doc_id, count)
            return count

        except Exception as e:
            doc.status = "failed"
            doc.error_msg = str(e)
            await db.commit()
            logger.error("Indexing failed for doc %s: %s", doc_id, e)
            raise

    async def retrieve_context(
        self,
        tenant_id: str,
        query: str,
        top_k: int = 3,
        score_threshold: float = 0.72,
    ) -> list[dict]:
        query_vector = await self.embedder.embed(query)
        return await self.qdrant.search(
            tenant_id=tenant_id,
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
        )

    async def delete_document(
        self,
        db: AsyncSession,
        doc_id: uuid.UUID,
        tenant_id: str,
    ) -> bool:
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == str(doc_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return False

        await self.qdrant.delete_document_chunks(tenant_id, str(doc_id))
        await db.delete(doc)
        await db.commit()
        return True
