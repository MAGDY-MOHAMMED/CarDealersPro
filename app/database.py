# Import required libraries for database connection
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker  # Create async engines and sessions
from sqlalchemy.orm import DeclarativeBase  # Base class for database models
from sqlalchemy import event
from sqlalchemy.engine import URL
from typing import AsyncGenerator  # Type hint for return values
import os  # Read environment variables
from app.core.request_id import set_request_id, generate_request_id, get_request_id
from app.core.logging_config import logger
from app.core.config import settings  # Read settings from config.py

# Try to get DATABASE_URL from environment variables
# If present, this means we're using Neon or cloud database
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    SQL_ALCHEMY_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    SQL_ALCHEMY_PRIMARY_URL = SQL_ALCHEMY_URL
    SQL_ALCHEMY_WRITE_URL = SQL_ALCHEMY_URL
    SQL_ALCHEMY_READ_URL = SQL_ALCHEMY_URL
    CLOUD_SINGLE_ENGINE = True
    logger.info("Using DATABASE_URL from environment (single engine cloud mode)", extra={"request_id": "N/A"})
else:
    # If DATABASE_URL doesn't exist, use local settings from config.py
    # Here we use 3 different users for each engine
    try:
        # Primary user credentials - this is the main user for general operations
        DB_PRIMARY_USER = os.getenv("DATABASE_PRIMARY_USER", settings.DATABASE_USERNAME)
        DB_PRIMARY_PASSWORD = os.getenv("DATABASE_PRIMARY_PASSWORD", settings.DATABASE_PASSWORD)

        # Write user credentials - this user is used for API POST/PUT/DELETE
        DB_WRITE_USER = os.getenv("DATABASE_WRITE_USER", settings.DATABASE_USERNAME)
        DB_WRITE_PASSWORD = os.getenv("DATABASE_WRITE_PASSWORD", settings.DATABASE_PASSWORD)

        # Read user credentials - this user is used for GET and reports (read-only)
        DB_READ_USER = os.getenv("DATABASE_READ_USER", settings.DATABASE_USERNAME)
        DB_READ_PASSWORD = os.getenv("DATABASE_READ_PASSWORD", settings.DATABASE_PASSWORD)

        DB_HOST = settings.DATABASE_HOSTNAME  # Database host
        DB_PORT = settings.DATABASE_PORT  # Database port
        DB_NAME = settings.DATABASE_NAME  # Database name

        # Build SQLAlchemy URLs using the modern URL.create API
        SQL_ALCHEMY_PRIMARY_URL = URL.create(
            drivername="postgresql+asyncpg",
            username=DB_PRIMARY_USER,
            password=DB_PRIMARY_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
        ).render_as_string(hide_password=False) #means show the password in the log what password ? the primary user password
        SQL_ALCHEMY_WRITE_URL = URL.create(
            drivername="postgresql+asyncpg",
            username=DB_WRITE_USER,
            password=DB_WRITE_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
        ).render_as_string(hide_password=False) #means show the password in the log what password ? the write user password
        SQL_ALCHEMY_READ_URL = URL.create(
            drivername="postgresql+asyncpg",
            username=DB_READ_USER,
            password=DB_READ_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
        ).render_as_string(hide_password=False) #means show the password in the log what password ? the read user password

        logger.info("Using 3-tier database configuration (primary, write, read)", extra={"request_id": "N/A"})
    except Exception as e:
        # If any error occurs, log it and raise Exception
        logger.error("Failed to construct database URL from settings", extra={"error": str(e), "request_id": "N/A"})
        raise ValueError("Database configuration is incomplete. Please check your .env file.")

# Create engines once after URLs are resolved
if DATABASE_URL:
    primary_engine = create_async_engine(
        SQL_ALCHEMY_PRIMARY_URL,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    write_engine = primary_engine
    read_engine = primary_engine
else:
    primary_engine = create_async_engine(
        SQL_ALCHEMY_PRIMARY_URL,
        pool_size=15,
        max_overflow=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    write_engine = create_async_engine(
        SQL_ALCHEMY_WRITE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
    read_engine = create_async_engine(
        SQL_ALCHEMY_READ_URL,
        pool_size=20,
        max_overflow=40,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

# Add event listener to write engine to add request ID in logs
# Reason: so we can track requests in database logs
@event.listens_for(write_engine.sync_engine, "before_cursor_execute")
def add_request_id_to_logs(conn, cursor, statement, parameters, context, executemany):
    # Get request ID
    request_id = get_request_id()

    # If request ID exists, add it to SQL statement as a comment
    # Reason: so it appears in database logs and we know which request it is
    if request_id:
        context.statement = f"/* Request_id : {request_id} */ {statement}"

    # Log the SQL statement for debugging
    logger.debug("Executing SQL statement", extra={
        "statement": statement,
        "parameters": parameters,
        "request_id": request_id,
        "query": context.statement if request_id else statement
    })

# Create session makers for the 3 engines
# Session maker is a factory that creates sessions for each engine
# autocommit=False: we commit manually to control transactions
# autoflush=False: we flush manually to control when to update the database
# expire_on_commit=False: after commit, objects don't expire, so we can use them without reload
PrimarySessionLocal = async_sessionmaker(
    autocommit=False, # to commit manually to control transactions
    autoflush=False, # to flush manually to control when to update the database
    bind=primary_engine,
    class_=AsyncSession,
    expire_on_commit=False # after commit, objects don't expire, so we can use them without reload
)

WriteSessionLocal = async_sessionmaker(
    autocommit=False, # to commit manually to control transactions
    autoflush=False, # to flush manually to control when to update the database
    bind=write_engine,
    class_=AsyncSession,
    expire_on_commit=False # after commit, objects don't expire, so we can use them without reload
)

ReadSessionLocal = async_sessionmaker(
    autocommit=False, # to commit manually to control transactions
    autoflush=False, # to flush manually to control when to update the database
    bind=read_engine,
    class_=AsyncSession,
    expire_on_commit=False # after commit, objects don't expire, so we can use them without reload
)

# Base class for all database models
# All models must inherit from this
class Base(DeclarativeBase):
    """
    Base class for all database models
    """
    pass


async def get_primary_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for general operations (primary engine)
    """
    # Open session from primary engine
    async with PrimarySessionLocal() as session:
        try:
            # Log that session was opened
            logger.debug("Primary database session opened", extra={"request_id": get_request_id()})

            # Return session to route handler
            yield session

            # If no exceptions, commit
            # Reason: to save changes to the database
            await session.commit()
        except Exception as e:
            # If exception occurs, rollback
            # Reason: to revert database to its original state and avoid saving corrupted data
            await session.rollback()
            logger.exception("Primary database transaction failed", extra={"request_id": get_request_id(), "error": str(e)})
            raise
        finally:
            # In any case, close the session
            # Reason: to return connection to pool and free up space in the pool for other requests
            await session.close()


async def get_write_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for write operations (POST, PUT, DELETE)
    """
    # Open session from write engine
    async with WriteSessionLocal() as session:
        try:
            # Log that session was opened
            logger.debug("Write database session opened", extra={"request_id": get_request_id()})

            # Return session to route handler
            yield session

            # If no exceptions, commit
            # Reason: to save changes to the database
            await session.commit()
        except Exception as e:
            # If exception occurs, rollback
            # Reason: to revert database to its original state and avoid saving corrupted data
            await session.rollback()
            logger.exception("Write database transaction failed", extra={"request_id": get_request_id(), "error": str(e)})
            raise
        finally:
            # In any case, close the session
            await session.close()


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for read operations (GET and reports)
    """
    # Open session from read engine
    async with ReadSessionLocal() as session:
        try:
            # Log that session was opened
            logger.debug("Read database session opened", extra={"request_id": get_request_id()})

            # Return session to route handler
            yield session

            # No commit needed for read operations
            # Reason: read operations don't change data, so we don't need to commit
        except Exception as e:
            # If exception occurs, rollback
            # Reason: even for read operations, there might be an open transaction that needs to be closed
            await session.rollback()
            logger.exception("Read database transaction failed", extra={"request_id": get_request_id(), "error": str(e)})
            raise
        finally:
            # In any case, rollback if no commit was made
            # Reason: to ensure no transaction is left open in the database
            # Even for read operations, PostgreSQL automatically opens a transaction
            # We must rollback to close the transaction and return the connection to the pool
            if not session.in_transaction():  # If no transaction is open
                # If no transaction is open, close the session
                await session.close()
            else:
                # If transaction is open, rollback first
                await session.close() # close make automatic rollback in sqlalchemy2.0


# Backward compatibility: get_db uses primary engine (for existing code)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session (defaults to primary engine for backward compatibility)
    Reason: so existing code that uses get_db continues to work without changes
    """
    # Open session from primary engine
    async with PrimarySessionLocal() as session:
        try:
            # Log that session was opened
            logger.debug("Database session opened (primary engine)", extra={"request_id": get_request_id()})

            # Return session to route handler
            yield session

            # If no exceptions, commit
            await session.commit()
        except Exception as e:
            # If exception occurs, rollback
            await session.rollback()
            logger.exception("Database transaction failed", extra={"request_id": get_request_id(), "error": str(e)})
            raise
        finally:
            # In any case, close the session
            await session.close()


async def close_all_engines():
    """
    Close database engines cleanly without double-disposing shared engines.
    """
    closed_engines = set()
    for engine_name, db_engine in (
        ("Primary", primary_engine),
        ("Write", write_engine),
        ("Read", read_engine),
    ):
        try:
            if db_engine and id(db_engine) not in closed_engines:
                await db_engine.dispose() # means close all connections and clear the connection pool
                closed_engines.add(id(db_engine))
                logger.info(f"{engine_name} database engine closed", extra={"request_id": "N/A"})
        except Exception as e:
            logger.error(f"Failed to close {engine_name.lower()} engine", extra={"error": str(e), "request_id": "N/A"})