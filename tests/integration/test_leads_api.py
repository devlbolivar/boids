from httpx import AsyncClient


async def _create_campaign(client: AsyncClient, headers: dict, name: str = "Test Campaign") -> str:
    r = await client.post("/campaigns", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


async def test_add_lead_to_campaign(client: AsyncClient, auth_headers):
    campaign_id = await _create_campaign(client, auth_headers)

    r = await client.post(
        f"/campaigns/{campaign_id}/leads",
        json={
            "email": "cto@startup.cl",
            "full_name": "Carlos Vega",
            "company": "Startup Chile",
            "title": "CTO",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "cto@startup.cl"
    assert data["status"] == "new"


async def test_add_duplicate_lead_returns_existing(client: AsyncClient, auth_headers):
    campaign_id = await _create_campaign(client, auth_headers, "Dedup Test")
    payload = {"email": "dup@test.com", "full_name": "Dup User"}

    r1 = await client.post(f"/campaigns/{campaign_id}/leads", json=payload, headers=auth_headers)
    r2 = await client.post(f"/campaigns/{campaign_id}/leads", json=payload, headers=auth_headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


async def test_list_leads_filters_by_status(client: AsyncClient, auth_headers):
    campaign_id = await _create_campaign(client, auth_headers, "Filter Test")
    emails = ["a@test.com", "b@test.com", "c@test.com"]
    for email in emails:
        await client.post(
            f"/campaigns/{campaign_id}/leads",
            json={"email": email},
            headers=auth_headers,
        )

    r = await client.get(f"/campaigns/{campaign_id}/leads?status=new", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 3


async def test_campaign_leads_count_updates(client: AsyncClient, auth_headers):
    campaign_id = await _create_campaign(client, auth_headers, "Count Test")

    r = await client.get(f"/campaigns/{campaign_id}", headers=auth_headers)
    assert r.json()["leads_count"] == 0

    await client.post(
        f"/campaigns/{campaign_id}/leads",
        json={"email": "lead@test.com"},
        headers=auth_headers,
    )

    r = await client.get(f"/campaigns/{campaign_id}", headers=auth_headers)
    assert r.json()["leads_count"] == 1
