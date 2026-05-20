import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.knowledge.retrieval import build_rag_context
from app.leads.models import Lead


def make_lead(**kwargs):
    lead = Lead()
    lead.id = str(uuid.uuid4())
    lead.tenant_id = str(uuid.uuid4())
    lead.title = kwargs.get("title", "CTO")
    lead.company = kwargs.get("company", "Startup")
    lead.research_ctx = kwargs.get("research_ctx", {})
    return lead


@pytest.mark.asyncio
async def test_build_rag_context_formats_chunks():
    lead = make_lead(title="CTO", company="SaaS Chile")

    mock_chunks = [
        {
            "text": "Ayudamos a Fintual a reducir su ciclo de ventas",
            "doc_type": "case_study",
            "title": "Caso Fintual",
            "doc_id": "abc",
            "score": 0.89,
        }
    ]

    with patch(
        "app.knowledge.retrieval._svc.retrieve_context",
        new_callable=AsyncMock,
        return_value=mock_chunks,
    ):
        result = await build_rag_context(str(lead.tenant_id), lead)

    assert "CASE_STUDY" in result
    assert "Caso Fintual" in result
    assert "Fintual" in result


@pytest.mark.asyncio
async def test_build_rag_context_returns_empty_when_no_chunks():
    lead = make_lead()

    with patch(
        "app.knowledge.retrieval._svc.retrieve_context",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await build_rag_context(str(lead.tenant_id), lead)

    assert result == ""
