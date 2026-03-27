---
phase: 13-api-integration
plan: 01
subsystem: api
tags: [pydantic, sqlite, diarization, job-queue]

# Dependency graph
requires:
  - phase: 10-speaker-diarization
    provides: Diarization core functionality with pyannote.audio
  - phase: 11-orchestration
    provides: Progress reporting phases (transcribing, diarizing, formatting)
provides:
  - Extended Job model with diarization parameters
  - PARTIAL status for partial failure handling
  - Database schema with diarization columns
  - Repository CRUD for all diarization fields
affects: [13-02, 13-03, worker, endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - model_validator for cross-field validation (min_speakers <= max_speakers)
    - SQLite boolean storage as INTEGER (1/0/NULL)

key-files:
  created: []
  modified:
    - cesar/api/models.py
    - cesar/api/database.py
    - cesar/api/repository.py
    - tests/test_models.py

key-decisions:
  - "PARTIAL status for transcription OK, diarization failed"
  - "diarize defaults to True (matches CLI behavior)"
  - "Progress tracking with overall, phase, and phase_pct fields"
  - "Explicit diarized boolean flag for fallback detection"

patterns-established:
  - "Boolean to SQLite: 1 if True else (0 if False else None)"
  - "Column order in schema matches _row_to_job indices"

# Metrics
duration: 5min
completed: 2026-02-01
---

# Phase 13 Plan 01: Data Layer Foundation Summary

**Extended Job model with diarization parameters, progress tracking, and PARTIAL status; updated database schema and repository CRUD**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-01T17:32:00Z
- **Completed:** 2026-02-01T17:37:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Job model accepts diarization parameters (diarize, min/max_speakers)
- Progress tracking with overall, phase, and phase-level progress
- PARTIAL status enables graceful degradation when diarization fails
- Speaker count and diarized flag track results
- Comprehensive test coverage for all new fields

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Job model with diarization fields** - `d6513b2` (feat)
2. **Task 2: Update database schema with diarization columns** - `df68943` (feat)
3. **Task 3: Update repository for diarization fields** - `cd9cd63` (feat)

## Files Created/Modified
- `cesar/api/models.py` - Extended Job model with 10 new fields, PARTIAL status, speaker range validator
- `cesar/api/database.py` - Added 10 new columns to jobs table schema
- `cesar/api/repository.py` - Updated create(), update(), _row_to_job() for all 21 columns
- `tests/test_models.py` - Added TestDiarizationFields class with 21 new tests

## Decisions Made
- diarize defaults to True (matches CLI default from Phase 12)
- PARTIAL status value is "partial" (lowercase, consistent with other statuses)
- Progress fields: overall progress (0-100), phase name, phase progress (0-100)
- diarized is Optional[bool] for tri-state: True (diarized), False (fallback), None (pending)
- diarization_error_code uses snake_case: hf_token_required, hf_token_invalid, diarization_failed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Data layer complete for diarization integration
- Worker (13-02) can now track progress and store results
- Endpoints (13-03) can accept diarization parameters

---
*Phase: 13-api-integration*
*Completed: 2026-02-01*
