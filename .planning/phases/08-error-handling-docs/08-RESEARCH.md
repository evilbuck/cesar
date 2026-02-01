# Phase 8: Error Handling & Documentation - Research

**Researched:** 2026-02-01
**Domain:** YouTube error handling, CLI/API error patterns, documentation
**Confidence:** HIGH

## Summary

This phase focuses on comprehensive error handling for YouTube-related failures and updating documentation with YouTube usage examples. The research identifies the specific yt-dlp exception types that need mapping to user-friendly error messages, establishes error message patterns that match the decided style (balanced technical info + plain English), and defines the API error response structure.

The codebase already has a solid foundation with custom exception classes (`YouTubeDownloadError`, `YouTubeURLError`, `YouTubeUnavailableError`, `YouTubeRateLimitError`, `FFmpegNotFoundError`) and basic error detection in `youtube_handler.py`. This phase enhances these with more granular error detection (age-restricted, geo-blocked, network timeout) and clearer user-facing messages.

**Primary recommendation:** Extend the existing exception hierarchy with additional error types (age-restricted, geo-restricted, network timeout), add an `error_type` field to API error responses, and craft user-friendly error messages following the "brief technical + plain English explanation" pattern.

## Standard Stack

### Core (Already in Codebase)

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| yt-dlp | latest | YouTube download | Already imported, provides exception classes |
| Click | 8.x | CLI error handling | Already used, has built-in exception handling |
| FastAPI | 0.100+ | API error responses | Already used, has HTTPException pattern |
| Rich | 13.x | CLI error formatting | Already used for colored output |

### No New Dependencies

This phase requires no new dependencies. All error handling uses existing libraries.

## Architecture Patterns

### Pattern 1: yt-dlp Exception Mapping

**What:** Map yt-dlp exceptions to domain-specific custom exceptions with user-friendly messages.

**Current implementation (youtube_handler.py:160-187):**
```python
except DownloadError as e:
    error_str = str(e).lower()
    if '403' in error_str or 'forbidden' in error_str or '429' in error_str:
        raise YouTubeRateLimitError(...)
    elif 'unavailable' in error_str or 'private' in error_str:
        raise YouTubeUnavailableError(...)
```

**Enhanced pattern:**
```python
# Source: yt-dlp GitHub utils/_utils.py + issue discussions
except DownloadError as e:
    error_str = str(e).lower()
    video_id = _extract_video_id(url)

    # Rate limiting / bot detection
    if '403' in error_str or 'forbidden' in error_str or '429' in error_str:
        raise YouTubeRateLimitError(
            f"YouTube is limiting requests (video: {video_id}). "
            "This is YouTube throttling connections. Try again later."
        )

    # Age-restricted
    elif 'sign in to confirm your age' in error_str:
        raise YouTubeAgeRestrictedError(
            f"Age-restricted video (video: {video_id}). "
            "This video requires sign-in to verify age."
        )

    # Private video
    elif 'private video' in error_str:
        raise YouTubeUnavailableError(
            f"Private video (video: {video_id}). "
            "This video is private and cannot be accessed."
        )

    # Geo-restricted
    elif 'not available in your country' in error_str or 'geo' in error_str:
        raise YouTubeUnavailableError(
            f"Geo-restricted video (video: {video_id}). "
            "This video is not available in your region."
        )

    # General unavailable
    elif 'unavailable' in error_str:
        raise YouTubeUnavailableError(
            f"Video unavailable (video: {video_id}). "
            "This video may have been deleted or made private."
        )
```

### Pattern 2: Network Error Detection

**What:** Detect network-related errors and provide retry guidance.

```python
# Source: yt-dlp GitHub issues #7376, #3771, #14571
import socket
import urllib.error

# In download_youtube_audio exception handling:
except DownloadError as e:
    error_str = str(e).lower()

    # Network timeout
    if 'timed out' in error_str or 'timeout' in error_str:
        raise YouTubeNetworkError(
            f"Network timeout (video: {video_id}). "
            "Connection timed out. Check your network and try again."
        )

    # Connection reset
    elif 'connection reset' in error_str or 'errno 104' in error_str:
        raise YouTubeNetworkError(
            f"Connection interrupted (video: {video_id}). "
            "The connection was reset. Try again."
        )

    # General network error
    elif any(x in error_str for x in ['network', 'connection', 'urlopen']):
        raise YouTubeNetworkError(
            f"Network error (video: {video_id}). "
            "Could not connect to YouTube. Check your network and try again."
        )
```

### Pattern 3: API Error Response with error_type

**What:** Include `error_type` field in API error responses for programmatic error handling.

```python
# Source: FastAPI documentation handling-errors
from fastapi import HTTPException
from fastapi.responses import JSONResponse

class YouTubeError(Exception):
    """Base YouTube error with error_type."""
    error_type: str = "youtube_error"
    http_status: int = 400

class YouTubeURLError(YouTubeError):
    error_type = "invalid_youtube_url"
    http_status = 400

class YouTubeUnavailableError(YouTubeError):
    error_type = "video_unavailable"
    http_status = 404

class YouTubeRateLimitError(YouTubeError):
    error_type = "rate_limited"
    http_status = 429

class YouTubeAgeRestrictedError(YouTubeError):
    error_type = "age_restricted"
    http_status = 403

class YouTubeNetworkError(YouTubeError):
    error_type = "network_error"
    http_status = 502

# Exception handler in server.py
@app.exception_handler(YouTubeError)
async def youtube_error_handler(request: Request, exc: YouTubeError):
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error_type": exc.error_type,
            "message": str(exc),
        }
    )
```

### Pattern 4: CLI Error Message Formatting

**What:** Consistent error formatting with Rich for CLI.

```python
# Source: Current cli.py pattern
def format_youtube_error(error: YouTubeError, verbose: bool = False) -> str:
    """Format YouTube error for CLI display."""
    message = str(error)

    if verbose and error.__cause__:
        # Show cleaned underlying cause (no raw stack trace)
        cause = str(error.__cause__)
        # Clean up yt-dlp verbose output
        cause = cause.split('\n')[0]  # First line only
        message += f"\n  Cause: {cause}"

    return message
```

### Anti-Patterns to Avoid

- **Raw exception messages:** Never expose raw yt-dlp exception strings to users. Always map to user-friendly messages.
- **Installation hints in error messages:** Per CONTEXT.md decision, don't include install hints for FFmpeg. Just state it's not found.
- **External links in errors:** Keep error messages self-contained per CONTEXT.md.
- **Stack traces in non-verbose mode:** Only show cleaned underlying cause with `-v` flag.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exception hierarchy | Custom base class from scratch | Extend existing `YouTubeDownloadError` | Already has proper chaining |
| Video ID extraction | Manual regex | yt-dlp's own extraction | Handles all URL formats |
| HTTP status mapping | Manual status code logic | HTTPException with custom handler | FastAPI standard pattern |

**Key insight:** The existing exception hierarchy in `youtube_handler.py` is well-designed. Extend it rather than replace it.

## Common Pitfalls

### Pitfall 1: Incomplete Error String Matching

**What goes wrong:** Missing error patterns causes generic "download failed" messages.
**Why it happens:** yt-dlp error messages vary; new patterns added over time.
**How to avoid:** Use substring matching (lowercase), test with real error messages from yt-dlp issues.
**Warning signs:** Users reporting unhelpful error messages.

### Pitfall 2: Verbose Leaking Raw Exceptions

**What goes wrong:** Verbose mode shows entire stack trace or raw yt-dlp output.
**Why it happens:** Using `traceback.format_exc()` without filtering.
**How to avoid:** Show only first line of `__cause__`, clean up yt-dlp formatting.
**Warning signs:** Error messages spanning multiple screens.

### Pitfall 3: Wrong HTTP Status Codes

**What goes wrong:** All YouTube errors return 400 Bad Request.
**Why it happens:** Not mapping error types to appropriate HTTP statuses.
**How to avoid:** Use proper status codes: 404 for unavailable, 429 for rate limit, 403 for age-restricted.
**Warning signs:** API consumers can't distinguish error types from status codes.

### Pitfall 4: Duplicate Error Output

**What goes wrong:** Error appears twice (Rich console + click.echo).
**Why it happens:** Current cli.py outputs to both for testing compatibility.
**How to avoid:** Use Rich for user-facing output, plain text only for testing assertions.
**Warning signs:** Users see doubled error messages.

## Code Examples

### Video ID Extraction

```python
# Source: Adapted from yt-dlp patterns
import re

def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL for error messages."""
    patterns = [
        r'(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?/]|$)',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'shorts/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return "unknown"
```

### Enhanced Exception Classes

```python
# Extend existing hierarchy
class YouTubeAgeRestrictedError(YouTubeUnavailableError):
    """Video is age-restricted and requires sign-in."""
    pass

class YouTubeGeoRestrictedError(YouTubeUnavailableError):
    """Video is not available in user's region."""
    pass

class YouTubeNetworkError(YouTubeDownloadError):
    """Network-related download failure."""
    pass
```

### Error Messages Reference

| Error Type | Message Template |
|------------|------------------|
| Invalid URL | `Invalid YouTube URL (video: {id}). The URL format is not recognized.` |
| Private | `Private video (video: {id}). This video is private and cannot be accessed.` |
| Age-restricted | `Age-restricted video (video: {id}). This video requires sign-in to verify age.` |
| Geo-restricted | `Geo-restricted video (video: {id}). This video is not available in your region.` |
| Unavailable | `Video unavailable (video: {id}). This video may have been deleted or made private.` |
| Rate limited | `YouTube is limiting requests (video: {id}). This is YouTube throttling connections. Try again later.` |
| Network timeout | `Network timeout (video: {id}). Connection timed out. Check your network and try again.` |
| Network error | `Network error (video: {id}). Could not connect to YouTube. Check your network and try again.` |
| FFmpeg missing | `FFmpeg not found. YouTube transcription requires FFmpeg.` |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Generic "download failed" | Specific error categories | This phase | Users know what went wrong |
| Plain text errors | Rich-formatted CLI errors | Already implemented | Better readability |
| Single error status code | Typed HTTP status codes | This phase | API consumers can handle errors programmatically |

## Open Questions

1. **Video ID extraction edge cases**
   - What we know: Standard patterns cover watch, shorts, youtu.be, embed
   - What's unclear: Edge cases with extra query params
   - Recommendation: Fall back to "unknown" if extraction fails

2. **yt-dlp error message stability**
   - What we know: Error messages can change between yt-dlp versions
   - What's unclear: How stable are the key phrases we match
   - Recommendation: Use loose substring matching, monitor for false negatives

## Sources

### Primary (HIGH confidence)
- yt-dlp GitHub source `yt_dlp/utils/_utils.py` - Exception class definitions
- FastAPI documentation `handling-errors` - HTTPException patterns
- Click documentation `exceptions` - CLI error handling
- Existing codebase `youtube_handler.py` - Current implementation

### Secondary (MEDIUM confidence)
- yt-dlp GitHub issues #11296, #11961, #14680 - Real error message examples
- yt-dlp GitHub issues #7376, #3771 - Network error patterns
- pyOpenSci README guidelines - Documentation structure

### Tertiary (LOW confidence)
- WebSearch results for yt-dlp error patterns - Community discussions

## Metadata

**Confidence breakdown:**
- Exception mapping: HIGH - Based on yt-dlp source and issues
- Error message style: HIGH - Locked in CONTEXT.md decisions
- API error structure: HIGH - FastAPI documentation patterns
- Network error detection: MEDIUM - Based on issue discussions, may need tuning

**Research date:** 2026-02-01
**Valid until:** 30 days (yt-dlp updates frequently, error messages may change)
