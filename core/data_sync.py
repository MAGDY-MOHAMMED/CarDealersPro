import asyncio
import logging
import os
from pathlib import Path
import pyarrow.parquet as pq
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
from app.models import CarFeatures
from app.core.config import settings
#this file for 

logger= logging.getLogger(__name__)
 #
async def get_async_db_url():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        if "sslmode=require" not in url: #add sslmode=require if not present
            url += "?sslmode=require" if "?" not in url else "&sslmode=require" #add sslmode=require if not present
        return url
    return (
        f"postgresql+asyncpg://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}"
        f"@{settings.DATABASE_HOSTNAME}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
    )






async def sync_parquet_to_db():
    engine = create_async_engine(await get_async_db_url(),echo=False) # echo=False to not print sql queries
    parquet_path = Path("data/optimized/") # means data/optimized/ folder
    for file in parquet_path.glob("*.parquet"): # means iterate over all parquet files in data/optimized/ folder
        df = pq.read_table(file).to_pandas() #read parquet file and convert to pandas dataframe
        async with AsyncSession(engine) as session: #means using context manager to ensure connection is properly closed
            for _, row in df.iterrows(): # iterate over each row in the dataframe
                # insert or update car features
                stmt = pg_insert(CarFeatures).values( #
                    car_id=row['car_id'],
                    feature_vector=row['features'],
                    predicted_price=row.get('price_prediction'),
                    damage_score=row.get('damage_score')
                    #add last_updated column
                ).on_conflict_do_update( #update if car_id already exists
                    index_elements=['car_id'],
                    set_=dict(
                        feature_vector=row['features'],
                        predicted_price=row.get('price_prediction'),
                        damage_score=row.get('damage_score'),
                        last_updated=func.now()
                    )
                )
                await session.execute(stmt) #execute the statement
        await session.commit() #commit the transaction
    await engine.dispose() #close database connection
    
if __name__ == "__main__":
    asyncio.run(sync_parquet_to_db())

        