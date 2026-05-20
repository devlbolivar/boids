"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-05-19 18:22:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.execute("""
    CREATE TABLE tenants (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name            TEXT NOT NULL,
        email           TEXT UNIQUE NOT NULL,
        password_hash   TEXT NOT NULL,
        plan            TEXT NOT NULL DEFAULT 'starter'
                            CHECK (plan IN ('starter', 'growth', 'agency')),
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        icp_config      JSONB NOT NULL DEFAULT '{}',
        api_keys_enc    JSONB NOT NULL DEFAULT '{}',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("""
    CREATE TABLE agent_runs (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        agent_type      TEXT NOT NULL,
        lead_id         UUID,
        input_tokens    INTEGER,
        output_tokens   INTEGER,
        cache_read_tokens INTEGER,
        latency_ms      INTEGER,
        status          TEXT NOT NULL DEFAULT 'ok'
                            CHECK (status IN ('ok', 'error', 'retry')),
        error_msg       TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("CREATE INDEX idx_agent_runs_tenant ON agent_runs(tenant_id);")
    op.execute("CREATE INDEX idx_agent_runs_created ON agent_runs(created_at DESC);")
    op.execute("ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE agent_runs FORCE ROW LEVEL SECURITY;")

    op.execute("""
    CREATE POLICY agent_runs_tenant_isolation ON agent_runs
        USING (tenant_id = current_setting('app.tenant_id')::UUID);
    """)

def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS agent_runs_tenant_isolation ON agent_runs;")
    op.execute("DROP TABLE IF EXISTS agent_runs;")
    op.execute("DROP TABLE IF EXISTS tenants;")
