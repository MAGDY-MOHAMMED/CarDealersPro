import asyncio
from app.database import engine, Base
from app.models import Car  
#this file for creating tables in the database with async
async def init_models():
    async with engine.begin() as conn:
        
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_models())