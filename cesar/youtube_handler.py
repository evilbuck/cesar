"""
YouTube audio download handler for Cesar Transcription.

Provides functions to validate YouTube URLs and download audio using yt-dlp.
Requires FFmpeg to be installed as a system binary.
"""
import logging
import re
import shutil
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError, PostProcessingError

logger = logging.getLogger(__name__)


# === YouTube URL Patterns ===

YOUTUBE_URL_PATTERNS = [
    r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
    r'^https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
    r'^https?://youtu\.be/[\w-]+',
    r'^https?://(?:www\.)?youtube\.com/embed/[\w-]+',
    r'^https?://(?:www\.)?youtube\.com/v/[\w-]+',
]
_YOUTUBE_REGEX = re.compile('|'.join(YOUTUBE_URL_PATTERNS))


# === Custom Exceptions ===

class YouTubeDownloadError(Exception):
    """Base exception for YouTube download errors."""
    pass


class YouTubeURLError(YouTubeDownloadError):
    """Invalid or unsupported YouTube URL."""
    pass


class YouTubeUnavailableError(YouTubeDownloadError):
    """Video is unavailable (private, deleted, geo-blocked)."""
    pass


class YouTubeRateLimitError(YouTubeDownloadError):
    """YouTube rate limiting or bot detection."""
    pass


class FFmpegNotFoundError(YouTubeDownloadError):
    """FFmpeg binary not found on system."""
    pass


# === FFmpeg Validation ===

@lru_cache(maxsize=1)
def check_ffmpeg_available() -> tuple[bool, str]:
    """Check if FFmpeg binaries are available.

    Returns:
        Tuple of (is_available, error_message_if_not)
    """
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')

    if not ffmpeg:
        return False, (
            "FFmpeg not found. YouTube transcription requires FFmpeg. "
            "Install with: pacman -S ffmpeg (Arch), apt install ffmpeg (Debian), "
            "or brew install ffmpeg (macOS)"
        )
    if not ffprobe:
        return False, (
            "FFprobe not found. Install FFmpeg which includes ffprobe."
        )
    return True, ""


def require_ffmpeg() -> None:
    """Raise FFmpegNotFoundError if FFmpeg is not available."""
    available, error = check_ffmpeg_available()
    if not available:
        raise FFmpegNotFoundError(error)


# === URL Validation ===

def is_youtube_url(url: str) -> bool:
    """Check if URL is a valid YouTube URL.

    Args:
        url: URL string to validate

    Returns:
        True if URL matches YouTube patterns, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    return bool(_YOUTUBE_REGEX.match(url.strip()))


# === Download Function ===

def download_youtube_audio(url: str, output_dir: Optional[Path] = None) -> Path:
    """Download audio from YouTube URL to a temporary file.

    Args:
        url: YouTube video URL
        output_dir: Optional directory for output. Defaults to system temp.

    Returns:
        Path to downloaded audio file (.m4a format)

    Raises:
        FFmpegNotFoundError: If FFmpeg not installed
        YouTubeURLError: If URL is invalid
        YouTubeUnavailableError: If video unavailable
        YouTubeRateLimitError: If rate limited
        YouTubeDownloadError: For other download errors
    """
    require_ffmpeg()

    if not is_youtube_url(url):
        raise YouTubeURLError(f"Invalid YouTube URL: {url}")

    # Set up output path
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir()) / 'cesar-youtube'
    output_dir.mkdir(parents=True, exist_ok=True)

    # UUID-based filename to avoid collisions
    base_name = str(uuid.uuid4())
    output_template = str(output_dir / base_name)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': {'default': output_template},
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            logger.info(f"Downloaded YouTube audio: {info.get('title', 'Unknown')}")

    except DownloadError as e:
        _cleanup_partial_files(output_dir, base_name)
        error_str = str(e).lower()
        if '403' in error_str or 'forbidden' in error_str or '429' in error_str:
            raise YouTubeRateLimitError(
                "YouTube blocked the download. This may be temporary rate limiting. "
                "Try again in a few minutes or update yt-dlp."
            ) from e
        elif 'unavailable' in error_str or 'private' in error_str:
            raise YouTubeUnavailableError(
                "Video is unavailable (may be private, deleted, or geo-blocked)"
            ) from e
        else:
            raise YouTubeDownloadError(f"Download failed: {e}") from e

    except ExtractorError as e:
        _cleanup_partial_files(output_dir, base_name)
        raise YouTubeURLError(f"Could not process YouTube URL: {e}") from e

    except PostProcessingError as e:
        _cleanup_partial_files(output_dir, base_name)
        raise YouTubeDownloadError(
            f"Audio conversion failed. Ensure FFmpeg is properly installed: {e}"
        ) from e

    except Exception as e:
        _cleanup_partial_files(output_dir, base_name)
        raise YouTubeDownloadError(f"Unexpected error: {e}") from e

    # Find the actual output file (yt-dlp adds extension)
    expected_path = output_dir / f"{base_name}.m4a"
    if expected_path.exists():
        return expected_path

    # Check alternative extensions
    for ext in ['.mp3', '.opus', '.webm', '.wav', '.aac']:
        alt_path = output_dir / f"{base_name}{ext}"
        if alt_path.exists():
            return alt_path

    raise YouTubeDownloadError(
        "Download appeared to succeed but output file not found"
    )


def _cleanup_partial_files(directory: Path, base_name: str) -> None:
    """Clean up partial download files left by yt-dlp.

    Args:
        directory: Directory containing partial files
        base_name: Base filename (UUID) to match
    """
    patterns = [
        f"{base_name}.*",
        f"{base_name}.*.part",
        f"{base_name}.*.ytdl",
    ]
    for pattern in patterns:
        for file in directory.glob(pattern):
            try:
                file.unlink()
                logger.debug(f"Cleaned up partial file: {file}")
            except OSError:
                pass


def cleanup_youtube_temp_dir() -> int:
    """Clean up old files in the YouTube temp directory.

    Call this on startup to remove orphaned temp files from
    previous sessions that may have crashed or been interrupted.

    Returns:
        Number of files removed
    """
    temp_dir = Path(tempfile.gettempdir()) / 'cesar-youtube'
    if not temp_dir.exists():
        return 0

    count = 0
    for file in temp_dir.iterdir():
        if file.is_file():
            try:
                file.unlink()
                count += 1
                logger.debug(f"Cleaned up orphaned temp file: {file}")
            except OSError:
                pass
    return count
