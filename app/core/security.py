from jose import jwt
from core.logging_config import logger
from datetime import datetime, timedelta, timezone
from app.core.config import settings 
from app.schemas import TokenData
from fastapi import HTTPException, status, Depends
from pydantic import ValidationError
from uuid import UUID
from core.request_id import get_request_id
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login") # the url to get the token 




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


async def validate_token_payload (token: str) -> TokenData: # how ? by using the public key to decode the token
    # Define the exception to raise if credentials are invalid, credentials or the token is not valid
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,# 401 means unauthorized
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, # the token to decode
            settings.public_key, # the public key
            algorithms=[settings.ALGORITHM] # the algorithm to use , jwt.decode expects a list of algorithms so [settings.ALGORITHM]
        )
        user_id = payload.get("sub") # get the user id from the payload
        if user_id is None:
            logger.error("User ID not found in token payload", extra={"request_id": get_request_id()})
            raise credentials_exception 
        return TokenData(user_id=user_id) # return the token data object with the user id
    except (jwt.JWTError, ValidationError): # this is for JWT errors or validation errors
        logger.warning("JWT Error occurred while verifying access token", extra={"request_id": get_request_id()})
        raise credentials_exception
    except Exception as e: # this is for any other unexpected errors
        logger.error(f"An unexpected error occurred while verifying access token: {e}", extra={"request_id": get_request_id()})
        raise credentials_exception 

    

 # method for getting the authenticated user for routes
async def get_auth_user(token: str = Depends(oauth2_scheme)) -> TokenData: # depends here means that the function will be called when the route is accessed
    return await validate_token_payload(token) # return the validated token payload