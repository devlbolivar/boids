import pytest
from unittest.mock import AsyncMock, MagicMock
from app.campaigns.service import CampaignService
from app.campaigns.schemas import CampaignCreate, CampaignUpdate
from app.campaigns.models import Campaign
import uuid


@pytest.fixture
def service():
    return CampaignService()


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


async def test_create_campaign_sets_tenant_id(service, mock_db):
    tenant_id = str(uuid.uuid4())
    data = CampaignCreate(name="Q2 Outbound", target_meetings=20)

    campaign_id = str(uuid.uuid4())
    async def fake_refresh(obj):
        obj.id = campaign_id

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    campaign = await service.create(mock_db, tenant_id, data)

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    assert campaign.tenant_id == tenant_id
    assert campaign.name == "Q2 Outbound"
    assert campaign.target_meetings == 20


async def test_update_campaign_only_changes_provided_fields(service, mock_db):
    existing = Campaign(
        id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        name="Old Name",
        status="draft",
        target_meetings=10,
        icp_override={},
    )

    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
    )

    updated = await service.update(mock_db, existing.id, CampaignUpdate(name="New Name"))

    assert updated.name == "New Name"
    assert updated.status == "draft"
    assert updated.target_meetings == 10


async def test_delete_returns_false_when_not_found(service, mock_db):
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    result = await service.delete(mock_db, str(uuid.uuid4()))
    assert result is False
