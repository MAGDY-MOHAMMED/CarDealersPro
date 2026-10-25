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
def get_min_disk_space_bytes() -> int:
    """
    Minimum free disk space required before accepting an upload.

    Configurable via MIN_DISK_SPACE_MB (default: 500 MB).
    Set to 0 to disable the check entirely — useful in CI where the
    runner's disk is constrained by the installed ML stack.
    """
    raw = os.getenv("MIN_DISK_SPACE_MB", "500")
    try:
        mb = int(raw)
    except ValueError:
        mb = 500
    return max(0, mb) * 1024 * 1024


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


# app/routers/media.py (استبدل دالة upload_car_media بالكامل)

@router.post("/upload/{car_id}", response_model=CarMediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_car_media(
    car_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_write_db),
    current_user: TokenData = Depends(get_auth_user)
):
    """
    Upload media (image or video) using chunked streaming.
    Zero‑waste memory: never loads the full file into RAM.
    """
    request_id = get_request_id()

    # 1. صلاحية السيارة والمستخدم (بدون لمس الملف)
    result = await db.execute(select(Car).where(Car.id == car_id))
    car = result.scalar_one_or_none()
    if not car:
        raise NotFoundException("Car", str(car_id))
    if current_user.role != UserRole.ADMIN.value and car.owner_id != current_user.user_id:
        raise ForbiddenException(message="You are not allowed to upload media for this car")

    # 2. تحديد نوع الوسائط من الامتداد
    try:
        media_type = get_media_type_from_filename(file.filename)
    except BadRequestException:
        logger.warning(f"Invalid file type", extra={"filename": file.filename, "request_id": request_id})
        raise # Invalid file type

    # 3. تجهيز المجلد والمسار
    storage_dir = get_storage_directory(media_type)
    storage_dir.mkdir(parents=True, exist_ok=True)
    unique_filename = generate_unique_filename(file.filename)
    file_path = storage_dir / unique_filename

    # 4. التأكد من وجود مساحة على القرص
    STORAGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    min_disk_bytes = get_min_disk_space_bytes()
    if min_disk_bytes > 0:
        disk_usage = shutil.disk_usage(STORAGE_BASE_DIR)
        if disk_usage.free < min_disk_bytes:
            raise InsufficientStorageException(
                required=min_disk_bytes,
                available=disk_usage.free,
            )

    # 5. الإعدادات: حجم القطعة، الحجم الأقصى، الحجم التراكمي
    CHUNK_SIZE = 1024 * 1024  # 1MB
    MAX_SIZE = MAX_FILE_SIZE   # 100MB
    total_size = 0
    first_chunk = True

    # 6. قراءة وكتابة متدفقة (Chunked)
    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            while True:
                # قراءة قطعة من UploadFile
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > MAX_SIZE:
                    # تجاوز الحجم ← نمسح الملف ونرفع خطأ
                    await buffer.close()
                    os.remove(file_path)
                    logger.warning("File too large", extra={"size": total_size, "request_id": request_id})
                    raise BadRequestException(
                        message=f"File size exceeds maximum allowed size of {MAX_SIZE // (1024*1024)}MB",
                        details={"current_size": total_size, "max_size": MAX_SIZE}
                    )

                # فحص Magic Bytes على أول قطعة فقط
                if first_chunk:
                    first_chunk = False
                    # نحتاج أول 2048 بايت عشان magic
                    # ناخد أول 2048 بايت من القطعة الحالية (قد تكون القطعة أكبر)
                    magic_sample = chunk[:2048]
                    # نفحص النوع باستخدام magic
                    mime = magic.Magic(mime=True)
                    detected_mime = mime.from_buffer(magic_sample) #from buffer means from the chunk
                    if media_type == MediaType.IMAGE:
                        if detected_mime not in ALLOWED_IMAGE_MIME_TYPES:
                            await buffer.close()
                            os.remove(file_path)
                            logger.warning("Invalid file type", extra={"filename": file.filename, "detected_mime": detected_mime, "expected": "image", "request_id": request_id})
                            raise BadRequestException(
                                message=f"Invalid file type. Expected image, got: {detected_mime}",
                                details={"detected_mime": detected_mime, "expected": "image"}
                            )
                            
                    else:
                        if detected_mime not in ALLOWED_VIDEO_MIME_TYPES:
                            await buffer.close()
                            os.remove(file_path)
                            logger.warning("Invalid file type", extra={"filename": file.filename, "detected_mime": detected_mime, "expected": "video", "request_id": request_id})
                            raise BadRequestException(
                                message=f"Invalid file type. Expected video, got: {detected_mime}",
                                details={"detected_mime": detected_mime, "expected": "video"}
                            )
                    logger.info("File type validated with magic (first chunk)", extra={"filename": file.filename, "request_id": request_id})

                # كتابة القطعة إلى القرص
                await buffer.write(chunk)

    except BadRequestException:
        raise  # نمرر الأخطاء المقصودة
    except Exception as e:
        logger.error("Failed to save file", extra={"error": str(e), "request_id": request_id})
        if file_path.exists(): # Delete the file if it exists
            os.remove(file_path)
        raise InternalServerException(message="Failed to save file", details={"error": str(e)})

    # 7. إنشاء سجل في قاعدة البيانات
    media_url = f"uploads/{media_type.value}s/{unique_filename}"
    media_data = CarMediaCreate(
        car_id=car_id,
        media_url=media_url,
        media_type=media_type,
        file_size=total_size
    )
    new_media = CarMedia(**media_data.model_dump())
    db.add(new_media)
    try:
        await db.commit()
        await db.refresh(new_media)
    except Exception as e:
        await db.rollback()
        os.remove(file_path) # Delete the file if it exists , why ? to avoid orphan files
        raise InternalServerException(message="Failed to save media record", details={"error": str(e)})

    logger.info("Media uploaded successfully", extra={"media_id": str(new_media.id), "request_id": request_id})

    # 8. مهام الخلفية (ضغط / صورة مصغرة)
    if media_type == MediaType.IMAGE:
        background_tasks.add_task(compress_image, file_path)
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
