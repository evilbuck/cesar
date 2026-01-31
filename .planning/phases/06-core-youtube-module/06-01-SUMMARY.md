---
phase: 06-core-youtube-module
plan: 01
subsystem: api
tags: [youtube, yt-dlp, ffmpeg, audio-extraction]

# Dependency graph
requires:
  - phase: 05-server-command
    provides: "REST API foundation for future YouTube endpoint integration"
provides:
  - "youtube_handler.py module with URL validation and audio download"
  - "FFmpeg validation with lru_cache for efficient repeated checks"
  - "Custom exceptions for YouTube-specific error handling"
  - "Temp file cleanup utilities for orphaned downloads"
affects: [07-youtube-api-integration, 08-youtube-cli-integration]

# Tech tracking
tech-stack:
  added: [yt-dlp>=2024.1.0]
  patterns: [lru_cache for system binary validation, UUID-based temp files, exception hierarchy]

key-files:
  created:
    - cesar/youtube_handler.py
    - tests/test_youtube_handler.py
  modified:
    - pyproject.toml

key-decisions:
  - "Use m4a format for audio extraction (smaller than wav, compatible with faster-whisper)"
  - "UUID-based temp filenames to avoid collisions in concurrent downloads"
  - "lru_cache on check_ffmpeg_available() for fast repeated validation"
  - "Separate cleanup utilities so callers can manage temp file lifecycle"

patterns-established:
  - "Exception hierarchy: YouTubeDownloadError base, specific subclasses for URL/unavailable/rate-limit/ffmpeg"
  - "require_X() pattern: call check_X(), raise if not available"
  - "Partial file cleanup on any download failure"

# Metrics
duration: 3min
completed: 2026-01-31
---

# Phase 6 Plan 01: Core YouTube Module Summary

**yt-dlp based YouTube audio extractor with FFmpeg validation, URL pattern matching, and comprehensive error handling**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-31T23:10:37Z
- **Completed:** 2026-01-31T23:13:16Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Created youtube_handler.py module with 5 exception classes and 6 public functions
- Comprehensive URL validation for watch, shorts, youtu.be, embed, and /v/ formats
- FFmpeg binary detection with cached results and helpful install instructions
- download_youtube_audio() with yt-dlp context manager and automatic cleanup on failure
- 33 unit tests covering all code paths with full mocking (no real network requests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create youtube_handler.py module** - `d1a127e` (feat)
2. **Task 2: Create unit tests for youtube_handler** - `af25742` (test)
3. **Task 3: Verify all existing tests still pass** - (verification only, no code changes)

## Files Created/Modified
- `cesar/youtube_handler.py` - YouTube audio download module with yt-dlp integration
- `tests/test_youtube_handler.py` - 33 unit tests for youtube_handler module
- `pyproject.toml` - Added yt-dlp>=2024.1.0 dependency

## Decisions Made
- Used m4a codec for audio extraction (good quality, smaller than wav, faster-whisper compatible)
- UUID-based temp filenames for collision-free concurrent downloads
- lru_cache on FFmpeg check for fast repeated validation during server lifetime
- Caller manages cleanup (download returns path, caller deletes after transcription)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed successfully on first attempt.

## User Setup Required

**FFmpeg is a system dependency.** Users must install FFmpeg before using YouTube transcription:
- Arch Linux: `pacman -S ffmpeg`
- Debian/Ubuntu: `apt install ffmpeg`
- macOS: `brew install ffmpeg`

The module provides clear error messages with install instructions if FFmpeg is missing.

## Next Phase Readiness
- youtube_handler.py provides complete YouTube download capability
- Ready for Phase 7: CLI integration (`cesar transcribe <youtube-url>`)
- Ready for Phase 7: API integration (`POST /transcribe/url` with YouTube support)
- Worker will need modification to call download_youtube_audio() for YouTube URLs

---
*Phase: 06-core-youtube-module*
*Completed: 2026-01-31*
