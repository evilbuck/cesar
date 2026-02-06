---
phase: 13-api-integration
plan: 02
subsystem: api
tags: [diarization, worker, orchestrator, hf-token, pyannote, partial-status]

# Dependency graph
requires:
  - phase: 13-01
    provides: Job model with PARTIAL status, diarization parameters, progress tracking
  - phase: 11
    provides: TranscriptionOrchestrator for coordinated pipeline
  - phase: 10
    provides: SpeakerDiarizer with AuthenticationError handling
provides:
  - Worker orchestrator integration for API diarization
  - HF token resolution from config/env/cache
  - Progress tracking at phase boundaries
  - PARTIAL status handling for diarization failures
  - Retry endpoint for partial jobs
affects: [13-03, api-endpoints, error-handling]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Worker uses orchestrator when diarize=True"
    - "HF token resolution hierarchy: config > env > cache"
    - "PARTIAL status for transcription OK, diarization failed"
    - "Phase-based progress tracking (downloading/transcribing/diarizing/formatting)"

key-files:
  created: []
  modified:
    - "cesar/api/worker.py"
    - "cesar/api/server.py"
    - "tests/test_worker.py"

key-decisions:
  - "Use _run_transcription_with_orchestrator for all jobs (orchestrator handles diarize=False)"
  - "Catch AuthenticationError specifically for hf_token_invalid error code"
  - "Set PARTIAL status when diarization_succeeded=False and diarize=True"
  - "Track retry scenario via result_text + diarization_error presence"

patterns-established:
  - "Worker method signature: (audio_path, model_size, diarize, min_speakers, max_speakers, is_retry)"
  - "Result dict keys: text, language, diarization_succeeded, speaker_count, diarization_error_code, diarization_error"
  - "Progress phases: downloading, transcribing, diarizing, formatting"

# Metrics
duration: 7min
completed: 2026-02-01
---

# Phase 13 Plan 02: Worker Integration Summary

**Worker orchestrator integration with HF token resolution, progress tracking, PARTIAL status handling, and retry endpoint for failed diarization**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-01T22:49:52Z
- **Completed:** 2026-02-01T22:56:38Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Worker uses TranscriptionOrchestrator when diarize=True with full pipeline
- HF token resolved from config, env var, or cached file in priority order
- Jobs get PARTIAL status when transcription succeeds but diarization fails
- AuthenticationError caught and mapped to hf_token_invalid error code
- Progress tracking at phase boundaries (downloading/transcribing/diarizing/formatting)
- Retry endpoint added for re-queuing PARTIAL jobs

## Task Commits

Each task was committed atomically:

1. **Task 1: Integrate orchestrator into worker** - `587a365` (feat)
2. **Task 2: Add progress tracking** - included in `587a365` (integrated with Task 1)
3. **Task 2b: Add retry endpoint** - `a73d12e` (feat)
4. **Task 3: Add worker diarization tests** - `5f3ce6b` (test)

## Files Created/Modified

- `cesar/api/worker.py` - Added orchestrator integration, HF token resolution, progress tracking, PARTIAL handling
- `cesar/api/server.py` - Added POST /jobs/{id}/retry endpoint for re-queuing partial jobs
- `tests/test_worker.py` - Added 11 new tests for diarization and HF token resolution

## Decisions Made

- **Orchestrator for all jobs:** _run_transcription_with_orchestrator handles both diarize=True and diarize=False paths consistently
- **Error code mapping:** AuthenticationError maps to hf_token_invalid, DiarizationError maps to diarization_failed
- **Retry detection:** Jobs with result_text AND diarization_error are considered retry scenarios
- **Progress updates:** Updated at phase boundaries only (not real-time) to avoid sync/async callback complexity

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Linter removed unused imports during initial edits, requiring re-addition after methods were implemented
- No functional issues during execution

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Worker fully supports diarization with graceful fallback
- Ready for Plan 03: API endpoint updates and OpenAPI documentation
- Retry endpoint available for PARTIAL job recovery

---
*Phase: 13-api-integration*
*Completed: 2026-02-01*
