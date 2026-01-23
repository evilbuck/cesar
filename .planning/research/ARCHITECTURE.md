# Architecture Research: Async Transcription API

**Domain:** HTTP API layer for offline audio transcription
**Researched:** 2026-01-23
**Confidence:** HIGH (verified with FastAPI official docs, established patterns)

## Executive Summary

The cesar v2.0 API must wrap the existing synchronous `AudioTranscriber` class with an async HTTP layer. The key challenge: faster-whisper's `transcribe()` is CPU-bound and blocks for seconds to minutes. The solution uses a **background worker thread** started via FastAPI's lifespan events, processing jobs from a **SQLite-backed queue**.

This architecture avoids external dependencies (no Redis, no Celery) while providing:
- Non-blocking API endpoints (instant job submission)
- Persistent job queue (survives process restarts)
- Progress tracking and result retrieval
- File upload with automatic cleanup

## Component Design

### Component Diagram

```
                                    FastAPI Application
    +------------------------------------------------------------------------+
    |                                                                        |
    |   +-----------------+      +--------------------+                      |
    |   |  HTTP Endpoints |      |   TranscriptionSvc |                      |
    |   |  (api.py)       |----->|   (service.py)     |                      |
    |   +-----------------+      +--------------------+                      |
    |          |                         |                                   |
    |          |                         v                                   |
    |          |               +--------------------+                        |
    |          |               |    JobRepository   |                        |
    |          |               |   (repository.py)  |                        |
    |          |               +--------------------+                        |
    |          |                         |                                   |
    |          v                         v                                   |
    |   +-----------------+      +--------------------+                      |
    |   |  UploadManager  |      |     SQLite DB      |                      |
    |   |  (uploads.py)   |      |   (jobs.db)        |                      |
    |   +-----------------+      +--------------------+                      |
    |          |                         ^                                   |
    |          v                         |                                   |
    |   +-----------------+      +--------------------+      +-------------+ |
    |   |  Temp Files     |      |  BackgroundWorker  |----->| AudioTrans- | |
    |   |  (uploads/)     |      |  (worker.py)       |      | criber      | |
    |   +-----------------+      +--------------------+      +-------------+ |
    |                                                                        |
    +------------------------------------------------------------------------+
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| HTTP Endpoints | `cesar/api/routes.py` | Request handling, validation, response formatting |
| TranscriptionService | `cesar/api/service.py` | Job orchestration, business logic |
| JobRepository | `cesar/api/repository.py` | SQLite CRUD operations for jobs |
| BackgroundWorker | `cesar/api/worker.py` | Async task processor, runs AudioTranscriber |
| UploadManager | `cesar/api/uploads.py` | File storage, cleanup, validation |
| Database Models | `cesar/api/models.py` | Pydantic models and enums |

### Package Structure

```
cesar/
├── __init__.py
├── __main__.py
├── cli.py                    # Existing CLI (unchanged)
├── transcriber.py            # Existing AudioTranscriber (unchanged)
├── device_detection.py       # Existing (unchanged)
├── utils.py                  # Existing (unchanged)
└── api/                      # NEW: API module
    ├── __init__.py
    ├── app.py                # FastAPI app factory with lifespan
    ├── routes.py             # HTTP endpoint definitions
    ├── service.py            # TranscriptionService class
    ├── repository.py         # JobRepository (SQLite operations)
    ├── worker.py             # BackgroundWorker class
    ├── uploads.py            # UploadManager class
    ├── models.py             # Pydantic models, enums
    └── config.py             # API configuration
```

## Data Flow

### Job Submission Flow

```
1. Client POST /transcribe (file upload)
         │
         v
2. UploadManager.save_upload()
   - Validate file type/size
   - Write to temp storage
   - Return upload path
         │
         v
3. TranscriptionService.create_job()
   - Generate UUID
   - Create job record (status=PENDING)
   - Return job_id immediately
         │
         v
4. Client receives 202 Accepted
   - Response: { "job_id": "uuid", "status": "pending" }
```

### Job Processing Flow

```
1. BackgroundWorker (running in lifespan)
   - Polls JobRepository every N seconds
   - Claims next PENDING job
         │
         v
2. JobRepository.claim_job(job_id)
   - UPDATE status=PROCESSING, started_at=now()
   - Return job details
         │
         v
3. loop.run_in_executor(None, transcriber.transcribe_file, ...)
   - Runs synchronous AudioTranscriber in thread
   - Does NOT block event loop
         │
         v
4. On completion:
   - JobRepository.complete_job(job_id, result)
   - UploadManager.cleanup(job_id)  [optional, configurable]
   - Webhook callback if configured
```

### Status Polling Flow

```
1. Client GET /jobs/{job_id}
         │
         v
2. JobRepository.get_job(job_id)
         │
         v
3. Return job state:
   - PENDING: { status, created_at, position_in_queue }
   - PROCESSING: { status, started_at, progress? }
   - COMPLETED: { status, result, completed_at }
   - FAILED: { status, error, failed_at }
```

## SQLite Schema

### Jobs Table

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,           -- UUID
    status TEXT NOT NULL,          -- PENDING, PROCESSING, COMPLETED, FAILED

    -- Input configuration
    input_path TEXT NOT NULL,      -- Path to uploaded/downloaded file
    input_source TEXT NOT NULL,    -- 'upload' or 'url'
    model_size TEXT DEFAULT 'base',
    device TEXT DEFAULT 'auto',
    compute_type TEXT DEFAULT 'auto',

    -- Optional parameters
    webhook_url TEXT,
    start_time_seconds REAL,
    end_time_seconds REAL,
    max_duration_minutes INTEGER,

    -- Timestamps
    created_at TEXT NOT NULL,      -- ISO 8601
    started_at TEXT,
    completed_at TEXT,

    -- Results
    result_json TEXT,              -- JSON blob with transcription result
    error_message TEXT,

    -- Indexes for common queries
    CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'))
);

CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
```

### Why SQLite (Not In-Memory)

| Consideration | In-Memory Dict | SQLite |
|---------------|----------------|--------|
| Persistence | Lost on restart | Survives restart |
| Concurrent access | Needs locks | Built-in |
| Query flexibility | Manual filtering | SQL queries |
| Memory footprint | Grows unbounded | Bounded by disk |
| Complexity | Simple | Slightly more setup |

**Recommendation:** SQLite is worth the small complexity increase for persistence across restarts.

### aiosqlite Integration

```python
# repository.py
import aiosqlite
from pathlib import Path

class JobRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def init_db(self):
        """Initialize database schema"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(SCHEMA_SQL)
            await db.commit()

    async def create_job(self, job: Job) -> str:
        """Insert new job, return job_id"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO jobs (...) VALUES (...)",
                job.to_row()
            )
            await db.commit()
        return job.id

    async def claim_next_pending(self) -> Optional[Job]:
        """Atomically claim next pending job for processing"""
        async with aiosqlite.connect(self.db_path) as db:
            # Use RETURNING for atomic claim
            cursor = await db.execute("""
                UPDATE jobs
                SET status = 'PROCESSING', started_at = ?
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE status = 'PENDING'
                    ORDER BY created_at
                    LIMIT 1
                )
                RETURNING *
            """, (datetime.utcnow().isoformat(),))
            row = await cursor.fetchone()
            await db.commit()
            return Job.from_row(row) if row else None
```

**Note:** SQLite's `RETURNING` clause (added in 3.35) enables atomic claim-and-return operations.

## File Handling

### Upload Storage Strategy

```
~/.cesar/                        # Or configurable via env
├── uploads/                     # Uploaded audio files
│   ├── {job_id}/
│   │   └── input.{ext}
│   └── ...
├── results/                     # Optional: persist transcription results
│   └── {job_id}.txt
└── jobs.db                      # SQLite database
```

### File Lifecycle

```
1. UPLOAD
   - Client uploads file via multipart form
   - UploadManager validates (size, MIME type, magic bytes)
   - File saved to uploads/{job_id}/input.{ext}
   - Path stored in job record

2. PROCESSING
   - BackgroundWorker reads from stored path
   - AudioTranscriber processes (no changes to existing code)
   - Result written to job record (result_json)

3. CLEANUP (Configurable)
   Option A: Immediate cleanup after completion
   - Delete uploads/{job_id}/ when job completes

   Option B: Retention period
   - Cleanup task deletes files older than N hours

   Option C: Manual cleanup
   - DELETE /jobs/{job_id} removes files
```

### UploadManager Implementation

```python
# uploads.py
class UploadManager:
    ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac'}
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB default

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_upload(
        self,
        job_id: str,
        file: UploadFile
    ) -> Path:
        """Save uploaded file, return path"""
        # Validate extension
        ext = Path(file.filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported format: {ext}")

        # Create job directory
        job_dir = self.base_path / job_id
        job_dir.mkdir(exist_ok=True)

        # Save file with streaming (memory efficient)
        file_path = job_dir / f"input{ext}"
        async with aiofiles.open(file_path, 'wb') as out:
            while chunk := await file.read(8192):
                await out.write(chunk)

        return file_path

    async def cleanup_job(self, job_id: str) -> None:
        """Remove all files for a job"""
        job_dir = self.base_path / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
```

## Integration with Existing Code

### Principle: Minimal Changes to Existing Code

The existing `AudioTranscriber` class works well. The API layer wraps it without modification.

### Running Synchronous Code in Async Context

**Pattern:** Use `loop.run_in_executor()` to run `AudioTranscriber.transcribe_file()` without blocking.

```python
# worker.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from cesar.transcriber import AudioTranscriber

class BackgroundWorker:
    def __init__(self, repository: JobRepository, upload_manager: UploadManager):
        self.repository = repository
        self.upload_manager = upload_manager
        self.executor = ThreadPoolExecutor(max_workers=1)  # Single transcription at a time
        self._running = False

    async def process_job(self, job: Job) -> dict:
        """Run transcription in thread pool"""
        loop = asyncio.get_running_loop()

        # Create transcriber with job's configuration
        transcriber = AudioTranscriber(
            model_size=job.model_size,
            device=job.device if job.device != 'auto' else None,
            compute_type=job.compute_type if job.compute_type != 'auto' else None,
        )

        # Run blocking transcription in executor
        result = await loop.run_in_executor(
            self.executor,
            transcriber.transcribe_file,
            str(job.input_path),
            str(self._get_output_path(job)),
            None,  # progress_callback (not used in API)
            job.max_duration_minutes,
            job.start_time_seconds,
            job.end_time_seconds,
        )

        return result
```

**Why ThreadPoolExecutor with 1 worker:**
- faster-whisper is CPU/GPU intensive
- Running multiple transcriptions simultaneously causes memory pressure
- Sequential processing is more predictable
- Can increase workers if hardware allows

### FastAPI Lifespan Integration

```python
# app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services
    config = APIConfig.from_env()

    repository = JobRepository(config.db_path)
    await repository.init_db()

    upload_manager = UploadManager(config.upload_path)

    worker = BackgroundWorker(repository, upload_manager)
    worker_task = asyncio.create_task(worker.run())

    # Store in app state for route access
    app.state.repository = repository
    app.state.upload_manager = upload_manager
    app.state.service = TranscriptionService(repository, upload_manager)

    yield  # Application runs here

    # Shutdown: Clean up
    worker.stop()
    await worker_task
    worker.executor.shutdown(wait=True)

app = FastAPI(lifespan=lifespan)
```

### Worker Loop Pattern

```python
# worker.py (continued)
class BackgroundWorker:
    async def run(self):
        """Main worker loop - polls for pending jobs"""
        self._running = True

        while self._running:
            try:
                # Claim next pending job
                job = await self.repository.claim_next_pending()

                if job:
                    try:
                        result = await self.process_job(job)
                        await self.repository.complete_job(job.id, result)

                        # Webhook callback if configured
                        if job.webhook_url:
                            await self._send_webhook(job, result)

                    except Exception as e:
                        await self.repository.fail_job(job.id, str(e))

                    finally:
                        # Cleanup uploaded file (configurable)
                        if self.auto_cleanup:
                            await self.upload_manager.cleanup_job(job.id)
                else:
                    # No pending jobs, sleep before polling again
                    await asyncio.sleep(1.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but keep worker running
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5.0)

    def stop(self):
        """Signal worker to stop"""
        self._running = False
```

## API Endpoint Design

### POST /transcribe (File Upload)

```python
@router.post("/transcribe", status_code=202)
async def create_transcription_job(
    file: UploadFile = File(...),
    model: str = Form("base"),
    device: str = Form("auto"),
    compute_type: str = Form("auto"),
    webhook_url: Optional[str] = Form(None),
    start_time: Optional[float] = Form(None),
    end_time: Optional[float] = Form(None),
    max_duration: Optional[int] = Form(None),
    service: TranscriptionService = Depends(get_service),
):
    """Submit audio file for transcription"""
    job = await service.create_job_from_upload(
        file=file,
        model=model,
        device=device,
        compute_type=compute_type,
        webhook_url=webhook_url,
        start_time=start_time,
        end_time=end_time,
        max_duration=max_duration,
    )
    return JobResponse(job_id=job.id, status=job.status)
```

### GET /jobs/{job_id}

```python
@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    repository: JobRepository = Depends(get_repository),
):
    """Get job status and results"""
    job = await repository.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    response = JobStatusResponse(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )

    if job.status == JobStatus.COMPLETED:
        response.result = job.result
    elif job.status == JobStatus.FAILED:
        response.error = job.error_message

    return response
```

### CLI Integration: `cesar serve`

```python
# cli.py (add to existing)
@cli.command(name="serve")
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8000, type=int, help="Port number")
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev only)")
def serve(host: str, port: int, reload: bool):
    """Start the transcription API server"""
    import uvicorn
    from cesar.api.app import create_app

    app = create_app()
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
    )
```

## Build Order

### Suggested Implementation Sequence

```
Phase 1: Foundation (no HTTP yet)
├── 1.1 Models and enums (cesar/api/models.py)
├── 1.2 SQLite repository (cesar/api/repository.py)
└── 1.3 Unit tests for repository

Phase 2: File Handling
├── 2.1 UploadManager (cesar/api/uploads.py)
└── 2.2 Unit tests for uploads

Phase 3: Background Worker
├── 3.1 BackgroundWorker (cesar/api/worker.py)
├── 3.2 Integration test: worker + repository
└── 3.3 Verify AudioTranscriber integration

Phase 4: HTTP Layer
├── 4.1 FastAPI app factory (cesar/api/app.py)
├── 4.2 TranscriptionService (cesar/api/service.py)
├── 4.3 HTTP routes (cesar/api/routes.py)
└── 4.4 Integration tests with TestClient

Phase 5: CLI Integration
├── 5.1 Add `cesar serve` command
├── 5.2 Configuration from environment
└── 5.3 End-to-end testing

Phase 6: Polish
├── 6.1 OpenAPI documentation customization
├── 6.2 Error handling refinement
└── 6.3 Webhook implementation
```

### Dependency Graph

```
models.py (no deps)
    │
    v
repository.py (depends on: models)
    │
    v
uploads.py (no internal deps)
    │
    v
worker.py (depends on: repository, uploads, cesar.transcriber)
    │
    v
service.py (depends on: repository, uploads, models)
    │
    v
routes.py (depends on: service, models)
    │
    v
app.py (depends on: routes, worker, lifespan setup)
    │
    v
cli.py serve command (depends on: app)
```

## Configuration

### Environment Variables

```python
# config.py
from pydantic_settings import BaseSettings
from pathlib import Path

class APIConfig(BaseSettings):
    # Database
    db_path: Path = Path.home() / ".cesar" / "jobs.db"

    # File storage
    upload_path: Path = Path.home() / ".cesar" / "uploads"
    max_upload_size_mb: int = 500
    auto_cleanup: bool = True
    retention_hours: int = 24

    # Worker
    worker_poll_interval: float = 1.0
    max_concurrent_jobs: int = 1

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    class Config:
        env_prefix = "CESAR_"
```

### Usage

```bash
# Default (localhost only)
cesar serve

# Custom port
cesar serve --port 9000

# All interfaces
cesar serve --host 0.0.0.0

# Via environment
CESAR_PORT=9000 CESAR_MAX_UPLOAD_SIZE_MB=1000 cesar serve
```

## Patterns to Follow

### Pattern 1: Atomic Job Claiming

**Why:** Prevents multiple workers from processing the same job.

```sql
-- Atomic: SELECT + UPDATE in one statement
UPDATE jobs
SET status = 'PROCESSING', started_at = ?
WHERE id = (
    SELECT id FROM jobs
    WHERE status = 'PENDING'
    ORDER BY created_at
    LIMIT 1
)
RETURNING *
```

### Pattern 2: Graceful Shutdown

**Why:** Don't interrupt in-progress transcriptions.

```python
async def shutdown(self):
    self._running = False
    # Wait for current job to finish (if any)
    # Don't forcefully kill transcription
```

### Pattern 3: Streaming File Upload

**Why:** Don't load entire file into memory.

```python
async with aiofiles.open(path, 'wb') as out:
    while chunk := await file.read(8192):
        await out.write(chunk)
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Blocking the Event Loop

**Wrong:**
```python
@router.post("/transcribe")
async def transcribe(file: UploadFile):
    result = transcriber.transcribe_file(...)  # BLOCKS!
    return result
```

**Right:**
```python
@router.post("/transcribe")
async def transcribe(file: UploadFile):
    job = await service.create_job(...)  # Returns immediately
    return {"job_id": job.id}  # Client polls for result
```

### Anti-Pattern 2: In-Memory Job State

**Wrong:**
```python
jobs = {}  # Lost on restart!
```

**Right:**
```python
# Use SQLite for persistence
await repository.create_job(job)
```

### Anti-Pattern 3: Synchronous Database Access in Async Routes

**Wrong:**
```python
import sqlite3
conn = sqlite3.connect(...)  # Blocks!
```

**Right:**
```python
import aiosqlite
async with aiosqlite.connect(...) as db:
    ...
```

## Scalability Considerations

| Load Level | Architecture | Notes |
|------------|--------------|-------|
| Single user | Default config | 1 worker, sequential jobs |
| Light team use | Increase workers | 2-4 workers if GPU has memory |
| Heavy use | Multiple processes | Run multiple `cesar serve` instances behind nginx |
| Enterprise | External queue | Graduate to Redis + Celery, reuse service layer |

The architecture is designed to grow:
- `TranscriptionService` can be reused with different queue backends
- `JobRepository` interface could swap SQLite for PostgreSQL
- Worker pattern scales to distributed processing

## Sources

- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - Official documentation for async context manager pattern
- [FastAPI Concurrency and async/await](https://fastapi.tiangolo.com/async/) - Official guidance on blocking code
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) - Built-in task handling
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) - Async SQLite library
- [litequeue](https://github.com/litements/litequeue) - SQLite-based queue pattern reference
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices) - Community patterns

**Confidence Assessment:**
- Component design: HIGH (follows established FastAPI patterns)
- SQLite schema: HIGH (standard patterns)
- Worker pattern: MEDIUM (custom implementation, needs testing)
- File handling: HIGH (standard patterns)
