import uuid
from uuid import UUID
from http import HTTPStatus
from fastapi import status, Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from app.core.security import get_auth_user
from app.database import get_read_db, get_write_db
from app.core.request_id import get_request_id
from app.core.logging_config import logger
from app.models import Car, User, CarRating, UserRole
from app.core.config import SUBSCRIPTION_LIMITS
from app.schemas import CarUpdate, CarResponse, TokenData, CarCreate
from app.services.car_service import get_filtered_cars
from app.utils.filter_builder import build_filter_query
from app.core.exceptions import NotFoundException, BadRequestException




router = APIRouter(
    prefix="/cars",
    tags=["Cars"],
)


def _serialize_car_row(row) -> CarResponse:
    return CarResponse(
        **row.Car.__dict__,
        owner_name=row.owner_name,
        ratings_count=row.ratings_count or 0,
        average_rating=float(row.average_rating) if row.average_rating is not None else 0.0,
    )



@router.get("/") # to get all cars with pagination
async def get_all_cars (
    db: AsyncSession = Depends(get_read_db),  # Use read-only database for GET
    current_user: TokenData = Depends(get_auth_user),
    brand : str | None = None,
    owner_id: uuid.UUID | None = None,
    max_price : float | None = None,
    search : str | None = None,
    color : str | None = None,
    page : int = 1,
    page_size : int = 20,
    sort_by: str = "created_at",
    order: str = "desc"
    ):# db is a dependency that will be injected by FastAPI means that we will use the db variable to access the database and depends means that the function will be called when the dependency is needed

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    limit = page_size
    offset = (page - 1) * page_size

    filter_params = {
        "brand": brand,
        "price": max_price,
        "search": search,
        "color": color,
        "owner_id": owner_id # so the admin could see the cars
    }
    rows = await get_filtered_cars(db, filter_params, limit, offset, sort_by, order)

    # Build count query using build_filter_query
    count_query = select(func.count(Car.id)).where(Car.is_deleted == False)

    # Build count filters dict (excluding search)
    count_filters = {
        "brand": brand,
        "price": max_price,
        "color": color,
        "owner_id": owner_id
    }

    # Remove None values
    count_filters = {k: v for k, v in count_filters.items() if v is not None}

    count_query = build_filter_query(count_query, Car, count_filters, search_fields=["brand", "model", "color"])

    # Handle search separately for count query
    if search:
        count_query = count_query.where(
            or_(
                Car.brand.ilike(f"%{search}%"),
                Car.model.ilike(f"%{search}%"),
                Car.color.ilike(f"%{search}%")
            )
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate pagination metadata
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    has_next = page < total_pages
    has_previous = page > 1

    # here we return paginated response
    return {
        "items": [_serialize_car_row(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": has_next,
        "has_previous": has_previous
    }


@router.get("/my_cars", response_model=list[CarResponse])
async def get_my_cars(
    db: AsyncSession = Depends(get_read_db),  # Use read-only database for GET
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
    return [_serialize_car_row(row) for row in rows]

@router.get("/{id}", response_model=CarResponse) #get any car by id , response_model=CarResponse means that the response will be in the format of the CarResponse model
async def get_car(
    id: UUID,
    db: AsyncSession = Depends(get_read_db),  # Use read-only database for GET
    current_user: TokenData = Depends(get_auth_user)
): # it turns to UUID object automatically
    query = select(
        Car,
        User.full_name.label("owner_name"),
        func.count(CarRating.car_id).label("ratings_count"),
        func.avg(CarRating.value_score).label("average_rating")
    ).join(
        User,
        Car.owner_id == User.id,
        isouter=True
    ).join(
        CarRating, Car.id == CarRating.car_id, isouter=True
    ).where(
        Car.id == id,
        Car.is_deleted.is_(False)
    ).group_by(Car.id, User.id)
    result = await db.execute(query)
    row = result.first() # it returns a tuple (car, owner_name) or None
    if not row:
        logger.warning("Car not found", extra={"car_id": str(id), "request_id": get_request_id()})
        raise NotFoundException("Car", str(id)) 
    return _serialize_car_row(row)








@router.post("/", status_code=HTTPStatus.CREATED, response_model=CarResponse) # to create cars
async def create_cars (
    car: CarCreate, # CarCreate is a Pydantic model that will validate the request body
    db : AsyncSession = Depends(get_write_db),  # Use write database for POST
    current_user: TokenData = Depends(get_auth_user)
    ): # the difference between car and my_car is that car is a Pydantic model and my_car is a list of dictionaries , get_auth_user is the authenticated user which have all the data in tokens if we need to add more data like user_id or other data we can use get_auth_user

    new_car_data = car.model_dump(exclude_unset=True)# convert the car object to a dictionary, exclude_unset=True means that if the field is not set, it will be excluded from the dictionary
    owner = await db.get(User, current_user.user_id)
    if not owner:
        raise NotFoundException("User", str(current_user.user_id))
    user_role = current_user.role.lower()  # current_user.role is always string from token payload
    if owner.role == UserRole.DEALER:
        await db.refresh(owner)
        max_limit = SUBSCRIPTION_LIMITS.get((owner.subscription_plan or "FREE").upper(), SUBSCRIPTION_LIMITS["FREE"])
        if owner.inventory_count >= max_limit:
            raise BadRequestException(message=f"Maximum vehicle limit ({max_limit}) reached for {owner.subscription_plan} plan")
    if user_role == "client" or not new_car_data.get("price_dealer"): # if the user is a client or the price_dealer is not set, set the price_dealer to the price_consumer
        new_car_data["price_dealer"] = new_car_data.get("price_consumer")
    new_car_data["owner_id"] = current_user.user_id
    new_car = Car (**new_car_data)# create a new car object with the updated data , ** means unpacking the dictionary

    db.add(new_car)
    if owner.role == UserRole.DEALER:
        owner.inventory_count += 1
    await db.commit()  # commit the transaction
    await db.refresh(new_car) # refresh the car object to get the id
    logger.info(f"Car created successfully", extra={"car_id": str(new_car.id), "request_id": get_request_id()})
    return new_car # return the new car




@router.put("/{id}" , response_model=CarResponse) #update car
async def update_car(
    id : UUID ,
    car_update : CarUpdate,
    db : AsyncSession = Depends(get_write_db),
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
        raise NotFoundException("Car", str(id))
    updated_data = car_update.model_dump(exclude_unset=True) # exclude_unset=True means that we don't want to update the fields that are not provided , model_dump converts the Pydantic model to a dictionary
    if not updated_data:
        logger.error("No fields to update", extra={"car_id": str(id), "request_id": get_request_id()})
        raise BadRequestException(
            message="No fields to update",
            details={"car_id": str(id)}
        )
    for key, value in updated_data.items():# update the car
        setattr(car, key, value) # set the attributes of the car
    await db.commit()
    await db.refresh(car) # refresh the car to get the updated data
    logger.info(f"Car updated successfully", extra={"car_id": str(id), "request_id": get_request_id()})
    return car # return the updated car




@router.delete("/{id}", status_code= status.HTTP_204_NO_CONTENT) # delete car
async def delete_car(
    id: UUID,
    db :AsyncSession = Depends(get_write_db),
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
        raise NotFoundException("Car", str(id))
    car.is_deleted = True
    owner = await db.get(User, car.owner_id) if car.owner_id else None
    if owner and owner.role == UserRole.DEALER and owner.inventory_count > 0:
        owner.inventory_count -= 1
    await db.commit()
    logger.info(f"Car deleted successfully", extra={"car_id": str(id), "request_id": get_request_id()})
    return Response(status_code=HTTPStatus.NO_CONTENT)


