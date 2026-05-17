from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.core.logging_config import logger
from app.core.config import settings
from app.core.request_id import get_request_id
from app.core.exceptions import UnauthorizedException
from app.schemas import TokenData
from fastapi import Depends
from pydantic import ValidationError
from uuid import UUID
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")




async def Create_Access_Token(data: dict) -> str:
    to_encode = data.copy()
    if "sub" in to_encode and isinstance(to_encode["sub"], UUID): # why ? because the id is UUID and jwt can't encode it , RFC 7519
        to_encode["sub"] = str(to_encode["sub"]) # convert the UUID to string so to be able to encode it
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire}) # add expiration 
    encoded_jwt = jwt.encode(
        to_encode, # the data to encode
        settings.private_key, # the private key
        algorithm=settings.ALGORITHM # the algorithm to use , why  not [] ? because jwt.encode expects a single algorithm string, not a list
    )
    return encoded_jwt # return the token


async def validate_token_payload(token: str) -> TokenData:
    credentials_exception = UnauthorizedException("Could not validate credentials")
    try:
        payload = jwt.decode(
            token, # the token to decode
            settings.public_key, # the public key
            algorithms=[settings.ALGORITHM] # the algorithm to use , jwt.decode expects a list of algorithms so [settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        role = payload.get("role")
        if user_id is None or role is None:
            logger.error("Token payload is missing required claims", extra={"request_id": get_request_id()})
            raise credentials_exception
        return TokenData(user_id=user_id, role=role)
    except (JWTError, ValidationError):
        logger.warning("JWT validation failed", extra={"request_id": get_request_id()})
        raise credentials_exception
    except Exception as e: # this is for any other unexpected errors
        logger.error(f"An unexpected error occurred while verifying access token: {e}", extra={"request_id": get_request_id()})
        raise credentials_exception 



 # method for getting the authenticated user for routes
async def get_auth_user(token: str = Depends(oauth2_scheme)) -> TokenData: # depends here means that the function will be called when the route is accessed
    return await validate_token_payload(token) # return the validated token payload