import pytest
from httpx import AsyncClient
from app.models import User

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, dealer_headers):
    res = await client.post("/auth/login", json={
        "email": "dealer@test.com",
        "password": "dealer123"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid(client: AsyncClient):
    res = await client.post("/auth/login", json={
        "email": "dealer@test.com",
        "password": "wrongpass"
    })
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db_session, base_data):
    user = await db_session.get(User, base_data["client_id"])
    user.is_active = False
    await db_session.flush()

    res = await client.post("/auth/login", json={
        "email": "client@test.com",
        "password": "client123"
    })
    assert res.status_code == 401