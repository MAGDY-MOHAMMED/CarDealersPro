import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool 
import time
import logging
from app.logging_config import logger
from typing import Generator

logger = logging.getLogger(__name__) # why ? because it's easier to filter logs by logger name



CONN_STR = "host=localhost dbname=fastapi user=postgres password=Magdy123456"
MIN_POOL_SIZE = 2
MAX_POOL_SIZE = 20
MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 1

def create_pool_with_retry() -> ConnectionPool:
    attempt = 0 # attempts here means the number of times we tried to create the pool
    max_attempts = 5
    while attempt < max_attempts:
        try:

            pool = ConnectionPool(
                conninfo=CONN_STR,
                min_size=MIN_POOL_SIZE,
                max_size=MAX_POOL_SIZE,
                kwargs={"row_factory": dict_row},
                retry=MAX_RETRIES, # number of times to retry if the connection fails
                max_lifetime=300 # maximum of connections in seconds
            )
            pool.wait(timeout=10) # wait for the pool to be ready
            logger.info("Connection pool created successfully", extra={"min_size": MIN_POOL_SIZE, "max_size": MAX_POOL_SIZE}) # why extra ? because it's easier to filter logs by extra fields
            return pool

        except Exception as e:
            attempt += 1 # increment the attempt counter
            wait_time = RETRY_BACKOFF_BASE * (2 ** (attempt - 1)) # exponential backoff
            logging.warning(f"pool initializtion failed (attempt{attempt}/{MAX_RETRIES}) : {e}."
                            f" Retrying in {wait_time} seconds...")
            if attempt < MAX_RETRIES : # if we haven't reached the maximum number of retries
                time.sleep(wait_time) # wait for the specified time before retrying
            else :  # if we have reached the maximum number of retries
                logger.critical ("Max retries reached while creating connection pool")
                raise RuntimeError("Failed to create connection pool after multiple attempts")
_pool = create_pool_with_retry()

def get_db() -> Generator[Connecion,None,None] :

    with _pool.connection() as conn:
        try:
            yield conn
            # psycopg3 automatically commits if no exception inside the with block
        except Exception:
            conn.rollback()
            logger.exception("Database transaction rolled back due to error")
            raise

