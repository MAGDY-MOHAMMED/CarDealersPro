from uuid import UUID
from http import HTTPStatus
from fastapi import Depends, APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_auth_user
from app.database import get_write_db
from app.core.request_id import get_request_id
from app.core.logging_config import logger
from app.models import Car, CarRating
from app.schemas import TokenData, RatingBase
from app.core.auth import UserRole
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException, InternalServerException


router = APIRouter(
    prefix="/ratings",
    tags=["Ratings"]
)


# we need to rate the car with specific id 
@router.post("/rate-car/{car_id}", status_code=HTTPStatus.CREATED)
async def rate_car(
    car_id: UUID,
    rating: RatingBase,
    current_user: TokenData = Depends(get_auth_user),
    db: AsyncSession = Depends(get_write_db)
):
    # check if the user is inspector
    if current_user.role != UserRole.INSPECTOR.value:
        raise ForbiddenException(
            message="عفواً، خدمة تقييم الفحص متاحة للفنيين المعتمدين فقط"
        )
    #  we need to get the car by id
    car = await db.get(Car,car_id) #
    if not car:
        logger.error("Car not found", extra={"request_id": get_request_id()})
        raise NotFoundException("Car", str(car_id))
    existing_rating = await db.execute(
        select(CarRating).where(
            CarRating.car_id == car_id,
            CarRating.user_id == current_user.user_id,
        )
    )
    if existing_rating.scalar_one_or_none():
        raise ConflictException(
            message="Rating already exists for this inspector and car",
            details={"car_id": str(car_id), "user_id": str(current_user.user_id)},
        )

    new_rating = CarRating(
        car_id=car_id,
        user_id=current_user.user_id,
        value_score=rating.value_score,
        comment=rating.comment,
        is_ai_generated=False
    )
    db.add(new_rating)
    try :
        await db.commit()
        await db.refresh(new_rating)
        return new_rating
    except Exception as e:
        await db.rollback()
        logger.error("Error rating car", extra={"request_id": get_request_id(), "error": str(e)})
        raise InternalServerException(
            message="Error rating car",
            details={"error": str(e)}
        )




