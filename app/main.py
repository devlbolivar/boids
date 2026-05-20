from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.redis import init_redis, close_redis, get_redis_client
from app.dependencies import get_db
from app.workers.celery_app import celery
from app.auth.router import router as auth_router
from app.tenants.router import router as tenants_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Redis
    await init_redis()
    yield
    # Shutdown: Close Redis connection
    await close_redis()

app = FastAPI(
    title="Boids AI API",
    description="Multi-tenant FastAPI backend with Celery background workers and schema-based isolation.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(tenants_router, prefix="/tenants", tags=["Tenants"])

@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """System health check"""
    db_status = "error"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        pass

    redis_status = "error"
    try:
        redis = get_redis_client()
        if await redis.ping():  # type: ignore
            redis_status = "ok"
    except Exception:
        pass

    celery_status = "error"
    try:
        # Check connection to the broker
        with celery.pool.acquire(block=True, timeout=2) as conn:
            conn.ensure_connection()
        celery_status = "ok"
    except Exception:
        pass

    status = "ok" if all(s == "ok" for s in [db_status, redis_status, celery_status]) else "error"

    return {
        "status": status,
        "db": db_status,
        "redis": redis_status,
        "celery": celery_status
    }
