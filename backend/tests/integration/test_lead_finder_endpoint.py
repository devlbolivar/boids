import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy import text

MOCK_APOLLO_RESPONSE = {
    "people": [
        {
            "id": "ap1",
            "name": "Carlos Vega",
            "email": "carlos@startup.cl",
            "title": "CTO",
            "organization": {"name": "Startup Chile"},
        },
        {
            "id": "ap2",
            "name": "Ana Torres",
            "email": "ana@fintech.cl",
            "title": "VP Engineering",
            "organization": {"name": "Fintech SA"},
        },
    ]
}


async def test_find_leads_dispatches_task(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={
        "name": "Find Leads Test",
        "icp_override": {"titles": ["CTO"], "locations": ["Chile"]},
    }, headers=auth_headers)
    assert r.status_code == 201
    campaign_id = r.json()["id"]

    with patch("app.campaigns.router.find_leads_for_campaign") as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-123")

        r = await client.post(
            f"/campaigns/{campaign_id}/run/find-leads",
            headers=auth_headers,
        )

    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "task-123"
    mock_task.delay.assert_called_once()


async def test_campaign_not_found_returns_404(client: AsyncClient, auth_headers):
    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/campaigns/{fake_id}/run/find-leads",
        headers=auth_headers,
    )
    assert r.status_code == 404


async def test_done_campaign_returns_400(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={"name": "Done Camp"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    await client.patch(f"/campaigns/{campaign_id}", json={"status": "done"}, headers=auth_headers)

    with patch("app.campaigns.router.find_leads_for_campaign"):
        r = await client.post(
            f"/campaigns/{campaign_id}/run/find-leads",
            headers=auth_headers,
        )

    assert r.status_code == 400


async def test_find_leads_sets_campaign_status_to_running(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={"name": "Status Test"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    assert r.json()["status"] == "draft"

    with patch("app.campaigns.router.find_leads_for_campaign") as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-abc")
        await client.post(f"/campaigns/{campaign_id}/run/find-leads", headers=auth_headers)

    r = await client.get(f"/campaigns/{campaign_id}", headers=auth_headers)
    assert r.json()["status"] == "running"


async def test_find_leads_end_to_end_with_mock_apollo(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    """
    Ejecuta el pipeline completo (agente + normalizer + service)
    con Apollo y Claude mockeados, usando la DB de test.
    """
    _, session_factory = test_engine

    r = await client.post("/campaigns", json={
        "name": "E2E Test",
        "icp_override": {"titles": ["CTO"], "locations": ["Chile"]},
    }, headers=auth_headers)
    assert r.status_code == 201
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    class _RLSCtx:
        def __init__(self):
            self._s = session_factory()

        async def __aenter__(self):
            s = await self._s.__aenter__()
            await s.execute(text("SET LOCAL ROLE boids_app"))
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
            return s

        async def __aexit__(self, *args):
            return await self._s.__aexit__(*args)

    class RLSSessionFactory:
        def __call__(self):
            return _RLSCtx()

    with patch("app.workers.tasks.lead_finder.AsyncSessionLocal", RLSSessionFactory()), \
         patch(
             "app.integrations.apollo.client.ApolloClient.search_people",
             new_callable=AsyncMock,
             return_value=MOCK_APOLLO_RESPONSE,
         ), \
         patch("app.agents.lead_finder.agent.anthropic.Anthropic") as mock_claude:

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="tool_use", input={"person_titles": ["CTO"], "person_locations": ["Chile"]})
        ]
        mock_claude.return_value.messages.create.return_value = mock_response

        from app.workers.tasks.lead_finder import _find_leads_async
        result = await _find_leads_async(campaign_id, tenant_id)

    assert result["status"] == "ok"
    assert result["created"] == 2
    assert result["skipped_duplicates"] == 0

    r = await client.get(f"/campaigns/{campaign_id}/leads", headers=auth_headers)
    assert r.status_code == 200
    leads = r.json()
    assert len(leads) == 2
    emails = {l["email"] for l in leads}
    assert "carlos@startup.cl" in emails
    assert "ana@fintech.cl" in emails


async def test_find_leads_deduplicates_on_second_run(
    client: AsyncClient,
    auth_headers,
    test_engine,
):
    _, session_factory = test_engine

    r = await client.post("/campaigns", json={"name": "Dedup Run Test"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    tenant_id = r.json()["tenant_id"]

    class _RLSCtx:
        def __init__(self):
            self._s = session_factory()

        async def __aenter__(self):
            s = await self._s.__aenter__()
            await s.execute(text("SET LOCAL ROLE boids_app"))
            await s.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
            return s

        async def __aexit__(self, *args):
            return await self._s.__aexit__(*args)

    class RLSSessionFactory:
        def __call__(self):
            return _RLSCtx()

    with patch("app.workers.tasks.lead_finder.AsyncSessionLocal", RLSSessionFactory()), \
         patch(
             "app.integrations.apollo.client.ApolloClient.search_people",
             new_callable=AsyncMock,
             return_value=MOCK_APOLLO_RESPONSE,
         ), \
         patch("app.agents.lead_finder.agent.anthropic.Anthropic") as mock_claude:

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="tool_use", input={})]
        mock_claude.return_value.messages.create.return_value = mock_response

        from app.workers.tasks.lead_finder import _find_leads_async

        result1 = await _find_leads_async(campaign_id, tenant_id)
        result2 = await _find_leads_async(campaign_id, tenant_id)

    assert result1["created"] == 2
    assert result1["skipped_duplicates"] == 0
    assert result2["created"] == 0
    assert result2["skipped_duplicates"] == 2

    r = await client.get(f"/campaigns/{campaign_id}/leads", headers=auth_headers)
    assert len(r.json()) == 2
