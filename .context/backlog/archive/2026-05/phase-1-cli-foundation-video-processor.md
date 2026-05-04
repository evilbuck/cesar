---
title: Phase 1 - CLI Foundation & Video Processor
status: completed
priority: high
created: 2026-05-02
updated: 2026-05-02
completed: 2026-05-02
related:
  - .context/2026-05-02.screen-recording-agent-processor/plan-agent-review-mode-phases.md
  - .context/memory/phase-1-cli-video-processor-2026-05-02.md
---

# Phase 1: CLI Foundation & Video Processor

Add `--mode` flag to CLI and create FFmpeg video wrapper for frame extraction.

## Files
- `cesar/cli.py` — Add `--mode` flag and agent-review options
- `cesar/video_processor.py` — FFmpeg wrapper for frame extraction
- `tests/test_video_processor.py` — Unit tests for video processor
- `tests/test_cli.py` — Added TestTranscriptionModes (6 tests)

## Acceptance Criteria
- [x] `cesar transcribe --help` shows `--mode` option
- [x] `--mode agent-review` shows: `--screenshots-interval`, `--speech-cues`, `--scene-threshold`, `--no-scene-detection`
- [x] `video_processor.py` extracts frames at timestamps
- [x] `video_processor.py` returns video duration
- [x] Graceful error if input is not a video file
- [x] Tests pass (19 video processor tests, 6 CLI mode tests)

## Notes
- Mode validation rejects YouTube URLs in agent-review mode
- FFmpeg availability check added to agent-review mode
- All 45 CLI tests pass
