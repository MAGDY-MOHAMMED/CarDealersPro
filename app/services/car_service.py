from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import Car, CarRating,User,UserRating
from app.utils.query_helpers import apply_filters
from typing import Dict

async def get_filtered_cars(db: AsyncSession,params: Dict, limit: int,offset : int):
    query = select(
        Car,
        User.full_name.label('owner_name'), #same as 
        func.count(CarRating.id).label('ratings_count'),
        func.avg(CarRating.rating).label('average_rating')
    ).join(
        User,
        Car.owner_id == User.id
    ).join( # Join with CarRating to get ratings data
        CarRating, 
        Car.id == CarRating.car_id,
        isouter=True # Use left join to include cars without ratings
    ).where(
        Car.is_deleted == False
        ).group_by(Car.id,User.id)
    # handle the owner_id before sending to the filter
    if params.get("owner_id"):
        query = query.where(Car.owner_id == params["owner_id"])
        #time to delete it so it cannot be dubplicated
        params = params.copy() #we don't want to modify the original params
        params.pop("owner_id") #remove it from the params
    query = await apply_filters(query,
     Car, 
     params,
     search_fields=[
        "brand",
        "model", 
        "color"        
    ])
    result = await db.execute(query.limit(limit).offset(offset))
    return result.all()

