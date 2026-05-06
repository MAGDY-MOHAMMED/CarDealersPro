from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from typing import AsyncGenerator
import os
from core.logging_config import logger
from core.request_id import get_request_id
from app.core.config import settings

# Try to get DATABASE_URL from environment (Render provides this)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Use Render's DATABASE_URL and convert to asyncpg
    SQL_ALCHEMY_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    logger.info("Using DATABASE_URL from environment", extra={"request_id": "N/A"})
else:
    # Use local settings from config.py
    try:
        SQL_ALCHEMY_URL = f"postgresql+asyncpg://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOSTNAME}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
        logger.info("Using local database configuration", extra={"request_id": "N/A"})
    except Exception as e:
        logger.error("Failed to construct database URL from settings", extra={"error": str(e), "request_id": "N/A"})
        raise ValueError("Database configuration is incomplete. Please check your .env file.")

engine = create_async_engine(SQL_ALCHEMY_URL, pool_size=10, max_overflow=20) # pool_size is the number of connections to keep in the pool, max_overflow is the number of connections to create beyond the pool_size
# this event is used to add request id to the sql queries for better debugging and tracing
@event.listens_for(engine.sync_engine, "before_cursor_execute") # pragma: no cover - database event , event listener means that this function will be called before every sql query
def add_request_id_to_logs(conn, cursor, statement, parameters, context, executemany):
    request_id= get_request_id()
    if request_id :
        context.statement = f"/* Request_id : {request_id} */ {statement}" # adding request id to the statement
    logger.debug("Executing SQL statement",extra={
        "statement": statement,
        "parameters": parameters,
        "request_id": request_id,
        "query" : context.statement if request_id else statement
    })
    



SessionLocal = async_sessionmaker( # pragma: no cover - database session
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
    ) 

class Base(DeclarativeBase):
    """
    Base class for all database models
    """
    
    pass


#"host=localhost dbname=fastapi user=postgres password=your_password"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            logger.debug("Database session opened", extra={"request_id": get_request_id()})
            yield session  
            await session.commit() # if no exceptions
            # psycopg3 automatically commits if no exception inside the with block
        except Exception as e:
            await session.rollback()
            logger.exception("Database transaction failed ", extra={"request_id": get_request_id(), "error": str(e)})
            raise
        finally :
            await session.close() # close the connection