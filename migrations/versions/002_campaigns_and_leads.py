"""campaigns and leads

Revision ID: 002_campaigns_and_leads
Revises: 001_initial_schema
Create Date: 2026-05-19 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op


revision: str = '002_campaigns_and_leads'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE campaigns (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        name            TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft','running','paused','done')),
        icp_override    JSONB NOT NULL DEFAULT '{}',
        target_meetings INTEGER NOT NULL DEFAULT 10,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("""
    CREATE TABLE leads (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
        email           TEXT NOT NULL,
        full_name       TEXT NOT NULL DEFAULT '',
        company         TEXT NOT NULL DEFAULT '',
        title           TEXT NOT NULL DEFAULT '',
        research_ctx    JSONB NOT NULL DEFAULT '{}',
        status          TEXT NOT NULL DEFAULT 'new'
                            CHECK (status IN (
                                'new','researched','emailed',
                                'replied','meeting','rejected','needs_review'
                            )),
        apollo_id       TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("CREATE UNIQUE INDEX idx_leads_tenant_email ON leads(tenant_id, email);")
    op.execute("CREATE INDEX idx_leads_campaign ON leads(campaign_id);")
    op.execute("CREATE INDEX idx_leads_status ON leads(tenant_id, status);")
    op.execute("CREATE INDEX idx_campaigns_tenant ON campaigns(tenant_id);")

    op.execute("ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE leads ENABLE ROW LEVEL SECURITY;")

    op.execute("""
    CREATE POLICY campaigns_isolation ON campaigns
        USING (tenant_id = current_setting('app.tenant_id')::UUID);
    """)

    op.execute("""
    CREATE POLICY leads_isolation ON leads
        USING (tenant_id = current_setting('app.tenant_id')::UUID);
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION set_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE TRIGGER campaigns_updated_at
        BEFORE UPDATE ON campaigns
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    op.execute("""
    CREATE TRIGGER leads_updated_at
        BEFORE UPDATE ON leads
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS leads_updated_at ON leads;")
    op.execute("DROP TRIGGER IF EXISTS campaigns_updated_at ON campaigns;")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at;")
    op.execute("DROP POLICY IF EXISTS leads_isolation ON leads;")
    op.execute("DROP POLICY IF EXISTS campaigns_isolation ON campaigns;")
    op.execute("DROP TABLE IF EXISTS leads;")
    op.execute("DROP TABLE IF EXISTS campaigns;")
