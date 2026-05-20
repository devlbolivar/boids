"""knowledge documents

Revision ID: 003_knowledge_documents
Revises: 002_campaigns_and_leads
Create Date: 2026-05-19 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op


revision: str = "003_knowledge_documents"
down_revision: Union[str, None] = "002_campaigns_and_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE knowledge_documents (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        title       TEXT NOT NULL,
        doc_type    TEXT NOT NULL
                        CHECK (doc_type IN (
                            'value_prop','case_study','objections',
                            'pain_points','email_examples','other'
                        )),
        content     TEXT NOT NULL,
        chunk_count INTEGER NOT NULL DEFAULT 0,
        status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','indexed','failed')),
        error_msg   TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("CREATE INDEX idx_knowledge_tenant ON knowledge_documents(tenant_id);")
    op.execute("CREATE INDEX idx_knowledge_status ON knowledge_documents(tenant_id, status);")

    op.execute("ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;")

    op.execute("""
    CREATE POLICY knowledge_isolation ON knowledge_documents
        USING (tenant_id = current_setting('app.tenant_id')::UUID);
    """)

    op.execute("""
    CREATE TRIGGER knowledge_updated_at
        BEFORE UPDATE ON knowledge_documents
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_updated_at ON knowledge_documents;")
    op.execute("DROP POLICY IF EXISTS knowledge_isolation ON knowledge_documents;")
    op.execute("DROP TABLE IF EXISTS knowledge_documents;")
