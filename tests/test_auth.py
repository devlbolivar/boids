import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_tenant_and_login(client: AsyncClient):
    # Register a new tenant
    response = await client.post("/auth/register", json={
        "name": "Acme Corp",
        "email": "admin@example.com",
        "password": "securepassword123",
    })
    assert response.status_code == 201
    data = response.json()
    assert "tenant_id" in data
    assert "access_token" in data

    # Login with correct credentials
    login_response = await client.post(
        "/auth/token",
        data={"username": "admin@example.com", "password": "securepassword123"},
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Fetch tenant profile with the token
    me_response = await client.get(
        "/tenants/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert me_response.status_code == 200
    profile = me_response.json()
    assert profile["email"] == "admin@example.com"
    assert profile["name"] == "Acme Corp"
    assert profile["is_active"] is True

    # Wrong password should fail
    fail_response = await client.post(
        "/auth/token",
        data={"username": "admin@example.com", "password": "wrongpassword"},
    )
    assert fail_response.status_code == 401
