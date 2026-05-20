import uuid
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)
from app.config import settings
from app.integrations.embeddings.client import EMBEDDING_DIMS


class QdrantKnowledgeClient:

    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)

    def _collection_name(self, tenant_id: str) -> str:
        return f"knowledge_{tenant_id.replace('-', '')}"

    async def ensure_collection(self, tenant_id: str) -> None:
        name = self._collection_name(tenant_id)
        exists = await self.client.collection_exists(name)
        if not exists:
            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=EMBEDDING_DIMS, distance=Distance.COSINE),
            )

    async def upsert_chunks(
        self,
        tenant_id: str,
        doc_id: str,
        chunks: list[dict],
    ) -> int:
        await self.ensure_collection(tenant_id)
        name = self._collection_name(tenant_id)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=chunk["vector"],
                payload={
                    "text": chunk["text"],
                    "doc_type": chunk["doc_type"],
                    "doc_id": doc_id,
                    "tenant_id": tenant_id,
                    "chunk_index": chunk["chunk_index"],
                    "title": chunk.get("title", ""),
                },
            )
            for chunk in chunks
        ]

        await self.client.upsert(collection_name=name, points=points)
        return len(points)

    async def search(
        self,
        tenant_id: str,
        query_vector: list[float],
        top_k: int = 3,
        score_threshold: float = 0.72,
        doc_type_filter: str | None = None,
    ) -> list[dict]:
        name = self._collection_name(tenant_id)

        query_filter: Filter | None = None
        if doc_type_filter:
            query_filter = Filter(
                must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type_filter))]
            )

        results = await self.client.search(
            collection_name=name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            {
                "text": r.payload["text"],
                "doc_type": r.payload["doc_type"],
                "doc_id": r.payload["doc_id"],
                "title": r.payload.get("title", ""),
                "score": r.score,
            }
            for r in results
        ]

    async def delete_document_chunks(self, tenant_id: str, doc_id: str) -> None:
        name = self._collection_name(tenant_id)
        await self.client.delete(
            collection_name=name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                )
            ),
        )

    async def delete_collection(self, tenant_id: str) -> None:
        name = self._collection_name(tenant_id)
        exists = await self.client.collection_exists(name)
        if exists:
            await self.client.delete_collection(name)
