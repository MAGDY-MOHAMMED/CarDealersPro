import sys
from pathlib import Path
from app.core.security import get_auth_user
from starlette.routing import Router
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
from app.models import Car , User , CarRating, UserRating
from core.auth import UserRole  
from app.schemas import CarUpdate, CarsBase, CarResponse , CarUpdate , UserCreate , UserResponse , TokenData , CarCreate , RatingBase   
from app.utils import get_password_hash, verify_password
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy 
from app.services.car_service import get_filtered_cars
from sqlalchemy import select , or_, func




router = APIRouter(
    prefix="/cars",  #  the url will be /cars
    tags=["Cars"],    #  this router is for cars
)



@router.get("/", response_model=list[CarResponse]) # to get all cars
async def get_all_cars (
    db: AsyncSession = Depends(get_db), 
    current_user: TokenData = Depends(get_auth_user),
    brand : str | None = None,
    owner_id: uuid.UUID | None = None,
    max_price : float | None = None,
    search : str | None = None,
    color : str | None = None,
    limit : int = 20, 
    offset : int = 0 #offset means the number of cars to skip
    ):# db is a dependency that will be injected by FastAPI means that we will use the db variable to access the database and depends means that the function will be called when the dependency is needed

    filter_params = {
        "brand": brand,
        "price": max_price,
        "search": search,
        "color": color,
        "owner_id": owner_id # so the admin could see the cars
    }
    rows = await get_filtered_cars(db, filter_params, limit, offset)
    # here we return a list of CarResponse objects
    return [
        CarResponse(
            **row.Car.__dict__, # take the car object and convert it to a dictionary why ? because CarResponse is a Pydantic model and we need to pass the car object as a dictionary
            owner_name=row.owner_name, # add the owner name to the response
            ratings_count=row.ratings_count, 
            average_rating=float(row.average_rating) if row.average_rating else 0.0
        )
        for row in rows
    ]


@router.get("/my_cars", response_model=list[CarResponse])
async def get_my_cars(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_auth_user)
):
    query = select(
        Car,
        User.full_name.label("owner_name"),
        func.count(CarRating.car_id).label("ratings_count"), # same in CarResponse schema so 
        func.avg(CarRating.value_score).label("average_rating") # same in CarResponse schema
    ).select_from(Car).join(
        User, 
        Car.owner_id == User.id, # Join مع اليوزر
    ).join(
        CarRating ,
        Car.id == CarRating.car_id,
        isouter=True # means left join, will show the car even if it has no ratings
    ).where(
        Car.owner_id == current_user.user_id, # only get cars owned by the current user
        Car.is_deleted == False
    ).group_by(Car.id, User.id)

    result = await db.execute(query)
    rows = result.all()
    logger.info(f"Retrieved {len(rows)} cars for user {current_user.user_id}", extra={"request_id": get_request_id()})
    return [
        CarResponse(
            **row.Car.__dict__, # take the car object and convert it to a dictionary why ? because CarResponse is a Pydantic model and we need to pass the car object as a dictionary
            owner_name=row.owner_name, # add the owner name to the response
            ratings_count=row.ratings_count, 
            average_rating=float(row.average_rating) if row.average_rating else 0.0
        ) 
        for row in rows
    ]

@router.get("/{id}", response_model=CarResponse) #get any car by id , response_model=CarResponse means that the response will be in the format of the CarResponse model
async def get_any_car_by_id(
    id: uuid.UUID, 
    db : AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_auth_user)
): # it turns to UUID object automatically
    query = select(
        Car,
        User.full_name.label("owner_name"),
        func.count(CarRating.id).label("ratings_count"), # عدد التقييمات
        func.avg(CarRating.value_score).label("average_rating") # متوسط التقييم
    ).join(
        User, # join the car table with the user table
        Car.owner_id == User.id # join the car table with the user table
    ).join(
        CarRating, Car.id == CarRating.car_id, isouter=True 
    ).where(
        Car.id == id, # get the car with the given id
        Car.is_deleted == False
    ).group_by(Car.id,User.full_name) # 
    result = await db.execute(query)
    row = result.first() # it returns a tuple (car, owner_name) or None
    if not row:
        logger.warning("Car not found", extra={"car_id": str(id), "request_id": get_request_id()})
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=f"car with id {id} doesn't exist") #don't forget the statuscode 
    return CarResponse( #return the car reponse object to dict
        **row.Car.__dict__, #
        owner_name=row.owner_name, # add the owner name to the response
        ratings_count=row.ratings_count, # add the ratings count to the response
        average_rating=float(row.average_rating) if row.average_rating else 0.0 # add the average rating to the response
    ) # return the post as a Pydantic model(dict)








@router.post("/", status_code=HTTPStatus.CREATED, response_model=CarResponse) # to create cars
async def create_cars (
    car: CarCreate, # CarCreate is a Pydantic model that will validate the request body
    db : AsyncSession = Depends(get_db) ,
    current_user: TokenData = Depends(get_auth_user)
    ): # the difference between car and my_car is that car is a Pydantic model and my_car is a list of dictionaries , get_auth_user is the authenticated user which have all the data in tokens if we need to add more data like user_id or other data we can use get_auth_user

    new_car_data = car.model_dump(exclude_unset=True)# convert the car object to a dictionary, exclude_unset=True means that if the field is not set, it will be excluded from the dictionary
    user_role = current_user.role.lower()  # current_user.role is always string from token payload
    if user_role == "client" or not new_car_data.get("price_dealer"): # if the user is a client or the price_dealer is not set, set the price_dealer to the price_consumer
        new_car_data["price_dealer"] = new_car_data.get("price_consumer")
    new_car_data["owner_id"] = current_user.user_id
    new_car = Car (**new_car_data)# create a new car object with the updated data , ** means unpacking the dictionary

    db.add(new_car)
    await db.commit()  # commit the transaction
    await db.refresh(new_car) # refresh the car object to get the id
    logger.info(f"Car created successfully", extra={"car_id": str(new_car.id), "request_id": get_request_id()})
    return new_car # return the new car




@router.put("/{id}" , response_model=CarResponse) #update car
async def update_car(
    id : UUID ,
    car_update : CarUpdate,
    db : AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_auth_user)
    ):
    query = select(Car).where(
        Car.id == id,
        Car.is_deleted == False,
        or_(
            Car.owner_id == current_user.user_id,
            current_user.role == UserRole.ADMIN.value
        )
    )
    result = await db.execute(query)
    car = result.scalar_one_or_none() # get the car
    if not car:
        logger.warning("Car not found", extra={"car_id": str(id), "request_id": get_request_id()})
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=f"car with id {id} doesn't exist")
    updated_data = car_update.model_dump(exclude_unset=True) # exclude_unset=True means that we don't want to update the fields that are not provided , model_dump converts the Pydantic model to a dictionary
    if not updated_data:
        logger.error("No fields to update", extra={"car_id": str(id), "request_id": get_request_id()})
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="No fields to update")
    for key, value in updated_data.items():# update the car
        setattr(car, key, value) # set the attributes of the car
    await db.commit()
    await db.refresh(car) # refresh the car to get the updated data
    logger.info(f"Car updated successfully", extra={"car_id": str(id), "request_id": get_request_id()})
    return car # return the updated car




@router.delete("/{id}", status_code= status.HTTP_204_NO_CONTENT) # delete car
async def delete_car(
    id:uuid.UUID, 
    db :AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_auth_user)
    ):
    query = await db.execute(select(Car).where(
        Car.id == id,
        Car.is_deleted == False,
        or_(
            Car.owner_id == current_user.user_id,
            current_user.role == UserRole.ADMIN.value
        )
    )) # get the car
    car = query.scalar_one_or_none() # get the car
    if not car:
        logger.warning("Car not found", extra={"car_id": str(id), "request_id": get_request_id()})
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=f"car with id {id} doesn't exist")
    car.is_deleted = True
    await db.commit()
    logger.info(f"Car deleted successfully", extra={"car_id": str(id), "request_id": get_request_id()})
    return Response(status_code=HTTPStatus.NO_CONTENT)


