import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
from fastapi import FastAPI, HTTPException, status, Response , Depends ,Request , APIRouter
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
import sqlalchemy
from sqlalchemy import select


router = APIRouter(
    prefix="/users",  # 
    tags=["Users"]    #
)






@router.post("/", status_code=HTTPStatus.CREATED,response_model=UserResponse) # create a new user , search for discription and summary 
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    hashed_pwd = get_password_hash(user.password) # hash the password , where  get_password_hash come from ? from fastapi.security
    new_user = User (
        email=user.email, 
        hashed_password=hashed_pwd,
        full_name=user.full_name
    )
    db.add(new_user)
    await db.commit() # why await ? because we are using async session
    await db.refresh(new_user)
    return new_user


@router.get("/{id}", response_model=UserResponse)
async def get_user(id: UUID, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.id == id , User.is_active == True)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        logger.error(f"user with id {id} doesn't exist", extra={"request_id": get_request_id()})
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, extra={"error": f"user with id {id} doesn't exist"})
    return user