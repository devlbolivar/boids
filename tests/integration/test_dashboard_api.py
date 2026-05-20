from httpx import AsyncClient


async def test_dashboard_summary(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={"name": "Active"}, headers=auth_headers)
    campaign_id = r.json()["id"]
    await client.patch(
        f"/campaigns/{campaign_id}",
        json={"status": "running"},
        headers=auth_headers,
    )

    r = await client.get("/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["active_campaigns"] >= 1
    assert "leads" in data
    assert "total" in data["leads"]


async def test_dashboard_summary_isolates_by_tenant(
    client: AsyncClient, auth_headers, second_auth_headers
):
    r = await client.post("/campaigns", json={"name": "Tenant A Active"}, headers=auth_headers)
    await client.patch(
        f"/campaigns/{r.json()['id']}",
        json={"status": "running"},
        headers=auth_headers,
    )

    r_b = await client.get("/dashboard/summary", headers=second_auth_headers)
    assert r_b.status_code == 200
    assert r_b.json()["active_campaigns"] == 0


async def test_dashboard_leads_structure(client: AsyncClient, auth_headers):
    r = await client.get("/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    leads = r.json()["leads"]
    for key in ["total", "new", "researched", "emailed", "replied", "meeting", "rejected", "needs_review"]:
        assert key in leads
