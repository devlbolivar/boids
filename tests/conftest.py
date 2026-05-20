import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from fastapi import Depends
from app.config import settings
from app.core.database import Base
from app.dependencies import get_db, get_tenant_db, get_current_tenant
from app.main import app

TEST_DATABASE_URL = settings.DATABASE_URL.replace("boids_db", "boids_test_db")


@pytest_asyncio.fixture
async def test_engine():
    # statement_cache_size=0 disables asyncpg's client-side prepared statement
    # cache. Without this, PostgreSQL uses a generic cached plan and evaluates
    # current_setting('app.tenant_id') at plan time, bypassing SET LOCAL changes
    # made between queries — which breaks RLS policy enforcement in tests.
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE agent_runs FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("""
            CREATE POLICY agent_runs_tenant_isolation ON agent_runs
                USING (tenant_id = current_setting('app.tenant_id')::UUID)
        """))

    yield engine, session_factory

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Session for direct DB queries in tests (separate from client session)."""
    _, session_factory = test_engine
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    """HTTP client with both get_db and get_tenant_db overridden to use the test DB."""
    _, session_factory = test_engine

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    async def _override_get_tenant_db(tenant_id: str = Depends(get_current_tenant)):
        async with session_factory() as session:
            # SET LOCAL doesn't support bind params in PostgreSQL
            await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_tenant_db] = _override_get_tenant_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
