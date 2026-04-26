#import sys from pathlib import Path project_root = Path(__file__).resolve().parent.parent if str(project_root) not in sys.path:    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request 
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict # for pydantic v2
import uuid
import time
from uuid import UUID
from http import HTTPStatus
from app.database import get_db, engine , Base
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from core.request_id import set_request_id, generate_request_id , get_request_id
from core.logging_config import logger
from app.models import Car , User
from app.schemas import CarUpdate, CarsBase, CarResponse , CarUpdate , UserCreate , UserResponse
from app.utils import get_password_hash, verify_password
from sqlalchemy.ext.asyncio import AsyncSession
from core.request_id import ensure_request_id, request_id_var
import sqlalchemy
from app.routers import users, cars
from app.routers import auth
from app.routers import ratings
from sqlalchemy import select
from fastapi.middleware.cors import CORSMiddleware







class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next): # override the dispatch method to add request ID to each request 
        request_id = generate_request_id()
        set_request_id(request_id)
        start_time= time.time()
        logger.info(f"Request started" , extra = {
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
        except Exception as e:
            logger.exception("Request failed", extra = {"error" : str(e), "duration" : time.time() - start_time}) # log the request status
            raise
        finally :
            duration = (time.time() - start_time) * 1000 # convert to milliseconds
            # prepare log parameters
            log_params = {
                "duration_ms" : round(duration, 2), # round to 2 decimal places
                "request_id" : get_request_id()
            }
            # add status code if response exists
            if 'response' in locals () : # locals return a dictionary of local variables, we check if response is in it
                log_params["status"] = response.status_code
            logger.info("Request completed", extra = log_params)
        

app = FastAPI(title="Car Dealers Pro API") # create the FastAPI app

origins = [
    "*" # allows all origins
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware) # add request ID middleware to the app

app.include_router(users.router) # include the users router
app.include_router(cars.router) # include the cars router
app.include_router(auth.router) # include the auth router
app.include_router(ratings.router) # include the ratings router




@app.get("/") # root endpoint
async def root ():
    return {"status": "Online", "engine": "CarDealers Pro API"}

@app.get("/health") # health check endpoint for cloud/load balancer
async def health():
    return {"status": "ok"}








# handle http exceptions
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request:Request, exc:StarletteHTTPException): # log the exception 
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail, # get the error message
            "request_id": get_request_id() # get the request id from the middleware
        }
    )

# handle validation errors
@app.exception_handler(RequestValidationError)
async def Validation_exception_handler (request : Request , exc : RequestValidationError):
    return JSONResponse(
        status_code = 422, # unprocessable entity
        content = {
            "detail" : exc.errors(),  # for all missing things not one 
            "body" : str(exc.body), # for the body of the request
            "request_id" : get_request_id(),
        },
    )

# handle unexpected exceptions
@app.exception_handler(Exception)
async def generic_exception_handler (request : Request , exc : Exception) : 
    logger.exception ("Unexpected error occurred" , extra={"request_id": get_request_id()})
    return JSONResponse (
        status_code = 500,
        content= {
            "detail" : "Internal server error",
            "request_id" : get_request_id(),
        }
    )





