import asyncio
import logging
import os
from pathlib import Path
import pyarrow.parquet as pq # for reading parquet files
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
from app.models import CarFeatures
from app.core.config import settings
#this file for syncing parquet files to database

logger= logging.getLogger(__name__)
 #
def get_async_db_url():
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





#function for syncing parquet files to database
async def sync_parquet_to_db():
    engine = create_async_engine(await get_async_db_url(),echo=False) # echo=False to not print sql queries
    parquet_path = Path("data/optimized/") # means data/optimized/ folder
    if not parquet_path.exists(): #
        logger.warning(f"Parquet directory {parquet_path} not found. Skipping sync.", exc_info=True,) # exc_info=True means print exception info
        return
    async with AsyncSession(engine) as session: #why async ? because we are using async engine
        for file in parquet_path.glob("*.parquet"): # means iterate over all parquet files in data/optimized/ folder
            df = pq.read_table(file).to_pandas() #read parquet file and convert to pandas dataframe
            required_cols = {'car_id', 'feature_vector', 'predicted_price', 'damage_score'} #required columns, why {} ? because it's faster to check if all required columns are present


            if not required_cols.issubset(set(df.columns)): #check if all required columns are present
                logger.warning(f"Missing required columns in {file.name}. Skipping.", exc_info=True) # exc_info=True means print exception info
                continue

            records = df[['car_id', 'feature_vector', 'predicted_price', 'damage_score']].to_dict(orient='records') #.to_dict(orient='records') means convert dataframe to list of dictionaries
            # time to insert or update car features
            stmt = pg_insert(CarFeatures).values(records)  #insert or update car features
            stmt = stmt.on_conflict_do_update( #update if car_id already exists
                    index_elements=['car_id'], # means 
                    set_=dict( # set_ means update the following columns
                        feature_vector=stmt.excluded.feature_vector,
                        predicted_price=stmt.excluded.predicted_price,
                        damage_score=stmt.excluded.damage_score,
                        last_updated=func.now()
                    )
                )
            await session.execute(stmt) #execute the statement
        await session.commit() #commit the transaction
    await engine.dispose() #close database connection
    
if __name__ == "__main__":
    asyncio.run(sync_parquet_to_db())

        