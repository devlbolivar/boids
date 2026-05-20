"""delivery and meetings

Revision ID: 005_delivery_and_meetings
Revises: 004_outreach_emails
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op


revision: str = "005_delivery_and_meetings"
down_revision: Union[str, None] = "004_outreach_emails"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Actualizar el CHECK de leads.status para incluir 'sent'
    op.execute("ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_status_check;")
    op.execute("""
    ALTER TABLE leads ADD CONSTRAINT leads_status_check
        CHECK (status IN (
            'new','researched','emailed','sent',
            'replied','meeting','rejected','needs_review'
        ));
    """)

    # 2. Agregar campos de tracking a outreach_emails
    op.execute("""
    ALTER TABLE outreach_emails
        ADD COLUMN instantly_id  TEXT,
        ADD COLUMN sent_at       TIMESTAMPTZ,
        ADD COLUMN opened_at     TIMESTAMPTZ,
        ADD COLUMN replied_at    TIMESTAMPTZ,
        ADD COLUMN reply_body    TEXT;
    """)

    op.execute("""
    CREATE INDEX idx_outreach_instantly ON outreach_emails(instantly_id)
        WHERE instantly_id IS NOT NULL;
    """)

    # 3. Tabla de meetings
    op.execute("""
    CREATE TABLE meetings (
        id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        lead_id            UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
        outreach_email_id  UUID REFERENCES outreach_emails(id),
        scheduled_at       TIMESTAMPTZ,
        calendar_event_id  TEXT,
        meet_link          TEXT,
        status             TEXT NOT NULL DEFAULT 'scheduled'
                               CHECK (status IN ('scheduled','completed','cancelled')),
        created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("CREATE INDEX idx_meetings_tenant  ON meetings(tenant_id);")
    op.execute("CREATE INDEX idx_meetings_lead    ON meetings(lead_id);")
    op.execute("CREATE INDEX idx_meetings_status  ON meetings(tenant_id, status);")

    op.execute("ALTER TABLE meetings ENABLE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY meetings_isolation ON meetings
        USING (tenant_id = current_setting('app.tenant_id')::UUID);
    """)

    op.execute("""
    CREATE TRIGGER meetings_updated_at
        BEFORE UPDATE ON meetings
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS meetings_updated_at ON meetings;")
    op.execute("DROP POLICY IF EXISTS meetings_isolation ON meetings;")
    op.execute("DROP TABLE IF EXISTS meetings;")
    op.execute("DROP INDEX IF EXISTS idx_outreach_instantly;")
    op.execute("""
    ALTER TABLE outreach_emails
        DROP COLUMN IF EXISTS instantly_id,
        DROP COLUMN IF EXISTS sent_at,
        DROP COLUMN IF EXISTS opened_at,
        DROP COLUMN IF EXISTS replied_at,
        DROP COLUMN IF EXISTS reply_body;
    """)
    op.execute("ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_status_check;")
    op.execute("""
    ALTER TABLE leads ADD CONSTRAINT leads_status_check
        CHECK (status IN (
            'new','researched','emailed',
            'replied','meeting','rejected','needs_review'
        ));
    """)
