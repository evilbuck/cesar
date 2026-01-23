"""
File handling utilities for the Cesar Transcription API.

Provides utilities for validating, saving uploaded files, and downloading
files from URLs for transcription processing.
"""
import os
import tempfile
from pathlib import Path

import httpx
from fastapi import HTTPException, UploadFile

# Constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma", ".webm"}
URL_TIMEOUT = 60  # seconds


def validate_file_extension(filename: str) -> bool:
    """Validate that a filename has an allowed audio extension.

    Args:
        filename: The filename to validate

    Returns:
        True if the extension is allowed, False otherwise
    """
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


async def save_upload_file(file: UploadFile) -> str:
    """Save an uploaded file to a temporary location.

    Validates file size and extension before saving.

    Args:
        file: The uploaded file from FastAPI

    Returns:
        Path to the saved temporary file

    Raises:
        HTTPException: 413 if file is too large
        HTTPException: 400 if file extension is invalid
        HTTPException: 500 if file save fails
    """
    # Validate file size if available
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    # Get extension from filename
    filename = file.filename or ""
    ext = Path(filename).suffix.lower() if filename else ".tmp"

    # Validate extension
    if ext != ".tmp" and not validate_file_extension(filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    try:
        # Create temp file and save content
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            # Check actual content size as backup validation
            if len(content) > MAX_FILE_SIZE:
                os.unlink(tmp.name)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
                )
            tmp.write(content)
            return tmp.name
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save uploaded file: {str(e)}",
        )


async def download_from_url(url: str) -> str:
    """Download a file from a URL to a temporary location.

    Validates the file extension from the URL path.

    Args:
        url: The URL to download from

    Returns:
        Path to the downloaded temporary file

    Raises:
        HTTPException: 408 if download times out
        HTTPException: 400 if download fails or extension is invalid
    """
    # Get extension from URL path
    url_path = Path(url.split("?")[0])  # Remove query params
    ext = url_path.suffix.lower() if url_path.suffix else ".mp3"

    # Validate extension
    if not validate_file_extension(f"file{ext}"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type in URL. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    try:
        async with httpx.AsyncClient(timeout=URL_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Create temp file
            fd, tmp_path = tempfile.mkstemp(suffix=ext)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(response.content)
                return tmp_path
            except Exception:
                os.unlink(tmp_path)
                raise

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=408,
            detail="URL download timeout",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download from URL: HTTP {e.response.status_code}",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download from URL: {str(e)}",
        )
