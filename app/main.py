import os
from typing import Final
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
import time
from app.database import close_all_engines
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.request_id import set_request_id, generate_request_id, get_request_id
from app.core.logging_config import logger
from app.routers import users, cars
from app.routers import auth
from app.routers import ratings
from app.routers import media
from app.routers import finance
from sqlalchemy import select
from fastapi.middleware.cors import CORSMiddleware
from app.core.exceptions import AppException
from dotenv import load_dotenv
from app.routers import ai
import sys

# Install uvloop for better performance (libuv-based event loop)
# Reason: uvloop is faster than the default asyncio event loop
# It uses libuv (the same library used by Node.js) for better performance
try:
    uvloop.install()
    logger.info("uvloop installed successfully - using libuv-based event loop", extra={"request_id": "N/A"})
except ImportError:
    logger.warning("uvloop not installed - falling back to default asyncio event loop", extra={"request_id": "N/A"})
except Exception as e: #
    logger.error(f"Failed to install uvloop: {e}", extra={"request_id": "N/A"})

# Load environment variables
load_dotenv()


# Standardized Constants (using Final to prevent modification)
APP_TITLE: Final = "CarDealersPro API"
APP_VERSION: Final = "1.0.0"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next): # override the dispatch method to add request ID to each request 
        request_id = generate_request_id()
        set_request_id(request_id)
        start_time = time.perf_counter() # High-resolution timer for MAMAA performance standards
        logger.info(f"Request started", extra={
            "method": request.method,
            "path": request.url.path, # get the path of the request
            "query_params": dict(request.query_params), # get the query parameters , ?key=value&key2=value2 this  is the query parameter separator
            "url": request.url, # get the full URL
            "client": request.client.host if request.client else None # get the client IP address
        })
        try :
            response = await call_next(request) # call the next middleware or route handler 
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e: # catch any exception
            # log the exception
            logger.exception("Request failed", extra={"error" : str(e), "duration" : time.perf_counter() - start_time}) # log the request status
            raise
        finally :
            duration = (time.perf_counter() - start_time) * 1000 # convert to milliseconds
            # prepare log parameters
            log_params = {
                "duration_ms" : round(duration, 2), # round to 2 decimal places
                "request_id" : get_request_id()
            }
            # add status code if response exists
            if 'response' in locals () : # locals return a dictionary of local variables, we check if response is in it
                log_params["status"] = response.status_code
            logger.info("Request completed", extra=log_params)


app = FastAPI(title=APP_TITLE, version=APP_VERSION) # create the FastAPI app

if sys.platform != "win32":
    try :
        import uvloop
        uvloop.asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        logger.warning("uvloop not available, using default event loop")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

# CORS Configuration - Read from environment variables for flexibility
# Format: CORS_ORIGINS=http://localhost:3000,http://localhost:8080,https://cardealerspro.com
cors_origins_env = os.getenv("CORS_ORIGINS", "")
origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()] if cors_origins_env else []

# Fallback to default origins if not set (for backward compatibility)
if not origins:
    origins = [
        "http://localhost:3000",  # Frontend dev server
        "http://localhost:8080",  # Alternative dev server
        "https://cardealerspro.com",  # Production frontend
        "https://www.cardealerspro.com",  # Production frontend with www
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # Expose request ID to frontend
)

app.add_middleware(RequestIDMiddleware) # add request ID middleware to the app

# Register shutdown event handler to close database engines gracefully
# Reason: when the API shuts down, we close all database connections cleanly
# and ensure no pending transactions are left open in the database
@app.on_event("shutdown")
async def shutdown_event():
    """
    Shutdown event handler to close all database engines
    """
    # Log that we're starting the shutdown process
    logger.info("Shutting down application - closing database engines", extra={"request_id": "N/A"})

    # Call close_all_engines() from database.py to close all engines
    # Reason: close_all_engines() closes primary_engine, write_engine, read_engine
    # and returns all connections to the pool and cleans up pending transactions
    await close_all_engines()

    # Log that shutdown process completed successfully
    logger.info("Application shutdown completed successfully", extra={"request_id": "N/A"})

app.include_router(users.router) # include the users router
app.include_router(cars.router) # include the cars router
app.include_router(auth.router) # include the auth router
app.include_router(ratings.router) # include the ratings router
app.include_router(media.router) # include the media router
app.include_router(finance.router) # include the finance router
app.include_router(ai.router) # include the ai router





@app.get("/")
async def root():
    return {"status": "Online", "engine": "CarDealers Pro API !!!!! "}








# handle http exceptions
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request:Request, exc:StarletteHTTPException): # log the exception
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": exc.detail,
            "request_id": get_request_id()
        }
    )

# handle validation errors
@app.exception_handler(RequestValidationError)
async def Validation_exception_handler (request : Request , exc : RequestValidationError):
    return JSONResponse(
        status_code = 422, # unprocessable entity
        content = {
            "code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": exc.errors(),
            "body": str(exc.body),
            "request_id" : get_request_id(),
        },
    )

# handle custom AppException
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    logger.error(f"Application error: {exc.code}", extra={"request_id": get_request_id(), "code": exc.code})
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response().model_dump()
    )

# Handle unexpected exceptions
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unexpected error occurred", extra={"request_id": get_request_id()})
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "Internal server error",
            "request_id": get_request_id(),
        }
    )

