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
from app.models import Car , User , CarRating
from app.schemas import CarUpdate, CarsBase, CarResponse , CarUpdate , UserCreate , UserResponse , TokenData , CarCreate , RatingBase , UserRole
from app.utils import get_password_hash, verify_password
from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy
from app.services.car_service import get_filtered_cars
from sqlalchemy import select


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
    db: AsyncSession = Depends(get_db)
):
    # check if the user is inspector
    if current_user.role != UserRole.INSPECTOR.value:
        raise HTTPException(
            status_code=403, 
            detail="عفواً، خدمة تقييم الفحص متاحة للفنيين المعتمدين فقط"
        )
    #  we need to get the car by id
    car = await db.get(Car,car_id) #
    if not car:
        logger.error("Car not found", extra={"request_id": get_request_id()})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found")
    new_rating = CarRating(
        car_id=car_id,
        user_id=current_user.user_id,
        value_score=rating.value_score,
        comment=rating.comment,
        is_ai_generated=False # if human
    )
    db.add(new_rating)
    try :
        await db.commit()
        await db.refresh(new_rating)
        return new_rating
    except Exception as e:
        await db.rollback()
        logger.error("Error rating car", extra={"request_id": get_request_id(), "error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error rating car")




