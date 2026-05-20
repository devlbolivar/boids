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
from app.outreach.models import OutreachEmail  # noqa: F401 — registers table in Base.metadata
from app.meetings.models import Meeting  # noqa: F401 — registers table in Base.metadata

TEST_DATABASE_URL = settings.DATABASE_URL.replace("boids_db", "boids_test_db").replace(":5432/", ":5433/")


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
        await conn.execute(text("ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE campaigns FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("""
            CREATE POLICY campaigns_isolation ON campaigns
                USING (tenant_id = current_setting('app.tenant_id')::UUID)
        """))
        await conn.execute(text("ALTER TABLE leads ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE leads FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("""
            CREATE POLICY leads_isolation ON leads
                USING (tenant_id = current_setting('app.tenant_id')::UUID)
        """))
        # Superusers bypass RLS unconditionally. Create a non-superuser role so
        # tenant-scoped sessions can enforce policies during tests.
        await conn.execute(text("DO $$ BEGIN CREATE ROLE boids_app; EXCEPTION WHEN duplicate_object THEN NULL; END $$"))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON tenants TO boids_app"))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runs TO boids_app"))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON campaigns TO boids_app"))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON leads TO boids_app"))
        await conn.execute(text("ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE knowledge_documents FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("""
            CREATE POLICY knowledge_isolation ON knowledge_documents
                USING (tenant_id = current_setting('app.tenant_id')::UUID)
        """))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_documents TO boids_app"))
        await conn.execute(text("ALTER TABLE outreach_emails ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE outreach_emails FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("""
            CREATE POLICY outreach_isolation ON outreach_emails
                USING (tenant_id = current_setting('app.tenant_id')::UUID)
        """))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON outreach_emails TO boids_app"))
        await conn.execute(text("ALTER TABLE meetings ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE meetings FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("""
            CREATE POLICY meetings_isolation ON meetings
                USING (tenant_id = current_setting('app.tenant_id')::UUID)
        """))
        await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON meetings TO boids_app"))

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
            # Use non-superuser role so RLS policies are enforced (superusers bypass RLS).
            await session.execute(text("SET LOCAL ROLE boids_app"))
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


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    """Registers a tenant and returns its auth headers."""
    r = await client.post("/auth/register", json={
        "name": "Test Corp",
        "email": "test@boids.ai",
        "password": "testpass123",
    })
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_auth_headers(client: AsyncClient):
    """Registers a second tenant for isolation tests."""
    r = await client.post("/auth/register", json={
        "name": "Other Corp",
        "email": "other@boids.ai",
        "password": "testpass123",
    })
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
