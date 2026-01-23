---
phase: 03-background-worker
plan: 01
subsystem: background-worker
tags: [asyncio, worker, job-queue, thread-pool, polling]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: Job model and JobRepository for persistence
provides:
  - BackgroundWorker class for async job processing
  - Sequential FIFO job processing with graceful shutdown
  - Thread pool integration for blocking transcription operations
  - Comprehensive worker unit tests
affects: [04-http-api, 05-cli-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Async worker loop with asyncio.Event shutdown"
    - "asyncio.to_thread() for blocking operations in async context"
    - "Polling pattern with timeout for graceful shutdown"

key-files:
  created:
    - cesar/api/worker.py
    - tests/test_worker.py
  modified:
    - cesar/api/__init__.py

key-decisions:
  - "Poll interval of 1.0s default (configurable) for repository queries"
  - "asyncio.Event for shutdown signaling (clean, non-blocking)"
  - "asyncio.to_thread() for running AudioTranscriber (avoids blocking event loop)"
  - "Temporary file creation for transcription output with cleanup in finally block"

patterns-established:
  - "Worker pattern: async run() loop with shutdown event"
  - "Job processing: QUEUED → PROCESSING → COMPLETED|ERROR state transitions"
  - "Error handling: failed jobs marked ERROR with message, worker continues"

# Metrics
duration: 2min
completed: 2026-01-23
---

# Phase 03 Plan 01: Background Worker Summary

**Async worker with FIFO job processing, thread pool transcription, and graceful shutdown via asyncio.Event**

## Performance

- **Duration:** 2 min
- **Started:** 2026-01-23T19:27:00Z
- **Completed:** 2026-01-23T19:29:20Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- BackgroundWorker class with async run() loop polling for queued jobs
- Sequential FIFO job processing (oldest queued job first)
- Blocking transcription wrapped in asyncio.to_thread() to avoid blocking event loop
- Graceful shutdown via asyncio.Event with current job completion
- 9 comprehensive unit tests covering all worker behaviors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create BackgroundWorker class** - `5ed6d14` (feat)
2. **Task 2: Create worker unit tests** - `a9f6b12` (test)

## Files Created/Modified
- `cesar/api/worker.py` - BackgroundWorker with async run loop, job processing, shutdown
- `cesar/api/__init__.py` - Export BackgroundWorker
- `tests/test_worker.py` - Comprehensive unit tests (9 tests covering all behaviors)

## Decisions Made
- **Poll interval:** Default 1.0s with configurable parameter
- **Shutdown mechanism:** asyncio.Event (clean, idiomatic async pattern)
- **Transcription execution:** asyncio.to_thread() prevents blocking event loop
- **Temp file cleanup:** Finally block ensures cleanup even on transcription error
- **Property access:** is_processing and current_job_id for external monitoring

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly following research patterns.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 4: HTTP API**
- Worker processes jobs from repository ✓
- FIFO order guaranteed via created_at ASC ✓
- Graceful shutdown works ✓
- Error handling marks jobs as ERROR ✓
- All tests pass (81 total, 9 new worker tests) ✓

**Next steps:**
- Phase 4 will wrap worker in FastAPI server with /jobs endpoints
- Worker will run as background task during server lifecycle
- API endpoints will create jobs, worker will process them

---
*Phase: 03-background-worker*
*Completed: 2026-01-23*
