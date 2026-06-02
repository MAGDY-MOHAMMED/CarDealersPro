import io
import pytest
from PIL import Image
from httpx import AsyncClient

def _make_fake_image():
    """Create a valid 1x1 JPEG in memory."""
    img = Image.new("RGB", (1, 1), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf

@pytest.mark.asyncio
async def test_upload_image(client: AsyncClient, dealer_headers, car_id):
    fake_img = _make_fake_image()
    files = {"file": ("test.jpg", fake_img, "image/jpeg")}
    res = await client.post(f"/media/upload/{car_id}", files=files, headers=dealer_headers)
    assert res.status_code == 201
    media = res.json()
    assert media["car_id"] == car_id
    assert media["media_type"] == "image"
    return media["id"]

@pytest.mark.asyncio
async def test_get_car_media(client: AsyncClient, dealer_headers, car_id):
    res = await client.get(f"/media/car/{car_id}", headers=dealer_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

@pytest.mark.asyncio
async def test_delete_media(client: AsyncClient, dealer_headers, car_id):
    # Upload a new image to delete
    fake_img = _make_fake_image()
    files = {"file": ("delete.jpg", fake_img, "image/jpeg")}
    upload_res = await client.post(f"/media/upload/{car_id}", files=files, headers=dealer_headers)
    assert upload_res.status_code == 201
    media_id = upload_res.json()["id"]

    # Delete it
    del_res = await client.delete(f"/media/{media_id}", headers=dealer_headers)
    assert del_res.status_code == 204

    # Verify it's gone
    res = await client.get(f"/media/car/{car_id}", headers=dealer_headers)
    ids = [item["id"] for item in res.json()]
    assert media_id not in ids