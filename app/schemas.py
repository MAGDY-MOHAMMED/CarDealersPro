from pydantic import BaseModel, ConfigDict , EmailStr
from uuid import UUID
from pydantic_partial import create_partial_model
from datetime import datetime

class CarsBase(BaseModel):
    brand : str
    model : str
    year : int
    price : float

# i will use RS256 algorithm and .pem file to store the public key and private key and to be ordered

class CarCreate(CarsBase):
    pass  

class CarResponse(CarsBase): # when pydantic validates the data, it will convert the UUID object to a string
    id : UUID
    owner_id : UUID | None = None
    owner_name: str | None = None
    created_at : datetime
    model_config = ConfigDict(from_attributes=True) # عشان يتعامل مع DB Objects as a dictionary , from_attributes means it will convert the DB Object to a dictionary
# i want to use UUID in the response to identify the car

class UserBase(BaseModel):
    email : EmailStr
    full_name : str 

class UserCreate(UserBase):
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




CarUpdate = create_partial_model(CarsBase) # this will create a model that has all the fields of CarsBase but all of them are optional