from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from typing import AsyncGenerator
from core.logging_config import logger 
from core.request_id import get_request_id
from core.logging_config import logger 
from core.db_cursor import RequestIDCursor
import logging



SQL_ALCHEMY_URL = "postgresql+asyncpg://postgres:Magdy123456@localhost:5432/fastapi" # why asyncpg ? because it's faster than psycopg
engine = create_async_engine(SQL_ALCHEMY_URL, pool_size=10, max_overflow=20) # pool_size is the number of connections to keep in the pool, max_overflow is the number of connections to create beyond the pool_size

@event.listens_for(engine.sync_engine, "before_cursor_execute")
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
    




SessionLocal = async_sessionmaker(
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


#"host=localhost dbname=fastapi user=postgres password=Magdy123456"


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


