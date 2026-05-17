from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_read_db
from app.schemas import UserLogin, Token
from app.models import User
from app.utils import verify_password
from app.core.logging_config import logger
from app.core.security import Create_Access_Token
from app.core.exceptions import UnauthorizedException

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


# TODO: Implement login endpoint
@router.post("/login" , status_code=status.HTTP_200_OK , response_model=Token)  # login endpoint 
async def login(user_credentials : UserLogin , db : AsyncSession = Depends(get_read_db)) -> Token:
    normalized_email = user_credentials.email.lower()
    query = select(User).where(User.email == normalized_email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {normalized_email}")
        raise UnauthorizedException(message="Invalid credentials")
    if not user.is_active:
        logger.warning(f"Inactive user login attempt: {normalized_email}", extra={"user_id": str(user.id)})
        raise UnauthorizedException(message="User account is inactive")
    logger.info(f"User logged in successfully: {user.email}", extra={"user_id": user.id})
    access_token = await Create_Access_Token(data={"sub" : str(user.id), "role": user.role.value}) # sub means subject (user id) ,  jwt can't encode UUID directly so we convert it to string, role is the user role

    return {"access_token": access_token, "token_type": "bearer"}
    
    
