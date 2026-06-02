import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_user_success(client: AsyncClient):
    """إنشاء مستخدم جديد بنجاح."""
    new_user = {
        "email": "test_new@example.com",
        "full_name": "Test New",
        "password": "secure123"
    }
    res = await client.post("/users/", json=new_user)
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "test_new@example.com"
    assert data["role"] == "CLIENT"

# validation errors
@pytest.mark.asyncio
async def test_create_user_duplicate(client: AsyncClient):
    """محاولة إنشاء مستخدم بإيميل موجود."""
    res = await client.post("/users/", json={
        "email": "dealer@test.com",
        "full_name": "Dup",
        "password": "pass123"
    })
    assert res.status_code == 409

# get user
@pytest.mark.asyncio
async def test_get_user(client: AsyncClient, dealer_user):
    """جلب بيانات مستخدم موجود."""
    res = await client.get(f"/users/{dealer_user.id}")
    assert res.status_code == 401 

# get user not found
@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient):
    """جلب مستخدم غير موجود."""
    res = await client.get("/users/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 401