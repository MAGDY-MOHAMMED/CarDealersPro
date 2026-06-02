from pathlib import Path
from PIL import Image
import os
import subprocess
from app.core.logging_config import logger
from app.core.request_id import get_request_id


def compress_image(file_path: Path, quality: int = 85, max_size: tuple = (1920, 1080)) -> None:
    """
    Compress image in background task.
    
    Args:
        file_path: Path to the image file
        quality: JPEG quality (1-100), default 85
        max_size: Maximum dimensions (width, height), default (1920, 1080)
    """
    try:
        # Open image
        with Image.open(file_path) as img:
            # Resize if larger than max_size
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]: # means width or height is larger than max_size
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary (for JPEG)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Save with compression
            img.save(file_path, "JPEG", quality=quality, optimize=True)
            
            logger.info(
                f"Image compressed successfully",
                extra={
                    "file_path": str(file_path),
                    "original_size": img.size,
                    "request_id": get_request_id()
                }
            )
    except Exception as e:
        logger.error(
            f"Failed to compress image",
            extra={
                "file_path": str(file_path),
                "error": str(e),
                "request_id": get_request_id()
            }
        )


def create_thumbnail(file_path: Path, thumbnail_path: Path, size: tuple = (300, 300)) -> None:
    """
    Create thumbnail for image in background task.
    
    Args:
        file_path: Path to the original image
        thumbnail_path: Path to save the thumbnail
        size: Thumbnail dimensions (width, height), default (300, 300)
    """
    try:
        with Image.open(file_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS) # Resampling.LANCZOS means high quality
            img.save(thumbnail_path, "JPEG", quality=80, optimize=True)
            
            logger.info(
                f"Thumbnail created successfully",
                extra={
                    "file_path": str(file_path),
                    "thumbnail_path": str(thumbnail_path),
                    "request_id": get_request_id()
                }
            )
    except Exception as e:
        logger.error(
            f"Failed to create thumbnail",
            extra={
                "file_path": str(file_path),
                "error": str(e),
                "request_id": get_request_id()
            }
        )


def create_video_thumbnail(file_path: Path, thumbnail_path: Path, timestamp: str = "00:00:01", size: tuple = (320, 240)) -> None:
    """
    Create thumbnail for video using ffmpeg in background task.

    Args:
        file_path: Path to the video file
        thumbnail_path: Path to save the thumbnail
        timestamp: Timestamp to capture thumbnail from (HH:MM:SS), default "00:00:01"
        size: Thumbnail dimensions (width, height), default (320, 240)
    """
    try:
        # Use ffmpeg to extract thumbnail at specific timestamp
        cmd = [
            "ffmpeg", # 
            "-i", str(file_path), # means input file
            "-ss", timestamp, # means seek to timestamp
            "-vframes", "1", # means extract 1 frame
            "-s", f"{size[0]}x{size[1]}", # means set size , f"{size[0]}x{size[1]}" means width x height
            "-y",  # Overwrite output file if exists
            str(thumbnail_path)
        ]

        subprocess.run(cmd, check=True, capture_output=True, text=True) # check=True means raise exception if return code is not 0, text=True means return output as string

        logger.info(
            f"Video thumbnail created successfully",
            extra={
                "file_path": str(file_path),
                "thumbnail_path": str(thumbnail_path),
                "timestamp": timestamp,
                "request_id": get_request_id()
            }
        )
    #means ffmpeg failed
    except subprocess.CalledProcessError as e:
        logger.error(
            f"FFmpeg failed to create video thumbnail",
            extra={
                "file_path": str(file_path),
                "stderr": e.stderr,
                "request_id": get_request_id()
            }
        )
    #means other error
    except Exception as e:
        logger.error(
            f"Failed to create video thumbnail",
            extra={
                "file_path": str(file_path),
                "error": str(e),
                "request_id": get_request_id()
            }
        )
