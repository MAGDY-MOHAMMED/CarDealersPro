from fastapi import FastAPI, HTTPException, status, Response
from pydantic import BaseModel, ConfigDict # for pydantic v2
import uuid
from uuid import UUID
from pydantic_partial import create_partial_model
from http import HTTPStatus
import logging
import psycopg
from psycopg.rows import dict_row
from fastapi import Depends
from app.database import connect_to_db , get_db




app = FastAPI(title="Car Dealers Pro API")



class CarsBase(BaseModel):
    brand : str
    model : str
    year : int
    price : float

class CarResponse(CarsBase): # when pydantic validates the data, it will convert the UUID object to a string
    id : UUID
    model_config = ConfigDict(from_attributes=True) # عشان يتعامل مع DB Objects as a dictionary


CarUpdate = create_partial_model(CarsBase)





@app.get("/")
async def root ():
    return {"status": "Online", "engine": "CarDealers Pro API"}


@app.get("/cars", response_model=list[CarResponse]) # to read posts
async def get_all_cars (db = Depends(get_db)):# db is a dependency that will be injected by FastAPI means that we will use the db variable to access the database and depends means that the function will be called when the dependency is needed
    with db.cursor() as cursor:
        cursor.execute ("""
            SELECT * 
            FROM cars
        """)
    return cursor.fetchall()



@app.get("/cars/{id}", response_model=CarResponse) # response_model=Post means that the response will be in the format of the Post model
async def get_car_by_id(id: uuid.UUID, db = Depends(get_db)): # it turns to UUID object automatically
    with db.cursor() as cursor:
        cursor.execute ("""
            SELECT * 
            FROM cars 
            WHERE id = %s
        """, (str(id),)) # str(id) is used to convert the UUID object to a string why ? because the database expects a string
        car = cursor.fetchone() # fetchone() returns a tuple
    if not car:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=f"car with id {id} doesn't exist") #don't forget the statuscode 
    return car # return the post as a Pydantic model

@app.post("/cars", status_code=HTTPStatus.CREATED, response_model=CarResponse) # status_code=201 is the status code for created  # to create posts
async def create_cars (car : CarsBase, db = Depends(get_db)): # the difference between car and my_car is that car is a Pydantic model and my_car is a list of dictionaries
    with db.cursor() as cursor: # db.cursor() returns a cursor object that we can use to execute SQL queries
        cursor.execute ("""
            INSERT INTO cars (brand, model, year, price) 
            VALUES (%s, %s, %s, %s) 
            RETURNING * 
        """, (car.brand, car.model, car.year, car.price)) # why ? because the database expects a string, why (car.brand, car.model, car.year, car.price) ?
        new_car = cursor.fetchone()
        db.commit()
    return new_car # return the new car





@app.delete("/cars/{id}", status_code= status.HTTP_204_NO_CONTENT)
async def delete_car(id:uuid.UUID, db = Depends(get_db)):
    with db.cursor() as cursor:
        cursor.execute ("""
            DELETE FROM cars 
            WHERE id = %s 
            RETURNING id
        """, (str(id),)) # str(id) is used to convert the UUID object to a string why ? because the database expects a string
        deleted_car = cursor.fetchone()
        db.commit() # commit the transaction
    if not deleted_car:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=f"car with id {id} doesn't exist")
    
    return Response(status_code=HTTPStatus.NO_CONTENT)

@app.put("/cars/{id}" , response_model=CarResponse) #update post
async def update_car(id : UUID ,car_update : CarUpdate, db = Depends(get_db)):
    updated_data = car_update.model_dump(exclude_unset=True) # exclude_unset=True means that we don't want to update the fields that are not provided
    if not updated_data:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="No fields to update")
    #why """ + ",".join([f"{k} = %s" for k in updated_data.keys()]) + """ ?
    # because we want to update the fields that are provided
    set_clause = ", ".join([f"{k} = %s" for k in updated_data.keys()]) # update the required fields to the query
    query = (
    """
        UPDATE cars 
        SET {set_clause} 
        WHERE id = %s 
        RETURNING *
    """
    )
    
    params = [*updated_data.values(), id] # the execute method expects a list of values
    with db.cursor() as cursor:
        cursor.execute(query, params)
        updated_car = cursor.fetchone() # fetchone() returns a tuple (row of data) from the database
        db.commit()
    if not updated_car:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND,detail= f"car with id {id} doesn't exist")
    return updated_car # return the updated car





