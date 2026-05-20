from httpx import AsyncClient


async def test_dashboard_summary(client: AsyncClient, auth_headers):
    r = await client.get("/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "leads" in data
    assert "emails" in data
    assert "meetings" in data
    assert "total" in data["leads"]


async def test_dashboard_summary_isolates_by_tenant(
    client: AsyncClient, auth_headers, second_auth_headers
):
    r_b = await client.get("/dashboard/summary", headers=second_auth_headers)
    assert r_b.status_code == 200
    assert r_b.json()["leads"]["total"] == 0


async def test_dashboard_leads_structure(client: AsyncClient, auth_headers):
    r = await client.get("/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    leads = r.json()["leads"]
    assert "total" in leads
    assert "needs_review" in leads
    assert "by_status" in leads
