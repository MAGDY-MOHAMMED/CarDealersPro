import pytest
from httpx import AsyncClient
from app.models import User

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, dealer_headers):
    """تسجيل الدخول بنجاح (التوكن موجود مسبقاً)."""
    # بما إننا بنستخدم shared_tokens، فمجرد وجود dealer_headers يعني النجاح.
    # لكن ممكن نختبر الـ login endpoint مباشرة للتأكد.
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
    """تسجيل دخول بكلمة مرور خاطئة."""
    res = await client.post("/auth/login", json={
        "email": "dealer@test.com",
        "password": "wrongpass"
    })
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db_module_session, base_data):
    """محاولة تسجيل دخول مستخدم غير نشط."""
    user = await db_module_session.get(User, base_data["client_id"])
    user.is_active = False
    await db_module_session.flush()

    res = await client.post("/auth/login", json={
        "email": "client@test.com",
        "password": "client123"
    })
    assert res.status_code == 401

    # رجوع الحالة النشطة (بيتراجع تلقائي في نهاية الاختبار بسبب الـ savepoint)
    user.is_active = True
    await db_module_session.flush()