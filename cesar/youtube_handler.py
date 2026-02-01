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
    error_type = "youtube_error"
    http_status = 400


class YouTubeURLError(YouTubeDownloadError):
    """Invalid or unsupported YouTube URL."""
    error_type = "invalid_youtube_url"
    http_status = 400


class YouTubeUnavailableError(YouTubeDownloadError):
    """Video is unavailable (private, deleted, geo-blocked)."""
    error_type = "video_unavailable"
    http_status = 404


class YouTubeAgeRestrictedError(YouTubeUnavailableError):
    """Video requires age verification."""
    error_type = "age_restricted"
    http_status = 403


class YouTubeRateLimitError(YouTubeDownloadError):
    """YouTube rate limiting or bot detection."""
    error_type = "rate_limited"
    http_status = 429


class YouTubeNetworkError(YouTubeDownloadError):
    """Network-related errors during download."""
    error_type = "network_error"
    http_status = 502


class FFmpegNotFoundError(YouTubeDownloadError):
    """FFmpeg binary not found on system."""
    error_type = "ffmpeg_not_found"
    http_status = 503


# === Video ID Extraction ===

def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL.

    Args:
        url: YouTube URL string

    Returns:
        11-character video ID, or 'unknown' if extraction fails
    """
    if not url or not isinstance(url, str):
        return "unknown"

    # Pattern 1: v= parameter (watch URLs)
    match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)

    # Pattern 2: youtu.be/ID
    match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)

    # Pattern 3: /shorts/ID, /embed/ID, /v/ID
    match = re.search(r'(?:/shorts/|/embed/|/v/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)

    return "unknown"


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

    video_id = extract_video_id(url)

    if not is_youtube_url(url):
        raise YouTubeURLError(
            f"Invalid YouTube URL (video: {video_id}). The URL format is not recognized."
        )

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

        # Age-restricted (most specific first)
        if 'sign in to confirm your age' in error_str:
            raise YouTubeAgeRestrictedError(
                f"Age-restricted video (video: {video_id}). "
                "This video requires sign-in to verify age."
            ) from e

        # Private video (check both "private video" and "is private")
        if 'private video' in error_str or 'is private' in error_str:
            raise YouTubeUnavailableError(
                f"Private video (video: {video_id}). "
                "This video is private and cannot be accessed."
            ) from e

        # Geo-restricted
        if 'not available in your country' in error_str or 'geo' in error_str:
            raise YouTubeUnavailableError(
                f"Geo-restricted video (video: {video_id}). "
                "This video is not available in your region."
            ) from e

        # Network timeout
        if 'timed out' in error_str or 'timeout' in error_str:
            raise YouTubeNetworkError(
                f"Network timeout (video: {video_id}). "
                "Connection timed out. Check your network and try again."
            ) from e

        # Connection reset
        if 'connection reset' in error_str or 'errno 104' in error_str:
            raise YouTubeNetworkError(
                f"Connection interrupted (video: {video_id}). "
                "The connection was reset. Try again."
            ) from e

        # General network error
        if any(term in error_str for term in ['network', 'connection', 'urlopen']):
            raise YouTubeNetworkError(
                f"Network error (video: {video_id}). "
                "Could not connect to YouTube. Check your network and try again."
            ) from e

        # Rate limiting (403, 429)
        if '403' in error_str or 'forbidden' in error_str or '429' in error_str:
            raise YouTubeRateLimitError(
                f"YouTube is limiting requests (video: {video_id}). "
                "This is YouTube throttling connections. Try again later."
            ) from e

        # General unavailable
        if 'unavailable' in error_str:
            raise YouTubeUnavailableError(
                f"Video unavailable (video: {video_id}). "
                "This video may have been deleted or made private."
            ) from e

        # Fallback
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
