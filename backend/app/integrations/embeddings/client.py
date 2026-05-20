from openai import AsyncOpenAI
from app.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536


class EmbeddingClient:

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def embed(self, text: str) -> list[float]:
        text = text.replace("\n", " ").strip()
        response = await self.client.embeddings.create(input=text, model=EMBEDDING_MODEL)
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        cleaned = [t.replace("\n", " ").strip() for t in texts]
        response = await self.client.embeddings.create(input=cleaned, model=EMBEDDING_MODEL)
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
