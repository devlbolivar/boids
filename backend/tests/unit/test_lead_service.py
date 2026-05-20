import pytest
from unittest.mock import AsyncMock, MagicMock
from app.leads.service import LeadService
from app.leads.models import Lead
from app.leads.schemas import LeadCreate
import uuid


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


async def test_create_lead_deduplicates_by_email(mock_db):
    service = LeadService()
    tenant_id = str(uuid.uuid4())
    campaign_id = str(uuid.uuid4())

    existing_lead = Lead(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        email="user@company.com",
        full_name="",
        company="",
        title="",
        research_ctx={},
        status="new",
    )

    mock_db.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=existing_lead)
        )
    )

    data = LeadCreate(email="user@company.com", full_name="John Doe")
    result = await service.create(mock_db, tenant_id, campaign_id, data)

    mock_db.add.assert_not_called()
    assert result.id == existing_lead.id


async def test_create_lead_adds_new_when_no_duplicate(mock_db):
    service = LeadService()
    tenant_id = str(uuid.uuid4())
    campaign_id = str(uuid.uuid4())

    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    data = LeadCreate(email="new@company.com")
    lead = await service.create(mock_db, tenant_id, campaign_id, data)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    assert lead.email == "new@company.com"
    assert lead.tenant_id == tenant_id
