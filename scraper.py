import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession 
from sqlalchemy import select
from app.models import Car
from app.core.config import settings
import re
import sys
import logging
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("Scraper")
BASE_URL = "https://www.olx.com.eg/vehicles/cars-for-sale/"
HEADERS = {"User-Agent": "CarDealersPro/1.0 (research bot; contact@cardealerspro.com)"}


def get_db_url() -> str:
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


#fetch the html content of a page
async def fetch_page(client :httpx.AsyncClient, url : str, retries : int =3) -> str | None :
    for _ in range(1, retries + 1):
        try:
            response = await client.get(url,timeout= 30 , follow_redirects=True) #follow redirects to handle redirects
            if response.status_code == 200:
                logging.info(f"Fetched {url}")
                return response.text #return the html content
        except Exception:
            await asyncio.sleep(2)
            logger.warning(f"Failed to fetch {url}")
    return None



#parse the html content and extract car data
def parse_listing(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cars = []
    #select all car listings
    for ad in soup.select('.ads__item'):#select all car listings , ad means advertisement
        try:
            #extract car title
            title_elem = ad.select_one('.ads__item__title')
            if not title_elem:
                continue
            title = title_elem.text.strip() #get the title of the car
            #extract car price
            price_elem = ad.select_one('.ads__item__price') #select the price element
            price_str = price_elem.text if price_elem else "0"
            price = float(re.sub(r'[^\d.]', '', price_str)) if price_str else None

            link_elem = ad.select_one('a')
            url = link_elem.get('href') if link_elem else None
            if not url:
                continue
            url = url.split('?')[0]  #remove query parameters
            #
            details_elem = ad.select_one('.ads__item__details') #select the details element
            
            details = details_elem.text if details_elem else ""
            #extract car year
            year_match = re.search(r'\b(19|20)\d{2}\b', details) #
            year = int(year_match.group()) if year_match else None #

            car = {
                'title': title,
                'price': float(price) if price else None, #
                'year': year,
                'url': url #get the url of the car
            }
            cars.append(car)
        except Exception:
            continue
    return cars
#import the database session and models


# for saving the data to the database
async def save_to_db(engine ,listings :List[Dict[str, Any]]) -> int:
    if not listings:
        return 0
    added = 0
    async with AsyncSession(engine) as session:
        for item in listings:
            existing = await session.execute(
                select(Car).where(Car.external_url == item['url'])
            )
            if existing.scalar_one_or_none():
                continue  # مكرر
            title_parts = item['title'].split()
            brand = title_parts[0] if title_parts else "Unknown" #
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
            added += 1
        await session.commit()
    return added



async def scrape_all():
    logger.info("Starting scraper...")
    engine = create_async_engine(get_db_url(), echo=True)
    async with httpx.AsyncClient(headers=HEADERS) as client:
         page = 1
         while True:
            url = f"{BASE_URL}?page={page}"
            logger.info(f"Scraping page {page}: {url}")
            html = await fetch_page(client, url)
            if not html:
                logger.info("No more pages to scrape.")
                break
            listings = parse_listing(html) #parse the html content
            if not listings:
                logger.info("No more listings to scrape.")
                break
            added = await save_to_db(engine, listings)
            logger.info(f"Added {added} listings to database.")
            page += 1 #move to the next page
            await asyncio.sleep(3)  # for rate limiting to respect the server
    await engine.dispose()
    logger.info("Scraping completed.")


if __name__ == "__main__":
    try:
        asyncio.run(scrape_all())
    except KeyboardInterrupt: # Handle Ctrl+C
        logger.info("Scraper stopped by user.")
    except Exception as e: # Handle any other exceptions
        logger.exception(f"Fatal error: {e}")
        sys.exit(1) # Exit with error code

