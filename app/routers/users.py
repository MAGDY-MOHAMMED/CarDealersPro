from uuid import UUID
from http import HTTPStatus
from fastapi import Depends, APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_auth_user
from app.database import get_read_db, get_write_db
from app.core.request_id import get_request_id
from app.core.logging_config import logger
from app.models import User
from app.schemas import UserCreate, UserResponse, TokenData
from app.utils import get_password_hash
from app.models import UserRole
from app.core.exceptions import ConflictException, NotFoundException

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)






@router.post("/", status_code=HTTPStatus.CREATED,response_model=UserResponse) # create a new user , search for discription and summary
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_write_db)):
    normalized_email = user.email.lower()
    existing_user = await db.execute(select(User).where(User.email == normalized_email))
    existing = existing_user.scalar_one_or_none()
    if existing: # if the user exists
        raise ConflictException(
            message="User with this email already exists",
            details={"email": user.email}
        )
    hashed_pwd = get_password_hash(user.password) # hash the password , where  get_password_hash come from ? from fastapi.security
    new_user = User (
        email=normalized_email, 
        hashed_password=hashed_pwd,
        full_name=user.full_name,
        role=UserRole.CLIENT
    )
    db.add(new_user)
    await db.commit() # why await ? because we are using async session
    await db.refresh(new_user)
    return new_user


@router.get("/{id}", response_model=UserResponse)
async def get_user(id: UUID, db: AsyncSession = Depends(get_read_db), current_user: TokenData = Depends(get_auth_user)):
    query = select(User).where(User.id == id , User.is_active == True)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        logger.error(f"user with id {id} doesn't exist", extra={"request_id": get_request_id()})
        raise NotFoundException("User", str(id))
    return user