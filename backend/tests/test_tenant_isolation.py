import asyncpg
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.config import settings

TEST_PG_DSN = (
    settings.DATABASE_URL
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("boids_db", "boids_test_db")
    .replace(":5432/", ":5433/")
)


@pytest.mark.asyncio
async def test_tenant_isolation_boundaries(client: AsyncClient, db_session: AsyncSession):
    # Register Tenant A
    res_a = await client.post("/auth/register", json={
        "name": "Acme Corp",
        "email": "admin@acme.com",
        "password": "acmePassword123",
    })
    assert res_a.status_code == 201
    tenant_a_id = res_a.json()["tenant_id"]
    token_a = res_a.json()["access_token"]

    # Register Tenant B
    res_b = await client.post("/auth/register", json={
        "name": "Beta Corp",
        "email": "admin@beta.com",
        "password": "betaPassword123",
    })
    assert res_b.status_code == 201
    tenant_b_id = res_b.json()["tenant_id"]
    token_b = res_b.json()["access_token"]

    # Each tenant sees their own profile
    profile_a = await client.get("/tenants/me", headers={"Authorization": f"Bearer {token_a}"})
    assert profile_a.status_code == 200
    assert profile_a.json()["name"] == "Acme Corp"
    assert profile_a.json()["id"] == tenant_a_id

    profile_b = await client.get("/tenants/me", headers={"Authorization": f"Bearer {token_b}"})
    assert profile_b.status_code == 200
    assert profile_b.json()["name"] == "Beta Corp"
    assert profile_b.json()["id"] == tenant_b_id

    # RLS isolation: PostgreSQL superusers bypass RLS unconditionally. To test the
    # policy, we create a transient non-superuser role, grant it table access, and
    # use SET LOCAL ROLE within a single transaction. RLS then applies normally.
    pg_conn = await asyncpg.connect(TEST_PG_DSN)
    try:
        # Create a transient non-superuser role for RLS testing (idempotent).
        await pg_conn.execute("DO $$ BEGIN CREATE ROLE boids_app; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
        await pg_conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON agent_runs TO boids_app")

        async with pg_conn.transaction():
            # Switch to non-superuser role so RLS policies are enforced.
            await pg_conn.execute("SET LOCAL ROLE boids_app")
            await pg_conn.execute(f"SET LOCAL app.tenant_id = '{tenant_b_id}'")
            await pg_conn.execute(
                f"INSERT INTO agent_runs (tenant_id, agent_type, status) "
                f"VALUES ('{tenant_b_id}', 'test_agent', 'ok')"
            )

            # Tenant A must not see tenant B's row
            await pg_conn.execute(f"SET LOCAL app.tenant_id = '{tenant_a_id}'")
            count_for_a = await pg_conn.fetchval("SELECT COUNT(*) FROM agent_runs")
            assert count_for_a == 0, "Tenant A must not see tenant B's agent_runs"

            # Tenant B must see its own row
            await pg_conn.execute(f"SET LOCAL app.tenant_id = '{tenant_b_id}'")
            count_for_b = await pg_conn.fetchval("SELECT COUNT(*) FROM agent_runs")
            assert count_for_b == 1
    finally:
        await pg_conn.close()
