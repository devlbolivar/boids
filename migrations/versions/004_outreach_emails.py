"""outreach emails

Revision ID: 004_outreach_emails
Revises: 003_knowledge_documents
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op


revision: str = "004_outreach_emails"
down_revision: Union[str, None] = "003_knowledge_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE outreach_emails (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        lead_id       UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
        subject       TEXT NOT NULL,
        body          TEXT NOT NULL,
        quality_score FLOAT NOT NULL,
        qa_details    JSONB NOT NULL DEFAULT '{}',
        attempt       INTEGER NOT NULL DEFAULT 1,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("CREATE INDEX idx_outreach_tenant ON outreach_emails(tenant_id);")
    op.execute("CREATE INDEX idx_outreach_lead   ON outreach_emails(lead_id);")

    op.execute("ALTER TABLE outreach_emails ENABLE ROW LEVEL SECURITY;")

    op.execute("""
    CREATE POLICY outreach_isolation ON outreach_emails
        USING (tenant_id = current_setting('app.tenant_id')::UUID);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS outreach_isolation ON outreach_emails;")
    op.execute("DROP TABLE IF EXISTS outreach_emails;")
