---
phase: 05-cli-integration
plan: 01
subsystem: cli
tags: [click, uvicorn, fastapi, server, job-recovery]

# Dependency graph
requires:
  - phase: 04-http-api
    provides: FastAPI server with worker and job endpoints
provides:
  - cesar serve command with host/port/reload/workers options
  - Job recovery on server startup (re-queue orphaned PROCESSING jobs)
  - Comprehensive CLI and recovery tests
affects: [05-02, deployment, user-facing-api]

# Tech tracking
tech-stack:
  added: [uvicorn]
  patterns: [Job recovery pattern for crash resilience, Graceful shutdown with 30s timeout]

key-files:
  created: [tests/test_serve.py]
  modified: [cesar/cli.py, cesar/api/server.py]

key-decisions:
  - "Use import string 'cesar.api.server:app' instead of app instance for reload support"
  - "Clear started_at timestamp when re-queuing orphaned jobs"
  - "30 second graceful shutdown timeout for in-flight requests"

patterns-established:
  - "Server startup job recovery: re-queue PROCESSING jobs left from crashes"
  - "CLI serve pattern: minimal startup message with listening URL"

# Metrics
duration: 2min
completed: 2026-01-23
---

# Phase 5 Plan 1: CLI Server Integration Summary

**cesar serve command starts HTTP API with configurable options and automatic job recovery on startup**

## Performance

- **Duration:** 2 min
- **Started:** 2026-01-23T16:20:40Z
- **Completed:** 2026-01-23T16:22:54Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- cesar serve command with --port, --host, --reload, --workers flags
- Job recovery logic re-queues orphaned PROCESSING jobs on server startup
- Comprehensive test coverage for CLI options and recovery logic
- All 124 tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add serve command and job recovery logic** - `5203257` (feat)
2. **Task 2: Add serve command tests** - `0d2176f` (test)

## Files Created/Modified
- `cesar/cli.py` - Added serve command with uvicorn integration
- `cesar/api/server.py` - Added job recovery logic to lifespan
- `tests/test_serve.py` - Comprehensive tests for serve command and recovery

## Decisions Made

1. **Import string for reload support:** Use `"cesar.api.server:app"` string instead of app instance. Uvicorn's reload feature requires import string to re-import the app on code changes.

2. **Clear started_at on recovery:** When re-queuing orphaned jobs, set `started_at = None` to indicate job hasn't actually started processing yet. Preserves accurate timestamp semantics.

3. **30-second graceful shutdown:** Set `timeout_graceful_shutdown=30` to allow in-flight requests to complete. Balances user experience with shutdown speed.

4. **Minimal startup message:** Print only `"Listening on http://{host}:{port}"` per CONTEXT.md. No ASCII art, no docs URL. Users discover /docs naturally.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Server lifecycle complete. Ready for:
- CLI unification (cesar transcribe integration with API)
- Deployment configuration
- Production deployment

All v2.0 API functionality accessible via `cesar serve` command.

---
*Phase: 05-cli-integration*
*Completed: 2026-01-23*
