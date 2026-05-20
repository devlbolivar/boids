import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.leads.models import Lead


def make_lead(**kwargs) -> Lead:
    defaults = {
        "id": str(uuid.uuid4()),
        "tenant_id": str(uuid.uuid4()),
        "campaign_id": str(uuid.uuid4()),
        "email": "cto@startup.cl",
        "full_name": "Carlos Vega",
        "company": "Startup Chile",
        "title": "CTO",
        "status": "new",
        "research_ctx": {},
    }
    defaults.update(kwargs)
    lead = Lead()
    for k, v in defaults.items():
        setattr(lead, k, v)
    return lead


@pytest.mark.asyncio
async def test_research_lead_skips_non_new_status():
    """Un lead que ya fue procesado no debe procesarse de nuevo."""
    from app.workers.tasks.research import _research_lead_async

    lead = make_lead(status="researched")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_svc = AsyncMock()
    mock_svc.get = AsyncMock(return_value=lead)

    with patch("app.workers.tasks.research.AsyncSessionLocal", return_value=mock_session), \
         patch("app.workers.tasks.research.LeadService", return_value=mock_svc):

        result = await _research_lead_async(str(lead.id), str(lead.tenant_id))

    assert result["status"] == "skipped"
    assert result["reason"] == "already_processed"


@pytest.mark.asyncio
async def test_research_lead_skips_not_found():
    """Un lead que no existe retorna skipped/not_found."""
    from app.workers.tasks.research import _research_lead_async

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_svc = AsyncMock()
    mock_svc.get = AsyncMock(return_value=None)

    with patch("app.workers.tasks.research.AsyncSessionLocal", return_value=mock_session), \
         patch("app.workers.tasks.research.LeadService", return_value=mock_svc):

        result = await _research_lead_async(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "skipped"
    assert result["reason"] == "not_found"
