---
phase: 14-whisperx-foundation
plan: 01
subsystem: dependencies
tags: [whisperx, pyannote, torch, diarization, transcription]

# Dependency graph
requires:
  - phase: 13-api-integration
    provides: Working diarization pipeline with pyannote.audio
provides:
  - WhisperX package installed and importable
  - Unified dependency for transcription + diarization
  - Simplified dependency management (whisperx bundles pyannote)
affects: [14-02, 14-03, 15-orchestrator-simplification]

# Tech tracking
tech-stack:
  added: [whisperx>=3.7.6, pyannote-audio-3.4.0 (transitive), torch-2.8.0 (transitive)]
  patterns: [unified-ml-pipeline, transitive-dependency-management]

key-files:
  created: []
  modified: [pyproject.toml]

key-decisions:
  - "Remove direct pyannote.audio dependency (whisperx bundles it)"
  - "Keep faster-whisper for backward compatibility (existing transcriber uses it)"
  - "Install torchvision 0.23.0 to match torch 2.8.0 (version compatibility)"

patterns-established:
  - "WhisperX as unified ML pipeline dependency"

# Metrics
duration: 4min
completed: 2026-02-01
---

# Phase 14 Plan 01: WhisperX Dependency Setup Summary

**Replaced pyannote.audio with whisperx>=3.7.6, simplifying dependency management for unified transcription+diarization pipeline**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-01T22:00:00Z
- **Completed:** 2026-02-01T22:04:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Removed direct pyannote.audio>=3.1.0 dependency from pyproject.toml
- Added whisperx>=3.7.6 to pyproject.toml
- Verified whisperx installs and imports successfully
- Confirmed pyannote.audio bundled transitively (version 3.4.0)
- Verified existing cesar modules still import correctly

## Task Commits

Each task was committed atomically:

1. **Task 1: Update pyproject.toml dependencies** - `20e0d87` (chore)
2. **Task 2: Verify installation in virtual environment** - (verification only, no commit)

## Files Created/Modified
- `pyproject.toml` - Replaced pyannote.audio with whisperx dependency

## Decisions Made
- **Remove pyannote.audio direct dependency:** WhisperX bundles pyannote-audio transitively, keeping both can cause version conflicts
- **Keep faster-whisper:** Existing transcriber.py uses it directly; Phase 15 will determine if fully migrated to WhisperX
- **Install torchvision 0.23.0:** Required for torch 2.8.0 compatibility (default 0.22.1 caused operator errors)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed torchvision/torch version mismatch**
- **Found during:** Task 2 (Verify installation)
- **Issue:** Initial pip install brought in torch 2.8.0 but existing torchvision 0.22.1 was incompatible, causing "operator torchvision::nms does not exist" error
- **Fix:** Installed compatible versions: torch==2.8.0, torchaudio==2.8.0, torchvision==0.23.0
- **Files modified:** None (virtual environment only)
- **Verification:** All imports succeed (whisperx, pyannote.audio, torch)
- **Committed in:** N/A (runtime environment fix, not source code)

---

**Total deviations:** 1 auto-fixed (blocking)
**Impact on plan:** Version alignment was necessary for correct operation. No scope creep.

## Issues Encountered
- torchaudio deprecation warning about `list_audio_backends` - informational only, does not affect functionality

## Next Phase Readiness
- WhisperX dependency ready for use
- Plan 14-02 can proceed to create WhisperX transcription wrapper
- pyannote.audio Pipeline still available for existing diarization code until migration

---
*Phase: 14-whisperx-foundation*
*Completed: 2026-02-01*
