import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from app.models import Car
from app.core.config import settings
import re


BASE_URL = "https://www.olx.com.eg/vehicles/cars-for-sale/"
HEADERS = {"User-Agent": "CarDealersPro/1.0 (research bot; contact@cardealerspro.com)"}



def _get_async_db_url():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        if "sslmode=require" not in url:
            url += "?sslmode=require" if "?" not in url else "&sslmode=require"
        return url
    return (
        f"postgresql+asyncpg://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOSTNAME}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )


engine = create_async_engine(_get_async_db_url(), echo=False) #echo=False means no sql queries will be printed to the console
#fetch the html content of a page
async def fetch_page(client, url, retries=3) -> str:
    for _ in range(retries):
        try:
            response = await client.get(url)
            if response.status_code == 200:
                return response.text #return the html content
        except Exception:
            await asyncio.sleep(2)
    return None
#parse the html content and extract car data
async def parse_listing(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    cars = []
    #select all car listings
    for ad in soup.select('.ads__item'):#select all car listings , ad means advertisement
        try:
            #extract car title
            title = ad.select_one('.ads__item__title').text.strip() #
            #extract car price
            price = re.sub(r'[^\d.]', '', ad.select_one('.ads__item__price').text) #
            #extract car details
            details = ad.select_one('.ads__item__details').text #
            #extract car year
            year_match = re.search(r'\b(19|20)\d{2}\b', details) #
            car = {
                'title': title,
                'price': float(price) if price else None,
                'year': int(year_match.group()) if year_match else None,
                'url': ad.select_one('a')['href']
            }
            cars.append(car)
        except Exception:
            continue
    return cars
#import the database session and models


# for saving the data to the database
async def save_to_db(listings):
    async with AsyncSession(engine) as session:
        for item in listings:
            result = await session.execute(
                select(Car).where(Car.external_url == item['url']) # Check if the car already exists
            )
            if result.scalar_one_or_none():
                continue
            # Extract brand and model from title
            title_parts = item['title'].split()
            brand = title_parts[0] if title_parts else "Unknown"
            model = " ".join(title_parts[1:3]) if len(title_parts) > 1 else "Unknown"
            # Create a new car
            # We assume brand/model are extracted from the title (e.g., "Toyota Corolla 2020")
            # Here is a simple logic to split the title
            title_parts = item['title'].split() # Split the title into words
            brand = title_parts[0] if title_parts else "Unknown" # Get the first word as brand
            model = " ".join(title_parts[1:3]) if len(title_parts) > 1 else "Unknown" # Get the second and third words as model
            car = Car(
                brand=brand,
                model=model,
                year=item['year'] or 2020,
                price_consumer=item['price'] or 0,
                price_dealer=item['price'] or 0,  # Temporary
                condition="used",
                external_url=item['url'],
                owner_id=None,   # No owner specified
                is_available=True,
                is_deleted=False,
                published=False   # Not published because it's raw data
            )
            session.add(car)
        await session.commit()



async def scrape_all():
    async with httpx.AsyncClient(headers=HEADERS) as client:
         page = 1
         while True:
            url = f"{BASE_URL}?page={page}"
            html = await fetch_page(client, url)
            if not html:
                break
            listings = await parse_listing(html) #parse the html content
            if not listings:
                break
            await save_to_db(listings)
            page += 1 #move to the next page
            await asyncio.sleep(2)  # for rate limiting to respect the server



if __name__ == "__main__":
    asyncio.run(scrape_all())

