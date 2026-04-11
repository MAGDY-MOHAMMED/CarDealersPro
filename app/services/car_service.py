from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Car , User 

async def get_filtered_cars(db: AsyncSession, brand, max_price,limit,offset):
    query = select(Car,User.full_name.label("owner_name")).join(User, Car.owner_id == User.id).where(Car.is_deleted == False)

    if brand:# Filter by brand (case-insensitive partial match)
        query = query.where(Car.brand.ilike(f"%{brand}%"))
    if max_price:# Filter by maximum price
        query = query.where(Car.price <= max_price) # Filter by maximum price
    result = await db.execute(query.limit(limit).offset(offset))
    return result.all()

