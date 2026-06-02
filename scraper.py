import asyncio
import os
import sys
import logging
import re
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from app.models import Car
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("Scraper")

BASE_URL = "https://www.contactcars.com"
SEARCH_URL = f"{BASE_URL}/cars/search"

def get_db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        if "sslmode=require" not in url:
            url += "?sslmode=require" if "?" not in url else "&sslmode=require"
        return url
    return (f"postgresql+asyncpg://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}"
            f"@{settings.DATABASE_HOSTNAME}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
}

def extract_cars_from_html(html: str) -> List[Dict[str, Any]]:
    """يستخرج بيانات السيارات من صفحة البحث في ContactCars"""
    soup = BeautifulSoup(html, "html.parser")
    cars = []
    for item in soup.select("div.car-list-item"):
        try:
            # العنوان والعربية (الماركة والموديل)
            title_elem = item.select_one("h2.car-title a, .car-model a")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)

            # استخراج الماركة والموديل
            brand, model = "", ""
            parts = title.split()
            if parts:
                brand = parts[0]
                model = " ".join(parts[1:]) if len(parts) > 1 else ""

            # السنة
            year_elem = item.select_one(".car-year, .year")
            year_text = year_elem.get_text(strip=True) if year_elem else ""
            year = None
            if year_text:
                year_match = re.search(r'(\d{4})', year_text)
                if year_match:
                    year = int(year_match.group(1))

            # السعر
            price_elem = item.select_one(".car-price, .price")
            price_text = price_elem.get_text(strip=True) if price_elem else ""
            price = 0.0
            if price_text:
                price_match = re.search(r'[\d,]+', price_text)
                if price_match:
                    price = float(price_match.group().replace(",", ""))

            # الكيلومترات
            km_elem = item.select_one(".car-km, .mileage")
            km_text = km_elem.get_text(strip=True) if km_elem else ""
            mileage = 0
            if km_text:
                km_match = re.search(r'[\d,]+', km_text)
                if km_match:
                    mileage = int(km_match.group().replace(",", ""))

            # الموقع (المدينة)
            loc_elem = item.select_one(".car-location, .location")
            location = loc_elem.get_text(strip=True) if loc_elem else "Egypt"

            # رابط الإعلان
            link_elem = title_elem  # عنوان العربية فيه رابط
            url = link_elem.get("href", "")
            if url and url.startswith("/"):
                url = f"{BASE_URL}{url}"

            cars.append({
                "title": title,
                "brand": brand,
                "model": model,
                "year": year,
                "price": price,
                "mileage": mileage,
                "city": location,
                "url": url,
            })
        except Exception:
            continue
    return cars

async def save_car(engine, car_data: Dict[str, Any]) -> bool:
    async with AsyncSession(engine) as session:
        existing = await session.execute(
            select(Car).where(Car.external_url == car_data["url"])
        )
        if existing.scalar_one_or_none():
            return False
        car = Car(
            brand=car_data["brand"] or (car_data["title"].split()[0] if car_data["title"] else "Unknown"),
            model=car_data["model"] or "Unknown",
            year=car_data["year"] or 2020,
            price_consumer=car_data["price"],
            price_dealer=car_data["price"],
            condition="used",
            external_url=car_data["url"],
            owner_id=None,
            is_available=True,
            is_deleted=False,
            published=False
        )
        session.add(car)
        await session.commit()
    return True

def get_total_pages(html: str) -> int:
    """يحدد عدد الصفحات من شريط التصفح"""
    soup = BeautifulSoup(html, "html.parser")
    # عادةً آخر رقم في الـ pagination
    pagination = soup.select_one("ul.pagination li:last-child a")
    if pagination:
        try:
            return int(pagination.get_text(strip=True))
        except ValueError:
            pass
    return 1

async def scrape_all():
    logger.info("Starting ContactCars scraper...")
    engine = create_async_engine(get_db_url(), echo=False)
    total_added = 0

    # جلب الصفحة الأولى لمعرفة عدد الصفحات
    first_page_url = f"{SEARCH_URL}?page=1"
    logger.info(f"Fetching first page: {first_page_url}")
    try:
        resp = requests.get(first_page_url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            logger.error(f"Failed to access ContactCars. Status: {resp.status_code}")
            await engine.dispose()
            return
    except Exception as e:
        logger.error(f"Connection error: {e}")
        await engine.dispose()
        return

    total_pages = get_total_pages(resp.text)
    logger.info(f"Total pages found: {total_pages}")

    for page_num in range(1, total_pages + 1):
        url = f"{SEARCH_URL}?page={page_num}"
        logger.info(f"Scraping page {page_num}/{total_pages}: {url}")
        if page_num > 1:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"Page {page_num} returned {resp.status_code}, skipping.")
                continue

        cars = extract_cars_from_html(resp.text)
        if not cars:
            logger.info("No cars found on this page. Stopping.")
            break

        for car_data in cars:
            if await save_car(engine, car_data):
                total_added += 1
                logger.info(f"Saved: {car_data['title'][:50]}...")

        logger.info(f"Page {page_num} done. Total added so far: {total_added}")

    await engine.dispose()
    logger.info(f"Scraping completed. Total cars added: {total_added}")

if __name__ == "__main__":
    asyncio.run(scrape_all())