from fastapi import APIRouter, Depends , status , HTTPException
from sqlalchemy import select
from app.database import get_db
from app.schemas import UserLogin , Token
from app.models import User
from app.utils import verify_password , get_password_hash
from core.logging_config import logger
from app.core.security import Create_Access_Token, get_auth_user ,validate_token_payload
from app.core.config import settings
from core.logging_config import logger



from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


# TODO: Implement login endpoint
@router.post("/login" , status_code=status.HTTP_200_OK , response_model=Token)  # login endpoint 
async def login(user_credentials : UserLogin , db : AsyncSession = Depends(get_db)) -> Token:
    query = select(User).where(User.email == user_credentials.email) #select means query
    result = await db.execute(query)
    user = result.scalar_one_or_none() # why ? because we want to get one user or none
    if not user or not verify_password(user_credentials.password, user.hashed_password): #
        logger.warning(f"Failed login attempt for email: {user_credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    logger.info(f"User logged in successfully: {user.email}", extra={"user_id": user.id})
    access_token = await Create_Access_Token(data={"sub" : str(user.id)}) # sub means subject (user id) ,  jwt can't encode UUID directly so we convert it to string

    return {"access_token": access_token, "token_type": "bearer"}
    
    
