# Phase 6: Core YouTube Module - Research

**Researched:** 2026-01-31
**Domain:** YouTube audio extraction with yt-dlp, FFmpeg validation
**Confidence:** HIGH

## Summary

Phase 6 creates a `youtube_handler.py` module that downloads audio from YouTube URLs using yt-dlp, with FFmpeg validation on startup. The existing project already has comprehensive research (STACK-YOUTUBE.md, PITFALLS-YOUTUBE.md) from milestone planning. This phase-specific research focuses on implementation patterns that directly inform planning.

**Key findings:**
1. yt-dlp Python API is well-documented with `YoutubeDL` class as context manager
2. FFmpeg validation uses `shutil.which('ffmpeg')` - standard Python pattern
3. Temp file cleanup is a known yt-dlp limitation requiring explicit handling
4. URL validation can delegate to yt-dlp's extractors or use simple prefix matching
5. Exception handling requires catching `DownloadError`, `ExtractorError`, `PostProcessingError`

**Primary recommendation:** Create a focused `youtube_handler.py` module with two public functions: `is_youtube_url()` for validation and `download_youtube_audio()` for extraction. Use context managers for cleanup, validate FFmpeg on import/startup.

## Standard Stack

The stack is already defined in milestone research. Phase 6 uses:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yt-dlp | `>=2026.1.29` | YouTube audio extraction | Active maintenance, Python 3.10+ native, stable embedding API |

### System Dependency
| Binary | Purpose | Why Required |
|--------|---------|--------------|
| ffmpeg | Audio extraction and format conversion | yt-dlp requires ffmpeg binary for merging/converting streams |
| ffprobe | Audio metadata detection | Used by yt-dlp for format selection |

### Supporting (Already in Project)
| Library | Purpose | Phase 6 Use |
|---------|---------|-------------|
| tempfile | Temporary file management | Downloaded audio before transcription |
| shutil | System binary detection | FFmpeg validation via `shutil.which()` |
| pathlib | Path handling | Temp file paths |

**Installation (already planned):**
```bash
pip install "yt-dlp[default]"
```

No alternatives considered - yt-dlp is the only viable option (youtube-dl unmaintained).

## Architecture Patterns

### Recommended Module Structure

```
cesar/
├── youtube_handler.py    # NEW - YouTube audio download
├── api/
│   ├── worker.py         # MODIFY - Add YouTube download step
│   ├── file_handler.py   # UNCHANGED (Phase 7 modifies)
│   └── ...
└── ...
```

### Pattern 1: Singleton FFmpeg Validation

**What:** Validate FFmpeg presence once at module import, cache result, check before operations.

**When to use:** Any module that requires system binaries.

**Example:**
```python
# cesar/youtube_handler.py
import shutil
from functools import lru_cache

@lru_cache(maxsize=1)
def check_ffmpeg_available() -> tuple[bool, str]:
    """Check if FFmpeg is available on the system.

    Returns:
        Tuple of (is_available, error_message)
    """
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')

    if not ffmpeg:
        return False, "FFmpeg not found. Install ffmpeg to enable YouTube transcription."
    if not ffprobe:
        return False, "FFprobe not found. Install ffmpeg (includes ffprobe) to enable YouTube transcription."

    return True, ""

def require_ffmpeg() -> None:
    """Raise error if FFmpeg is not available."""
    available, error = check_ffmpeg_available()
    if not available:
        raise RuntimeError(error)
```

**Source:** Standard Python pattern with `shutil.which()` from stdlib.

### Pattern 2: URL Validation with Prefix Matching

**What:** Simple prefix check for YouTube URLs, avoiding yt-dlp overhead for validation.

**When to use:** Quick validation before accepting jobs.

**Example:**
```python
# cesar/youtube_handler.py
import re

YOUTUBE_URL_PATTERNS = [
    r'^https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
    r'^https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
    r'^https?://youtu\.be/[\w-]+',
    r'^https?://(?:www\.)?youtube\.com/embed/[\w-]+',
    r'^https?://(?:www\.)?youtube\.com/v/[\w-]+',
]

_YOUTUBE_REGEX = re.compile('|'.join(YOUTUBE_URL_PATTERNS))

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
```

**Rationale:** Faster than invoking yt-dlp for validation. Covers common formats (watch, shorts, youtu.be, embed).

### Pattern 3: Context Manager for Download with Cleanup

**What:** Use context manager + try/finally for guaranteed temp file cleanup.

**When to use:** Any yt-dlp download operation.

**Example:**
```python
# cesar/youtube_handler.py
import tempfile
import uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

import yt_dlp

@contextmanager
def _temp_download_path(suffix: str = '.m4a') -> Generator[Path, None, None]:
    """Create a temporary file path for download, ensure cleanup on exit."""
    temp_dir = Path(tempfile.gettempdir()) / 'cesar-youtube'
    temp_dir.mkdir(exist_ok=True)

    temp_path = temp_dir / f"{uuid.uuid4()}{suffix}"
    try:
        yield temp_path
    finally:
        # Clean up main file
        temp_path.unlink(missing_ok=True)
        # Clean up any partial files yt-dlp may have left
        for pattern in ['*.part', '*.ytdl', '*.temp.*']:
            for leftover in temp_dir.glob(pattern):
                leftover.unlink(missing_ok=True)
```

**Source:** Addresses [yt-dlp Issue #11674](https://github.com/yt-dlp/yt-dlp/issues/11674) and [Issue #5463](https://github.com/yt-dlp/yt-dlp/issues/5463).

### Pattern 4: Download Function with Comprehensive Error Handling

**What:** Single public function for downloading audio with proper error mapping.

**When to use:** The main entry point for YouTube downloads.

**Example:**
```python
# cesar/youtube_handler.py
import logging
from pathlib import Path
from typing import Optional

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError, PostProcessingError

logger = logging.getLogger(__name__)

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

def download_youtube_audio(url: str, output_path: Optional[Path] = None) -> Path:
    """Download audio from YouTube URL.

    Args:
        url: YouTube video URL
        output_path: Optional output path. If None, creates temp file.

    Returns:
        Path to downloaded audio file

    Raises:
        RuntimeError: If FFmpeg not available
        YouTubeURLError: If URL is invalid
        YouTubeUnavailableError: If video unavailable
        YouTubeRateLimitError: If rate limited
        YouTubeDownloadError: For other download errors
    """
    require_ffmpeg()

    if not is_youtube_url(url):
        raise YouTubeURLError(f"Invalid YouTube URL: {url}")

    # Determine output path
    if output_path is None:
        temp_dir = Path(tempfile.gettempdir()) / 'cesar-youtube'
        temp_dir.mkdir(exist_ok=True)
        output_path = temp_dir / f"{uuid.uuid4()}.m4a"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': {'default': str(output_path.with_suffix(''))},  # yt-dlp adds extension
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
            logger.info(f"Downloaded: {info.get('title', 'Unknown')}")

    except DownloadError as e:
        error_str = str(e).lower()
        if '403' in error_str or 'forbidden' in error_str:
            raise YouTubeRateLimitError(
                "YouTube blocked the download. Try again later or update yt-dlp."
            ) from e
        elif 'unavailable' in error_str or 'private' in error_str:
            raise YouTubeUnavailableError(
                f"Video is unavailable: {e}"
            ) from e
        else:
            raise YouTubeDownloadError(f"Download failed: {e}") from e

    except ExtractorError as e:
        raise YouTubeURLError(f"Could not process URL: {e}") from e

    except PostProcessingError as e:
        raise YouTubeDownloadError(
            f"Audio conversion failed (FFmpeg error): {e}"
        ) from e

    # yt-dlp adds the extension, find the actual file
    actual_path = output_path.with_suffix('.m4a')
    if not actual_path.exists():
        # Try other common extensions
        for ext in ['.mp3', '.opus', '.webm', '.wav']:
            alt_path = output_path.with_suffix(ext)
            if alt_path.exists():
                actual_path = alt_path
                break

    if not actual_path.exists():
        raise YouTubeDownloadError(
            f"Download succeeded but output file not found at {output_path}"
        )

    return actual_path
```

**Source:** Exception types from [yt-dlp YoutubeDL.py source](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py).

### Anti-Patterns to Avoid

- **ProcessPoolExecutor with yt-dlp:** YoutubeDL objects are not picklable. Use ThreadPoolExecutor via `asyncio.to_thread()`.
- **String outtmpl:** Modern yt-dlp requires `{'default': path}` dict format, not plain string.
- **Relying on yt-dlp cleanup:** yt-dlp does NOT clean up partial files on failure. Always use try/finally.
- **pip install ffmpeg-python:** This is a Python wrapper, NOT the ffmpeg binary. yt-dlp needs the system binary.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YouTube URL parsing | Regex for video ID extraction | yt-dlp's extractors | Handles edge cases, shorts, embeds |
| Audio format detection | Manual extension checking | yt-dlp + FFmpeg | Automatic best format selection |
| Download progress | Custom byte tracking | yt-dlp progress_hooks | Already implemented, handles fragments |
| YouTube API integration | Direct YouTube Data API | yt-dlp | No API key needed, handles auth/captcha |

**Key insight:** yt-dlp handles enormous complexity (format negotiation, anti-bot measures, stream merging). Let it do its job; only wrap for error handling and cleanup.

## Common Pitfalls

### Pitfall 1: Temp File Leakage on Failure

**What goes wrong:** yt-dlp creates `.part`, `.ytdl`, and fragment files that aren't cleaned up on download failure, crash, or Ctrl+C. Disk fills with orphaned files.

**Why it happens:** yt-dlp's cleanup is best-effort and doesn't handle all failure modes.

**How to avoid:**
1. Use isolated temp directory: `cesar-youtube/` under system temp
2. Wrap all downloads in try/finally with explicit cleanup
3. Clean orphaned files on module startup (optional startup task)

**Warning signs:** Temp directory growing, `.part` files accumulating.

### Pitfall 2: FFmpeg Not Found After Install

**What goes wrong:** User installs `pip install ffmpeg-python` thinking it provides FFmpeg. yt-dlp fails with "ffmpeg not found".

**Why it happens:** ffmpeg-python is a Python wrapper library, not the FFmpeg binary.

**How to avoid:**
1. Document system FFmpeg requirement clearly
2. Validate FFmpeg on startup with clear error message
3. Error message should say "Install FFmpeg binary" not just "FFmpeg missing"

**Warning signs:** Download works but postprocessing fails.

### Pitfall 3: outtmpl Format String vs Dict

**What goes wrong:** Using `'outtmpl': '/path/to/%(title)s.%(ext)s'` (string) causes TypeError.

**Why it happens:** yt-dlp changed from youtube-dl's string format to dict format.

**How to avoid:** Always use `'outtmpl': {'default': '/path/to/file'}`.

**Warning signs:** TypeError about string indices.

### Pitfall 4: YouTube Rate Limiting (403 Forbidden)

**What goes wrong:** Downloads work initially, then start failing with 403 errors after several requests.

**Why it happens:** YouTube detects automated access and blocks IP/user-agent.

**How to avoid:**
1. Limit concurrent YouTube jobs (queue them)
2. Add delays between downloads (5+ seconds recommended)
3. Catch 403 specifically and return actionable error message
4. Document that YouTube support may be unreliable

**Warning signs:** 403 errors after batch processing.

### Pitfall 5: Testing with Copyrighted Content

**What goes wrong:** Tests use random YouTube videos that get deleted, made private, or cause legal issues.

**Why it happens:** Most YouTube content is copyrighted and ephemeral.

**How to avoid:**
1. Mock yt-dlp in unit tests
2. For integration tests, use: "Me at the zoo" (jNQXAC9IVRw) - first YouTube video, stable
3. Mark integration tests with `@pytest.mark.skipif(no_ffmpeg)` and `@pytest.mark.integration`

**Warning signs:** Flaky tests, legal notices.

## Code Examples

### Complete youtube_handler.py Module

```python
"""
YouTube audio download handler for Cesar Transcription.

Provides functions to validate YouTube URLs and download audio using yt-dlp.
Requires FFmpeg to be installed as a system binary.
"""
import logging
import shutil
import tempfile
import uuid
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError, PostProcessingError

logger = logging.getLogger(__name__)

# YouTube URL patterns
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
        True if URL matches YouTube patterns
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
        if '403' in error_str or 'forbidden' in error_str:
            raise YouTubeRateLimitError(
                "YouTube blocked the download. This may be temporary rate limiting. "
                "Try again in a few minutes or update yt-dlp."
            ) from e
        elif 'unavailable' in error_str or 'private' in error_str:
            raise YouTubeUnavailableError(
                f"Video is unavailable (may be private, deleted, or geo-blocked)"
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
        f"Download appeared to succeed but output file not found"
    )


def _cleanup_partial_files(directory: Path, base_name: str) -> None:
    """Clean up partial download files left by yt-dlp."""
    patterns = [
        f"{base_name}.*",
        f"{base_name}.*.part",
        f"{base_name}.*.ytdl",
    ]
    for pattern in patterns:
        for file in directory.glob(pattern):
            try:
                file.unlink()
            except OSError:
                pass


def cleanup_youtube_temp_dir() -> int:
    """Clean up old files in the YouTube temp directory.

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
            except OSError:
                pass
    return count
```

### Unit Test Example (Mocked)

```python
"""Tests for youtube_handler module."""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from cesar.youtube_handler import (
    is_youtube_url,
    check_ffmpeg_available,
    download_youtube_audio,
    YouTubeURLError,
    FFmpegNotFoundError,
)


class TestIsYouTubeUrl(unittest.TestCase):
    """Tests for is_youtube_url function."""

    def test_valid_watch_url(self):
        self.assertTrue(is_youtube_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ'))

    def test_valid_youtu_be(self):
        self.assertTrue(is_youtube_url('https://youtu.be/dQw4w9WgXcQ'))

    def test_valid_shorts(self):
        self.assertTrue(is_youtube_url('https://www.youtube.com/shorts/abc123'))

    def test_invalid_url(self):
        self.assertFalse(is_youtube_url('https://vimeo.com/123456'))

    def test_empty_url(self):
        self.assertFalse(is_youtube_url(''))
        self.assertFalse(is_youtube_url(None))


class TestCheckFfmpegAvailable(unittest.TestCase):
    """Tests for FFmpeg validation."""

    @patch('shutil.which')
    def test_ffmpeg_available(self, mock_which):
        mock_which.side_effect = lambda x: f'/usr/bin/{x}'
        check_ffmpeg_available.cache_clear()
        available, error = check_ffmpeg_available()
        self.assertTrue(available)
        self.assertEqual(error, '')

    @patch('shutil.which')
    def test_ffmpeg_missing(self, mock_which):
        mock_which.return_value = None
        check_ffmpeg_available.cache_clear()
        available, error = check_ffmpeg_available()
        self.assertFalse(available)
        self.assertIn('FFmpeg not found', error)


class TestDownloadYouTubeAudio(unittest.TestCase):
    """Tests for download_youtube_audio function."""

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('yt_dlp.YoutubeDL')
    def test_download_success(self, mock_ydl_class, mock_ffmpeg):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {'title': 'Test Video'}

        with patch.object(Path, 'exists', return_value=True):
            result = download_youtube_audio('https://youtube.com/watch?v=test')

        self.assertIsInstance(result, Path)
        mock_ydl.extract_info.assert_called_once()

    @patch('cesar.youtube_handler.require_ffmpeg')
    def test_invalid_url_raises(self, mock_ffmpeg):
        with self.assertRaises(YouTubeURLError):
            download_youtube_audio('https://vimeo.com/123')
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| youtube-dl | yt-dlp | 2021 | youtube-dl unmaintained, use yt-dlp |
| String outtmpl | Dict outtmpl | yt-dlp 2021+ | `{'default': path}` format required |
| ProcessPool for downloads | ThreadPool / asyncio.to_thread | Always | YoutubeDL not picklable |

**Deprecated/outdated:**
- youtube-dl: Unmaintained, use yt-dlp
- `ffmpeg-python` package for yt-dlp: Use system binary instead

## Open Questions

### 1. Output Format: m4a vs wav

**What we know:** faster-whisper accepts both m4a and wav. m4a is smaller, wav is uncompressed.

**What's unclear:** Does transcription quality differ? Does processing time differ?

**Recommendation:** Use m4a (default in examples). Faster download, smaller temp files. Verify in integration testing.

### 2. Cleanup Timing: Immediate vs Deferred

**What we know:** Temp files should be cleaned after transcription. Worker already has try/finally pattern.

**What's unclear:** Should youtube_handler clean up, or should caller (worker) manage cleanup?

**Recommendation:** Caller manages cleanup. `download_youtube_audio()` returns path; caller deletes after transcription. This matches existing pattern in worker.py.

### 3. Startup Validation vs Lazy Validation

**What we know:** FFmpeg must be validated before accepting YouTube jobs.

**What's unclear:** Validate on server startup, or validate on first YouTube request?

**Recommendation:** Validate on startup (SYS-01 requirement). Cache result with `@lru_cache`. This provides fast-fail and clear startup errors.

## Sources

### Primary (HIGH confidence)
- [yt-dlp GitHub Repository](https://github.com/yt-dlp/yt-dlp) - Official source, README, API
- [yt-dlp YoutubeDL.py source](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py) - Exception types, parameters
- [yt-dlp PyPI](https://pypi.org/project/yt-dlp/) - Version, installation

### Secondary (MEDIUM confidence)
- [yt-dlp Issue #11674: Cleanup temp files](https://github.com/yt-dlp/yt-dlp/issues/11674) - Confirms cleanup limitation
- [yt-dlp Issue #5463: Delete unfinished cache](https://github.com/yt-dlp/yt-dlp/issues/5463) - Confirms cleanup needed
- [RapidSeedbox: YT-DLP Guide 2026](https://www.rapidseedbox.com/blog/yt-dlp-complete-guide) - Current best practices

### Tertiary (Prior Milestone Research)
- `.planning/research/STACK-YOUTUBE.md` - Comprehensive stack research
- `.planning/research/PITFALLS-YOUTUBE.md` - Detailed pitfall analysis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - yt-dlp is the only viable option, well-documented
- Architecture: HIGH - Patterns verified against existing codebase and yt-dlp source
- Pitfalls: HIGH - Confirmed with GitHub issues and prior research

**Research date:** 2026-01-31
**Valid until:** 2026-03-01 (yt-dlp updates frequently, revalidate if YouTube breaks)
