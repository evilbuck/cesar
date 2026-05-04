---
date: 2026-05-03
domains: [bugfix, testing]
topics: [ffmpeg, mp4, video-formats, validation, transcriber]
related: []
priority: medium
status: completed
---

# Session: Fix MP4 support in agent-review mode

## Problem
When using `cesar transcribe video.mp4 -o review.md --mode agent-review`, cesar rejected mp4 files with "Unsupported audio format: .mp4" even though:
- The skill documentation claims mp4 is supported
- The underlying faster-whisper and whisperx libraries use ffmpeg and can handle video files
- The `VideoProcessor` already supports mp4 for screenshot extraction

## Root Cause
`AudioTranscriber.validate_input_file()` checked against a hardcoded `SUPPORTED_FORMATS` set containing only audio extensions (`{'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma'}`). When the `AgentReviewOrchestrator` passed the video path to the transcriber, validation failed.

## Solution
Rewrote `validate_input_file` to use `ffprobe` (when available) to verify the file is actually readable by FFmpeg, instead of relying on extension checks. This means **any format supported by the user's installed FFmpeg will now work**.

Fallback behavior: if `ffprobe` is not on PATH, falls back to the expanded extension list.

## Files Changed
- `cesar/transcriber.py`
  - Added `shutil` import
  - Expanded `SUPPORTED_FORMATS` to include video extensions
  - Rewrote `validate_input_file` with ffprobe-based validation
- `tests/test_validation.py`
  - Updated tests to mock ffprobe availability
  - Added `test_validate_input_file_with_ffprobe`
  - Updated `test_supported_formats` to check both audio and video formats

## Verification
```bash
python -m pytest tests/test_validation.py tests/test_transcription.py tests/test_orchestrator.py tests/test_video_processor.py tests/test_cli.py -v -k "not TestSkillInstall and not TestServeCommand"
# Result: 88 passed, 5 deselected
```

Full suite has 9 pre-existing failures unrelated to this change (skill install duplicate blocking, serve command uvicorn mocking).
