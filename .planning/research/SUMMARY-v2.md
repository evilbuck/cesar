# Research Summary: v2.0 API

**Project:** Cesar v2.0 - Async HTTP API
**Domain:** Async job-based transcription API
**Researched:** 2026-01-23
**Confidence:** HIGH

## Executive Summary

Cesar v2.0 adds an HTTP API layer with async job queue for programmatic transcription access. The key architectural challenge is running CPU-bound faster-whisper transcriptions within an async FastAPI context without blocking the event loop.

**Recommended approach:** FastAPI serves HTTP requests. Jobs are persisted to SQLite (via aiosqlite). A background worker claims pending jobs and runs transcription via `run_in_threadpool`. Sequential processing (one job at a time) avoids memory pressure and GIL contention.

## Key Findings

### Stack (STACK-API.md)

| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | >=0.128.0 | HTTP framework with automatic OpenAPI |
| aiosqlite | >=0.22.0 | Async SQLite for job persistence |
| httpx | >=0.28.0 | Async HTTP client for webhooks (bundled with FastAPI) |
| pydantic-settings | >=2.0.0 | Environment configuration |

**Key insight:** Use `run_in_threadpool` (not ProcessPoolExecutor) for single-process constraint. Transcription runs in thread, event loop stays responsive.

**Avoid:** Celery/Redis (violates offline-first), FastAPI BackgroundTasks (blocks event loop for CPU work), synchronous sqlite3.

### Features (FEATURES.md)

**Table Stakes:**
- `POST /transcribe` (file upload + URL reference)
- `GET /jobs/{id}` (status and results)
- Four job states: queued, processing, completed, error
- 202 Accepted with Location header
- Error details in response body (not HTTP status)

**Include in v2.0:**
- Model selection (already in CLI)
- Language detection (free from faster-whisper)
- Word-level timestamps (free from faster-whisper)

**Skip:**
- Authentication (internal service)
- Rate limiting (internal service)
- Speaker diarization (complex, v3+)
- Real-time streaming (different architecture)

### Architecture (ARCHITECTURE.md)

**Components:**
```
HTTP Endpoints (routes.py)
    │
    v
TranscriptionService (service.py)
    │
    ├──> JobRepository (repository.py) ──> SQLite
    │
    └──> UploadManager (uploads.py) ──> Temp files

BackgroundWorker (worker.py)
    │
    └──> AudioTranscriber (existing, unchanged)
```

**Data flow:**
1. Client POSTs to /transcribe
2. File saved, job created (status=PENDING), 202 returned
3. Background worker claims job, runs transcription in thread
4. Result stored, status updated to COMPLETED
5. Client polls GET /jobs/{id} for result

**SQLite schema:** jobs table with id, status, input_path, timestamps, result_json

### Pitfalls (PITFALLS-API.md)

**Critical (must address):**
1. **CP-1: Event loop blocking** - Use `run_in_threadpool` for transcription
2. **CP-2: SQLite write contention** - WAL mode, busy_timeout, BEGIN IMMEDIATE
3. **CP-3: Zombie jobs** - Heartbeat tracking, recovery on startup

**File handling:**
- FH-1: Stream uploads to disk (don't load into memory)
- FH-2: Clean up temp files on completion/failure
- FH-3: Always close UploadFile handles

**Job queue:**
- JQ-1: Atomic job creation (file + db together)
- JQ-2: Idempotent processing (check for existing output)

## Implications for Roadmap

**Suggested phases:**

1. **Foundation** - Models, SQLite repository, config
2. **File Handling** - UploadManager with streaming, cleanup
3. **Background Worker** - Job processor with thread pool
4. **HTTP Layer** - FastAPI routes, service layer
5. **CLI Integration** - `cesar serve` command
6. **Polish** - OpenAPI docs, webhooks (optional)

**Dependencies:**
- Repository before Worker (worker claims from repository)
- Worker before App (lifespan spawns worker)
- Routes depend on Service, which depends on Repository + Uploads

## Confidence Assessment

| Area | Level | Notes |
|------|-------|-------|
| Stack choices | HIGH | Official docs, established patterns |
| Job lifecycle | HIGH | Industry standard (AssemblyAI, Deepgram) |
| Architecture | HIGH | Standard FastAPI patterns |
| Pitfall prevention | HIGH | Verified via multiple sources |
| Worker pattern | MEDIUM | Custom implementation, needs testing |

## Open Questions

1. **Progress reporting:** Should API show progress percentage? (Adds IPC complexity)
2. **URL downloads:** Download in main process or worker? (Suggest: main process)
3. **Model caching:** Keep model warm between jobs? (Suggest: yes, saves load time)
4. **Job retention:** How long to keep completed jobs? (Suggest: 1 hour)

---
*Research completed: 2026-01-23*
*Ready for requirements definition*
