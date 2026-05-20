from httpx import AsyncClient


async def test_create_campaign(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={
        "name": "LATAM SaaS Q3",
        "target_meetings": 15,
        "icp_override": {
            "industries": ["SaaS", "Fintech"],
            "titles": ["CTO", "VP Engineering"],
            "locations": ["Chile", "Colombia"],
        },
    }, headers=auth_headers)

    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "LATAM SaaS Q3"
    assert data["status"] == "draft"
    assert data["target_meetings"] == 15
    assert data["leads_count"] == 0


async def test_list_campaigns_returns_only_own(client: AsyncClient, auth_headers, second_auth_headers):
    await client.post("/campaigns", json={"name": "Campaign A"}, headers=auth_headers)
    await client.post("/campaigns", json={"name": "Campaign B"}, headers=second_auth_headers)

    r = await client.get("/campaigns", headers=auth_headers)
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "Campaign A" in names
    assert "Campaign B" not in names


async def test_get_campaign_of_other_tenant_returns_404(
    client: AsyncClient, auth_headers, second_auth_headers
):
    r = await client.post("/campaigns", json={"name": "Private"}, headers=second_auth_headers)
    campaign_id = r.json()["id"]

    r = await client.get(f"/campaigns/{campaign_id}", headers=auth_headers)
    assert r.status_code == 404


async def test_update_campaign_status(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={"name": "Updatable"}, headers=auth_headers)
    campaign_id = r.json()["id"]

    r = await client.patch(
        f"/campaigns/{campaign_id}",
        json={"status": "running"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "running"


async def test_delete_campaign(client: AsyncClient, auth_headers):
    r = await client.post("/campaigns", json={"name": "Deletable"}, headers=auth_headers)
    campaign_id = r.json()["id"]

    r = await client.delete(f"/campaigns/{campaign_id}", headers=auth_headers)
    assert r.status_code == 204

    r = await client.get(f"/campaigns/{campaign_id}", headers=auth_headers)
    assert r.status_code == 404
