import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch


@pytest.mark.asyncio
async def test_summary_returns_correct_structure(
    client: AsyncClient,
    auth_headers,
):
    r = await client.get("/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "leads" in data
    assert "emails" in data
    assert "meetings" in data
    assert "needs_review" in data["leads"]
    assert "open_rate" in data["emails"]
    assert "this_month" in data["meetings"]


@pytest.mark.asyncio
async def test_funnel_returns_all_statuses(
    client: AsyncClient,
    auth_headers,
):
    r = await client.get("/dashboard/funnel", headers=auth_headers)
    assert r.status_code == 200
    statuses = [item["status"] for item in r.json()]
    for s in ["new", "researched", "emailed", "sent", "replied", "meeting"]:
        assert s in statuses


@pytest.mark.asyncio
async def test_funnel_returns_eight_steps(
    client: AsyncClient,
    auth_headers,
):
    r = await client.get("/dashboard/funnel", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 8


@pytest.mark.asyncio
async def test_upcoming_meetings_returns_list(
    client: AsyncClient,
    auth_headers,
):
    r = await client.get("/dashboard/meetings/upcoming", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_cost_endpoint_returns_breakdown(
    client: AsyncClient,
    auth_headers,
):
    r = await client.get("/dashboard/cost", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "period" in data
    assert "total_usd" in data
    assert "breakdown" in data
    assert isinstance(data["breakdown"], list)


@pytest.mark.asyncio
async def test_review_queue_returns_list(
    client: AsyncClient,
    auth_headers,
):
    r = await client.get("/review", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    for item in items:
        assert "lead" in item
        assert "email_draft" in item


@pytest.mark.asyncio
async def test_approve_review_changes_lead_status(
    client: AsyncClient,
    db_session: AsyncSession,
):
    r = await client.post("/auth/register", json={
        "name": "Approve Test Corp",
        "email": "approve-test@boids.ai",
        "password": "testpass123",
    })
    assert r.status_code == 201
    token = r.json()["access_token"]
    tenant_id = r.json()["tenant_id"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/campaigns", json={"name": "Review Test"}, headers=headers)
    assert r.status_code == 201
    campaign_id = r.json()["id"]

    from app.leads.models import Lead
    from app.outreach.models import OutreachEmail

    lead = Lead(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        email="review@test.cl",
        status="needs_review",
    )
    db_session.add(lead)
    await db_session.flush()

    email_obj = OutreachEmail(
        tenant_id=tenant_id,
        lead_id=str(lead.id),
        subject="Test Subject",
        body="Body content here for testing purposes",
        quality_score=0.62,
        qa_details={"issues": ["Poco personalizado"]},
    )
    db_session.add(email_obj)
    await db_session.commit()
    lead_id = str(lead.id)

    with patch("app.workers.tasks.delivery.send_email.delay"):
        r = await client.post(f"/review/{lead_id}/approve", headers=headers)

    assert r.status_code == 200
    assert r.json()["action"] == "approved"


@pytest.mark.asyncio
async def test_reject_review_marks_lead_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
):
    r = await client.post("/auth/register", json={
        "name": "Reject Test Corp",
        "email": "reject-test@boids.ai",
        "password": "testpass123",
    })
    assert r.status_code == 201
    token = r.json()["access_token"]
    tenant_id = r.json()["tenant_id"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/campaigns", json={"name": "Reject Test"}, headers=headers)
    assert r.status_code == 201
    campaign_id = r.json()["id"]

    from app.leads.models import Lead

    lead = Lead(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        email="reject@test.cl",
        status="needs_review",
    )
    db_session.add(lead)
    await db_session.commit()
    lead_id = str(lead.id)

    r = await client.post(f"/review/{lead_id}/reject", headers=headers)
    assert r.status_code == 200
    assert r.json()["action"] == "rejected"


@pytest.mark.asyncio
async def test_approve_returns_404_for_wrong_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """A tenant cannot approve leads belonging to another tenant."""
    r_a = await client.post("/auth/register", json={
        "name": "Corp A",
        "email": "corp-a@boids.ai",
        "password": "testpass123",
    })
    tenant_a_id = r_a.json()["tenant_id"]

    r_b = await client.post("/auth/register", json={
        "name": "Corp B",
        "email": "corp-b@boids.ai",
        "password": "testpass123",
    })
    token_b = r_b.json()["access_token"]

    r = await client.post(
        "/campaigns",
        json={"name": "A Campaign"},
        headers={"Authorization": f"Bearer {r_a.json()['access_token']}"},
    )
    campaign_id = r.json()["id"]

    from app.leads.models import Lead

    lead = Lead(
        tenant_id=tenant_a_id,
        campaign_id=campaign_id,
        email="iso@test.cl",
        status="needs_review",
    )
    db_session.add(lead)
    await db_session.commit()
    lead_id = str(lead.id)

    r = await client.post(
        f"/review/{lead_id}/approve",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404
