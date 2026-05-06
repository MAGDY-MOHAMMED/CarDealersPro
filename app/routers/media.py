from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pathlib import Path
import os
import uuid
from typing import List
from app.database import get_db
from app.models import Car, CarMedia, MediaType
from app.schemas import CarMediaCreate, CarMediaResponse
from app.core.security import get_auth_user
from core.logging_config import logger
from core.request_id import get_request_id

router = APIRouter(
    prefix="/media",
    tags=["Media"]
)

# Storage configuration
STORAGE_BASE_DIR = Path("storage/uploads")
IMAGES_DIR = STORAGE_BASE_DIR / "images"
VIDEOS_DIR = STORAGE_BASE_DIR / "videos"

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Maximum file size (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024


def get_media_type_from_filename(filename: str) -> MediaType:
    """Determine media type from file extension"""
    ext = Path(filename).suffix.lower() # suffix means extension means the file extension, why lower() ? because we want to compare the extension in lowercase
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return MediaType.IMAGE
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        return MediaType.VIDEO
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension: {ext}"
        )


def get_storage_directory(media_type: MediaType) -> Path:
    """Get the appropriate storage directory based on media type"""
    if media_type == MediaType.IMAGE:
        return IMAGES_DIR
    else:
        return VIDEOS_DIR


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename to avoid conflicts"""
    ext = Path(original_filename).suffix # suffix means extension means the file extension
    unique_id = str(uuid.uuid4())
    return f"{unique_id}{ext}" # return the unique filename with the extension


@router.post("/upload/{car_id}", response_model=CarMediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_car_media(
    car_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_auth_user)
):
    """
    Upload media (image or video) for a specific car.
    Files are automatically routed to the appropriate directory:
    - Images → storage/uploads/images/
    - Videos → storage/uploads/videos/
    """
    request_id = get_request_id()

    # Check if car exists
    result = await db.execute(select(Car).where(Car.id == car_id))
    car = result.scalar_one_or_none()
    if not car:
        logger.warning(f"Car not found for media upload", extra={"car_id": str(car_id), "request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Car not found"
        )

    # Validate file size
    file_content = await file.read() # read the file content
    if len(file_content) > MAX_FILE_SIZE:
        logger.warning(f"File too large", extra={"size": len(file_content), "request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024 * 1024)}MB"
        )

    # Determine media type
    try:
        media_type = get_media_type_from_filename(file.filename) # get the media type from the filename
    except HTTPException as e:
        logger.warning(f"Invalid file type", extra={"filename": file.filename, "request_id": request_id})
        raise e

    # Get storage directory
    storage_dir = get_storage_directory(media_type) # get the storage directory based on the media type

    # Ensure directory exists
    storage_dir.mkdir(parents=True, exist_ok=True) # create the directory if it doesn't exist

    # Generate unique filename
    unique_filename = generate_unique_filename(file.filename) # generate a unique filename to avoid conflicts
    file_path = storage_dir / unique_filename

    # Save file
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        logger.info(f"File saved successfully", extra={"path": str(file_path), "request_id": request_id})
    except Exception as e:
        logger.error(f"Failed to save file", extra={"error": str(e), "request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file"
        )

    # Create media URL (relative path for storage)
    media_url = f"/storage/uploads/{media_type.value}s/{unique_filename}" # create the media url

    # Create database record
    media_data = CarMediaCreate(
        car_id=car_id,
        media_url=media_url,
        media_type=media_type
    )

    new_media = CarMedia(**media_data.model_dump()) # create a new media object
    db.add(new_media)
    await db.commit()
    await db.refresh(new_media)

    logger.info(f"Media uploaded successfully", extra={"media_id": str(new_media.id), "request_id": request_id})

    return new_media


@router.get("/car/{car_id}", response_model=List[CarMediaResponse])
async def get_car_media(
    car_id: UUID,
    media_type: MediaType = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_auth_user)
):
    """
    Get all media for a specific car.
    Optionally filter by media type (image or video).
    """
    request_id = get_request_id()

    # Check if car exists
    result = await db.execute(select(Car).where(
        Car.id == car_id,
        Car.is_deleted == False
    ))
    car = result.scalar_one_or_none()
    if not car:
        logger.warning(f"Car not found", extra={"car_id": str(car_id), "request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Car not found"
        )

    # Build query
    query = select(CarMedia).where(CarMedia.car_id == car_id)
    if media_type:
        query = query.where(CarMedia.media_type == media_type)

    # Order by creation date (newest first)
    query = query.order_by(CarMedia.created_at.desc()) # order by creation date (newest first)

    result = await db.execute(query)
    media_items = result.scalars().all()

    logger.info(f"Retrieved media for car", extra={"car_id": str(car_id), "count": len(media_items), "request_id": request_id})

    return media_items


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_auth_user)
):
    """
    Delete a media file and its database record.
    """
    request_id = get_request_id()

    # Get media record
    result = await db.execute(select(CarMedia).where(CarMedia.id == media_id))
    media = result.scalar_one_or_none()
    if not media:
        logger.warning(f"Media not found", extra={"media_id": str(media_id), "request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )

    # Delete file from storage
    try:
        file_path = Path(media.media_url.lstrip("/")) # strip the leading slash to get the relative path
        if file_path.exists():
            os.remove(file_path)
            logger.info(f"File deleted", extra={"path": str(file_path), "request_id": request_id})
    except Exception as e:
        logger.error(f"Failed to delete file", extra={"error": str(e), "request_id": request_id})
        # Continue with database deletion even if file deletion fails

    # Delete database record
    await db.delete(media)
    await db.commit()

    logger.info(f"Media deleted successfully", extra={"media_id": str(media_id), "request_id": request_id})
