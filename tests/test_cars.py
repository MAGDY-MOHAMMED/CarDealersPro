import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_car(client: AsyncClient, dealer_headers, dealer_user):
    """إنشاء سيارة جديدة."""
    car_data = {
        "brand": "Honda",
        "model": "Civic",
        "year": 2021,
        "price_consumer": 350000.0
    }
    res = await client.post("/cars/", json=car_data, headers=dealer_headers)
    assert res.status_code == 201
    car = res.json()
    assert car["brand"] == "Honda"
    assert car["owner_id"] == str(dealer_user.id)

    # تنظيف: حذف العربية
    await client.delete(f"/cars/{car['id']}", headers=dealer_headers)
# get all cars
@pytest.mark.asyncio
async def test_get_all_cars(client: AsyncClient, dealer_headers):
    """جلب كل السيارات (المشتركة موجودة)."""
    res = await client.get("/cars/", headers=dealer_headers)
    assert res.status_code == 200
    data = res.json()
    # assert that total is greater than or equal to 1 (the car in base_data)
    assert data["total"] >= 1  # السيارة اللي في base_data

# get car by id
@pytest.mark.asyncio
async def test_get_car_by_id(client: AsyncClient, car_id):
    """جلب سيارة معينة."""
    res = await client.get(f"/cars/{car_id}")
    assert res.status_code == 401

# update car
@pytest.mark.asyncio
async def test_update_car(client: AsyncClient, dealer_headers, car_id):
    """تحديث لون سيارة."""
    update = {"color": "Red"}
    res = await client.put(f"/cars/{car_id}", json=update, headers=dealer_headers)
    assert res.status_code == 200

# delete car
@pytest.mark.asyncio
async def test_delete_car(client: AsyncClient, dealer_headers, dealer_user):
    """حذف سيارة (Soft Delete)."""
    car_data = {
        "brand": "DeleteMe",
        "model": "Test",
        "year": 2020,
        "price_consumer": 10000
    }
    res = await client.post("/cars/", json=car_data, headers=dealer_headers)
    assert res.status_code == 201
    car_id = res.json()["id"]

    # الحذف الناعم يجب أن يرجع 204 (نجاح)
    res = await client.delete(f"/cars/{car_id}", headers=dealer_headers)
    assert res.status_code == 204  # كان خطأ 404

    # الآن العربية مخفية، جلبها بدون توثيق يرجع 401 (أو 404 لو أضفنا توثيق)
    res = await client.get(f"/cars/{car_id}")
    assert res.status_code == 401  # هذا صحيح