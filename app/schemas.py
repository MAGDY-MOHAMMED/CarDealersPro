from pydantic import BaseModel, ConfigDict , EmailStr, Field
from uuid import UUID
from pydantic_partial import create_partial_model
from datetime import datetime
from typing import Optional
from core.auth import UserRole

class CarsBase(BaseModel):
    brand : str
    model : str
    year : int
    price_consumer : float
    price_dealer : Optional[float] = None
    color : str | None = None

# i will use RS256 algorithm and .pem file to store the public key and private key and to be ordered

class CarCreate(CarsBase): # this model is used to create a car
    pass  

class CarResponse(CarsBase): # when pydantic validates the data, it will convert the UUID object to a string
    id : UUID
    owner_id : UUID | None = None
    owner_name: str | None = None
    ratings_count : int = 0
    average_rating: float | None
    created_at : datetime
    model_config = ConfigDict(from_attributes=True) # عشان يتعامل مع DB Objects as a dictionary , from_attributes means it will convert the DB Object to a dictionary
# i want to use UUID in the response to identify the car

class UserBase(BaseModel):
    email : EmailStr
    full_name : str 
    role: UserRole = UserRole.CLIENT 


class UserCreate(UserBase): # we don't want to expose the password in the response
    password : str



class UserResponse(UserBase):
    id : UUID
    created_at : datetime
    model_config = ConfigDict(from_attributes=True)
# i want to use UUID in the response to identify the user

class UserLogin(BaseModel):
    email : EmailStr
    password : str # we need to authenticate the user


class Token(BaseModel): # why not UserBase? 
    access_token : str # we need to specify the access token
    token_type : str # we need to specify the type of the token


class TokenData(BaseModel):
    user_id : UUID | None = None
    role : str | None = None


class RatingBase(BaseModel):
    value_score: int = Field(..., ge=0, le=100, description="Trust score from 0 to 100")  # ge means greater than or equal, le means less than or equal, ... means required
    comment: str | None = Field(None, description="Optional comment about the rating")



CarUpdate = create_partial_model(CarsBase) # this will create a model that has all the fields of CarsBase but all of them are optional