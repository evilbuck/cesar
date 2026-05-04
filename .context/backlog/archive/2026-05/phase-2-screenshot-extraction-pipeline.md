---
title: Phase 2 - Screenshot Extraction Pipeline
status: completed
priority: high
created: 2026-05-02
updated: 2026-05-03
completed: 2026-05-03
related:
  - .context/2026-05-02.screen-recording-agent-processor/plan-agent-review-mode-phases.md
  - .context/memory/phase-1-cli-video-processor-2026-05-02.md
---

# Phase 2: Screenshot Extraction Pipeline

Implement all three trigger mechanisms: scene detection, speech cues, time-based.

## Files
- `cesar/ffmpeg_scene_detector.py` ✅ (new)
- `cesar/speech_cue_detector.py` ✅ (new)
- `cesar/video_processor.py` (no changes needed)
- `tests/test_scene_detector.py` ✅ (30 tests)
- `tests/test_speech_cue_detector.py` ✅ (22 tests)

## Acceptance Criteria
- [x] Scene detection returns timestamps (graceful fallback if unavailable)
- [x] Speech cue detection finds cue words in transcript
- [x] Time-based sampling at interval (default 30s)
- [x] Deduplicated combined timestamp list
- [x] Screenshots named `{name}_{HH-MM-SS}.png`
- [x] Tests pass (52 new tests)
