from fastapi import APIRouter, Depends, UploadFile, File, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pathlib import Path
import os
import shutil
import uuid
import aiofiles
import magic
from typing import List
from app.database import get_read_db, get_write_db
from app.models import Car, CarMedia, MediaType
from app.schemas import CarMediaCreate, CarMediaResponse, TokenData
from app.core.security import get_auth_user
from app.core.request_id import set_request_id, generate_request_id, get_request_id
from app.core.logging_config import logger
from app.core.tasks import compress_image, create_video_thumbnail
from app.core.exceptions import NotFoundException, BadRequestException, InsufficientStorageException, InternalServerException, ForbiddenException
from app.utils.filter_builder import build_filter_query
from app.models import UserRole

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

# Allowed MIME types for magic validation
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_MIME_TYPES = {"video/mp4", "video/avi", "video/quicktime", "video/x-matroska", "video/webm"}

# Maximum file size (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024

# Minimum disk space required (1GB)
MIN_DISK_SPACE = 1 * 1024 * 1024 * 1024


def get_media_type_from_filename(filename: str) -> MediaType:
    """Determine media type from file extension"""
    ext = Path(filename).suffix.lower() # suffix means extension means the file extension, why lower() ? because we want to compare the extension in lowercase
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return MediaType.IMAGE
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        return MediaType.VIDEO
    else:
        raise BadRequestException(
            message=f"Unsupported file extension: {ext}",
            details={"extension": ext}
        )


def validate_file_type_with_magic(file_content: bytes, expected_type: MediaType) -> None:
    """Validate actual file type using magic numbers"""
    mime = magic.Magic(mime=True) # get the mime type
    detected_mime = mime.from_buffer(file_content[:2048])  # Read first 2KB for magic detection

    if expected_type == MediaType.IMAGE:
        if detected_mime not in ALLOWED_IMAGE_MIME_TYPES:
            raise BadRequestException(
                message=f"Invalid file type. Expected image, got: {detected_mime}",
                details={"detected_mime": detected_mime, "expected_type": "image"}
            )
    else:  # VIDEO
        if detected_mime not in ALLOWED_VIDEO_MIME_TYPES:
            raise BadRequestException(
                message=f"Invalid file type. Expected video, got: {detected_mime}",
                details={"detected_mime": detected_mime, "expected_type": "video"}
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


# route for uploading car media
@router.post("/upload/{car_id}", response_model=CarMediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_car_media(
    car_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_write_db),
    current_user: TokenData = Depends(get_auth_user)
):
    """
    Upload media (image or video) for a specific car.
    Files are automatically routed to the appropriate directory:
    - Images → storage/uploads/images/
    - Videos → storage/uploads/videos/
    """
    request_id = get_request_id()

    # Check disk space on the actual target filesystem, not the process root
    STORAGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    disk_usage = shutil.disk_usage(STORAGE_BASE_DIR)
    free_space = disk_usage.free
    if free_space < MIN_DISK_SPACE:
        logger.warning(f"Insufficient disk space", extra={"free_space": free_space, "required": MIN_DISK_SPACE, "request_id": request_id})
        raise InsufficientStorageException(
            required=MIN_DISK_SPACE,
            available=free_space
        )

    # Check if car exists
    result = await db.execute(select(Car).where(Car.id == car_id))
    car = result.scalar_one_or_none()
    if not car:
        logger.warning(f"Car not found for media upload", extra={"car_id": str(car_id), "request_id": request_id})
        raise NotFoundException("Car", str(car_id))
    if current_user.role != UserRole.ADMIN.value and car.owner_id != current_user.user_id:
        raise ForbiddenException(message="You are not allowed to upload media for this car")

    # Validate file size
    file_content = await file.read() # read the file content
    if len(file_content) > MAX_FILE_SIZE:
        logger.warning(f"File too large", extra={"size": len(file_content), "request_id": request_id})
        raise BadRequestException(
            message=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024 * 1024)}MB",
            details={"file_size": len(file_content), "max_size": MAX_FILE_SIZE}
        )

    # Reset file position after reading
    await file.seek(0) # seek 0 means go to the beginning of the file

    # Determine media type
    try:
        media_type = get_media_type_from_filename(file.filename) # get the media type from the filename
    except BadRequestException as e:
        logger.warning(f"Invalid file type", extra={"filename": file.filename, "request_id": request_id})
        raise e

    # Validate actual file type using magic numbers
    try:
        validate_file_type_with_magic(file_content, media_type)
        logger.info(f"File type validated with magic", extra={"filename": file.filename, "media_type": media_type.value, "request_id": request_id})
    except BadRequestException as e:
        logger.warning(f"Magic validation failed", extra={"filename": file.filename, "request_id": request_id})
        raise e

    # Get storage directory
    storage_dir = get_storage_directory(media_type) # get the storage directory based on the media type

    # Ensure directory exists
    storage_dir.mkdir(parents=True, exist_ok=True) # create the directory if it doesn't exist

    # Generate unique filename
    unique_filename = generate_unique_filename(file.filename) # generate a unique filename to avoid conflicts
    file_path = storage_dir / unique_filename

    # Save file using async writes
    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            await buffer.write(file_content)
        logger.info(f"File saved successfully", extra={"path": str(file_path), "request_id": request_id})
    except Exception as e:
        logger.error(f"Failed to save file", extra={"error": str(e), "request_id": request_id})
        raise InternalServerException(
            message="Failed to save file",
            details={"error": str(e)}
        )

    # Create media URL (relative path without /storage/ prefix for AWS compatibility)
    # Frontend Note: When displaying media, prepend server URL: https://api.cardealerspro.com/static/ + media_url
    media_url = f"uploads/{media_type.value}s/{unique_filename}" # relative path

    # Create database record
    media_data = CarMediaCreate(
        car_id=car_id,
        media_url=media_url,
        media_type=media_type,
        file_size=len(file_content)
    )

    new_media = CarMedia(**media_data.model_dump()) # create a new media object
    db.add(new_media)

    try:
        await db.commit()
        await db.refresh(new_media)
    except Exception as e:
        # Rollback and delete file if database commit fails
        await db.rollback()
        try:
            os.remove(file_path)
            logger.warning(f"File deleted due to database commit failure", extra={"path": str(file_path), "request_id": request_id})
        except Exception as delete_error:
            logger.error(f"Failed to delete file after database commit failure", extra={"error": str(delete_error), "request_id": request_id})
        logger.error(f"Database commit failed", extra={"error": str(e), "request_id": request_id})
        raise InternalServerException(
            message="Failed to save media record",
            details={"error": str(e)}
        )

    logger.info(f"Media uploaded successfully", extra={"media_id": str(new_media.id), "request_id": request_id})

    # Add background task to compress image (only for images)
    if media_type == MediaType.IMAGE:
        background_tasks.add_task(compress_image, file_path)
    # Add background task to create video thumbnail (only for videos)
    elif media_type == MediaType.VIDEO:
        thumbnail_path = file_path.parent / f"{file_path.stem}_thumb.jpg"
        background_tasks.add_task(create_video_thumbnail, file_path, thumbnail_path)

    return new_media

# route for getting car media
@router.get("/car/{car_id}", response_model=List[CarMediaResponse])
async def get_car_media(
    car_id: UUID,
    media_type: MediaType = None,
    db: AsyncSession = Depends(get_read_db),
    current_user: TokenData = Depends(get_auth_user)
):
    """
    Get all media for a specific car.
    Optionally filter by media type (image or video).
    """
    request_id = get_request_id()

    # Check if car exists
    result = await db.execute(select(Car).where(
        Car.id == car_id,
        Car.is_deleted.is_(False)
    ))
    car = result.scalar_one_or_none()
    if not car:
        logger.warning(f"Car not found", extra={"car_id": str(car_id), "request_id": request_id})
        raise NotFoundException("Car", str(car_id))

    # Build query using build_filter_query
    query = select(CarMedia).where(CarMedia.car_id == car_id)

    # Apply media_type filter if provided
    if media_type:
        query = build_filter_query(query, CarMedia, {"media_type": media_type})

    # Order by creation date (newest first)
    query = query.order_by(CarMedia.created_at.desc()) # order by creation date (newest first)

    result = await db.execute(query)
    media_items = result.scalars().all()

    logger.info(f"Retrieved media for car", extra={"car_id": str(car_id), "count": len(media_items), "request_id": request_id})

    return media_items


# route for deleting media
@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media_id: UUID,
    db: AsyncSession = Depends(get_write_db),
    current_user: TokenData = Depends(get_auth_user)
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
        raise NotFoundException("Media", str(media_id))

    car = await db.get(Car, media.car_id)
    if not car:
        raise NotFoundException("Car", str(media.car_id))
    if current_user.role != UserRole.ADMIN.value and car.owner_id != current_user.user_id:
        raise ForbiddenException(message="You are not allowed to delete media for this car")

    # Delete file from storage (construct full path from relative URL)
    try:
        file_path = Path("storage") / media.media_url  # construct full path from relative URL
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
