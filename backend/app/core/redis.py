from typing import Optional
from redis.asyncio import Redis, from_url
from app.config import settings

redis_client: Optional[Redis] = None

async def init_redis() -> Redis:
    """Initialize connection to Redis"""
    global redis_client
    if redis_client is None:
        redis_client = from_url(settings.REDIS_URL, decode_responses=True)
    return redis_client

async def close_redis() -> None:
    """Close connection to Redis"""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None

def get_redis_client() -> Redis:
    """Retrieve initialized Redis client"""
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized. Run init_redis() first.")
    return redis_client
