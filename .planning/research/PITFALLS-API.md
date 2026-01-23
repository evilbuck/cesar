# Pitfalls Research: Async Transcription API

**Domain:** Adding async HTTP API to synchronous CLI tool (faster-whisper + FastAPI)
**Researched:** 2026-01-23
**Confidence:** HIGH (verified via official documentation and multiple sources)

## Executive Summary

Adding an async API layer to Cesar presents several architectural challenges unique to the combination of:
1. **FastAPI (async)** serving HTTP requests
2. **faster-whisper (synchronous, CPU-bound)** performing transcription
3. **SQLite (single-writer)** for job persistence
4. **Single process** constraint (no external workers)
5. **Offline-first** operation (unreliable webhook delivery)

This document catalogs pitfalls that will cause failures if not addressed, with prevention strategies for each.

---

## Critical Pitfalls

These issues will definitely break the API if not handled correctly.

### CP-1: Event Loop Blocking (Synchronous Transcription in Async Context)

**What goes wrong:**
faster-whisper's `model.transcribe()` is synchronous and CPU-bound. Calling it directly from an async FastAPI endpoint blocks the entire event loop. During a 10-minute transcription, the server cannot:
- Accept new requests
- Respond to health checks
- Update job status
- Process any other coroutines

**Why it happens:**
FastAPI runs on asyncio. When you `await` something, control returns to the event loop to handle other work. But synchronous code has no `await` points - it holds the GIL and blocks everything.

**Consequences:**
- API becomes unresponsive during transcription
- Health checks fail, orchestrators restart the service
- Job status endpoints return timeouts
- Multiple requests queue up, causing cascading failures

**Warning signs:**
- Health endpoint times out during transcription
- Concurrent requests all wait for first to complete
- Uvicorn logs show "worker timeout" errors

**Prevention:**
```python
# WRONG - blocks event loop
@app.post("/jobs")
async def create_job(file: UploadFile):
    result = transcriber.transcribe_file(...)  # BLOCKS EVERYTHING
    return result

# RIGHT - offload to thread pool
from starlette.concurrency import run_in_threadpool

@app.post("/jobs")
async def create_job(file: UploadFile):
    # Returns immediately, transcription runs in background
    job_id = create_job_record(...)
    asyncio.create_task(process_job(job_id))
    return {"job_id": job_id}

async def process_job(job_id: str):
    # Run CPU-bound work in thread pool
    result = await run_in_threadpool(
        transcriber.transcribe_file,
        input_path,
        output_path
    )
    update_job_status(job_id, result)
```

**Phase impact:** Must be addressed in Phase 1 (Core API Foundation)

**Sources:**
- [FastAPI Concurrency and async/await](https://fastapi.tiangolo.com/async/)
- [Starlette run_in_threadpool vs run_in_executor](https://sentry.io/answers/fastapi-difference-between-run-in-executor-and-run-in-threadpool/)

---

### CP-2: SQLite Write Contention (Database Locked Errors)

**What goes wrong:**
SQLite allows only one writer at a time. Without proper configuration:
- Job status updates block each other
- `sqlite3.OperationalError: database is locked` exceptions
- Data corruption under concurrent access

**Why it happens:**
Default SQLite configuration uses rollback journal (not WAL) and has a 5-second lock timeout. Multiple async tasks updating job status will contend for write locks.

**Consequences:**
- Random "database is locked" errors
- Lost job status updates
- Inconsistent state between actual job and recorded status

**Warning signs:**
- Intermittent `OperationalError: database is locked`
- Job status doesn't match actual state
- Errors only under concurrent load

**Prevention:**
```python
# Required SQLite configuration for async access
PRAGMAS = """
PRAGMA journal_mode=WAL;       -- Write-Ahead Logging for concurrent reads
PRAGMA synchronous=NORMAL;     -- Balance durability and performance
PRAGMA busy_timeout=30000;     -- 30 second timeout (not 5)
PRAGMA foreign_keys=ON;        -- Referential integrity
"""

# Use aiosqlite for async access
import aiosqlite

async def get_connection():
    conn = await aiosqlite.connect(
        "cesar.db",
        isolation_level=None  # Autocommit for simple operations
    )
    await conn.executescript(PRAGMAS)
    return conn

# For writes, use BEGIN IMMEDIATE to avoid lock promotion issues
async def update_job_status(job_id: str, status: str):
    async with get_connection() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            await db.execute(
                "UPDATE jobs SET status = ? WHERE id = ?",
                (status, job_id)
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
```

**Phase impact:** Must be addressed in Phase 2 (Job Queue and Persistence)

**Sources:**
- [SQLite Write-Ahead Logging](https://sqlite.org/wal.html)
- [aiosqlite documentation](https://aiosqlite.omnilib.dev/en/stable/)
- [SkyPilot Blog: Abusing SQLite for Concurrency](https://blog.skypilot.co/abusing-sqlite-to-handle-concurrency/)

---

### CP-3: Zombie Jobs (Crash Without Cleanup)

**What goes wrong:**
If the process crashes or is killed during transcription:
- Job remains in "running" status forever
- No transcription output exists
- User sees job stuck at "processing"

**Why it happens:**
The job status is updated to "running" before transcription starts. If the process dies mid-transcription, there's no cleanup code that runs. On restart, the job still shows "running" but nothing is processing it.

**Consequences:**
- Jobs stuck in "running" state indefinitely
- Users confused about job status
- No way to distinguish "running" from "crashed"
- Accumulation of zombie jobs over time

**Warning signs:**
- Jobs in "running" status for longer than maximum expected duration
- Jobs that never complete after server restart
- Mismatch between running jobs and actual processing activity

**Prevention:**
```python
# 1. Add heartbeat timestamp to jobs table
# Schema: jobs(id, status, created_at, updated_at, heartbeat_at, ...)

# 2. Update heartbeat during transcription
async def process_job(job_id: str):
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(job_id, interval=30)
    )
    try:
        result = await run_in_threadpool(transcribe, ...)
        await update_job_status(job_id, "completed", result)
    except Exception as e:
        await update_job_status(job_id, "failed", error=str(e))
    finally:
        heartbeat_task.cancel()

async def heartbeat_loop(job_id: str, interval: int):
    while True:
        await update_heartbeat(job_id)
        await asyncio.sleep(interval)

# 3. On startup, detect and recover zombie jobs
async def recover_zombies():
    threshold = datetime.now() - timedelta(minutes=5)
    zombies = await db.execute("""
        SELECT id FROM jobs
        WHERE status = 'running'
        AND heartbeat_at < ?
    """, (threshold,))

    for job in zombies:
        await update_job_status(job.id, "failed", error="Server restart")
        # Optionally: requeue for retry
```

**Phase impact:** Must be addressed in Phase 2 (Job Queue and Persistence)

**Sources:**
- [Apache Airflow: Zombie Task Detection](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html)
- [effectum: SQLite Job Queue with Crash Recovery](https://github.com/dimfeld/effectum)

---

## Async/Sync Mixing Pitfalls

### AS-1: GIL Limitations for CPU-Bound Work

**What goes wrong:**
Python's GIL means threads don't truly parallelize CPU-bound work. Using `run_in_threadpool` helps responsiveness but doesn't speed up transcription. Multiple concurrent transcriptions don't actually run in parallel.

**Why it happens:**
The GIL allows only one thread to execute Python bytecode at a time. Thread pools help with I/O-bound work (waiting for network, disk) but not CPU-bound work.

**Consequences:**
- Multiple concurrent transcriptions don't speed up total time
- High CPU usage from context switching
- Memory pressure from multiple models loaded

**Warning signs:**
- CPU at 100% but only one core active
- Multiple jobs don't complete faster than sequential
- Significant overhead from thread switching

**Prevention:**
For single-process constraint, accept sequential processing:
```python
# Use a semaphore to ensure only one transcription at a time
transcription_semaphore = asyncio.Semaphore(1)

async def process_job(job_id: str):
    async with transcription_semaphore:
        # Only one transcription runs at a time
        result = await run_in_threadpool(transcribe, ...)
```

If parallelism is needed later, consider ProcessPoolExecutor (but this adds complexity and memory overhead).

**Phase impact:** Design decision in Phase 1, documented limitation

---

### AS-2: Thread Pool Exhaustion

**What goes wrong:**
FastAPI's default thread pool has 40 threads. If many sync operations run simultaneously, the pool becomes exhausted and requests queue up.

**Why it happens:**
Every sync function in an async endpoint uses a thread. Long-running sync operations (like transcription) hold threads for extended periods.

**Consequences:**
- Requests start timing out
- New requests can't be processed
- Cascading failures under load

**Warning signs:**
- Requests queuing during high load
- Thread count at maximum
- Response times increasing linearly with queue depth

**Prevention:**
```python
# Option 1: Limit concurrent transcriptions with semaphore (recommended)
transcription_semaphore = asyncio.Semaphore(1)

# Option 2: Use dedicated executor with limited threads
from concurrent.futures import ThreadPoolExecutor

# Dedicated executor for transcription (separate from FastAPI's pool)
transcription_executor = ThreadPoolExecutor(max_workers=1)

async def transcribe_async(input_path, output_path):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        transcription_executor,
        transcriber.transcribe_file,
        input_path,
        output_path
    )
```

**Phase impact:** Architecture decision in Phase 1

---

## File Handling Pitfalls

### FH-1: Memory Exhaustion from Large Uploads

**What goes wrong:**
Using `await file.read()` loads entire file into memory. A 500MB audio file spikes memory by 500MB per concurrent upload.

**Why it happens:**
FastAPI's `UploadFile.read()` returns bytes. Without streaming, the entire file must fit in memory.

**Consequences:**
- OOM kills under concurrent large uploads
- Server crashes during peak usage
- Unpredictable memory usage

**Warning signs:**
- Memory spikes during uploads
- OOM killer terminating process
- Slow uploads due to memory pressure

**Prevention:**
```python
import aiofiles
import tempfile
from pathlib import Path

async def save_upload_streaming(upload: UploadFile, dest_dir: Path) -> Path:
    """Stream upload to disk without loading into memory"""
    # Create unique filename
    suffix = Path(upload.filename).suffix
    dest_path = dest_dir / f"{uuid4()}{suffix}"

    # Stream in chunks (default: 1MB)
    async with aiofiles.open(dest_path, 'wb') as f:
        while chunk := await upload.read(1024 * 1024):  # 1MB chunks
            await f.write(chunk)

    return dest_path
```

**Phase impact:** Must be addressed in Phase 1 (file upload endpoint)

**Sources:**
- [FastAPI File Uploads Best Practices](https://betterstack.com/community/guides/scaling-python/uploading-files-using-fastapi/)
- [Async File Uploads in FastAPI](https://medium.com/@connect.hashblock/async-file-uploads-in-fastapi-handling-gigabyte-scale-data-smoothly-aec421335680)

---

### FH-2: Temp File Cleanup Failures

**What goes wrong:**
Uploaded files stored in temp directory never get cleaned up:
- After successful transcription (file no longer needed)
- After failed transcription (partial file remains)
- After job cancellation
- On server restart (orphaned files)

**Why it happens:**
No cleanup logic tied to job lifecycle. Exceptions bypass cleanup code. Server restart loses track of temp files.

**Consequences:**
- Disk fills up over time
- Eventually server fails due to no disk space
- Sensitive audio data persists longer than necessary

**Warning signs:**
- Temp directory growing over time
- Disk usage increasing without obvious cause
- Old files in upload directory

**Prevention:**
```python
# 1. Track temp files in database
# Schema: job_files(job_id, file_path, created_at, cleaned_at)

# 2. Clean up on job completion/failure
async def cleanup_job_files(job_id: str):
    files = await get_job_files(job_id)
    for file_path in files:
        try:
            Path(file_path).unlink(missing_ok=True)
            await mark_file_cleaned(job_id, file_path)
        except Exception as e:
            logger.error(f"Failed to clean {file_path}: {e}")

# 3. Periodic cleanup task for orphaned files
async def cleanup_orphaned_files():
    """Run on startup and periodically"""
    threshold = datetime.now() - timedelta(hours=24)

    # Find files not associated with active jobs
    orphans = await db.execute("""
        SELECT file_path FROM job_files
        WHERE job_id NOT IN (SELECT id FROM jobs WHERE status = 'running')
        AND cleaned_at IS NULL
        AND created_at < ?
    """, (threshold,))

    for orphan in orphans:
        # ... clean up
```

**Phase impact:** Phase 2 (Job Queue) and Phase 3 (Operations)

---

### FH-3: File Handle Leaks

**What goes wrong:**
UploadFile objects hold file handles. If not explicitly closed, handles leak.

**Why it happens:**
Exceptions bypass cleanup. Missing `finally` blocks. Async context managers not used properly.

**Consequences:**
- "Too many open files" errors
- Server becomes unable to accept new uploads
- Requires restart to recover

**Prevention:**
```python
@app.post("/jobs")
async def create_job(file: UploadFile):
    try:
        dest_path = await save_upload_streaming(file, UPLOAD_DIR)
        # ... process
    finally:
        # ALWAYS close the upload file handle
        await file.close()
```

**Phase impact:** Phase 1 (Core API)

---

## Job Queue Pitfalls

### JQ-1: Lost Jobs on Startup Crash

**What goes wrong:**
If server crashes between accepting upload and persisting job to database, the job is lost forever.

**Why it happens:**
File is saved to disk, but database transaction fails or never completes.

**Consequences:**
- User uploaded file successfully but has no job ID
- File orphaned on disk
- No way to recover or retry

**Prevention:**
```python
# Atomic job creation: file + db in single transaction
async def create_job(file: UploadFile) -> str:
    job_id = str(uuid4())
    dest_path = UPLOAD_DIR / f"{job_id}{suffix}"

    try:
        # 1. Save file first
        await save_upload_streaming(file, dest_path)

        # 2. Create database record
        await db.execute("""
            INSERT INTO jobs (id, status, input_path, created_at)
            VALUES (?, 'pending', ?, ?)
        """, (job_id, str(dest_path), datetime.now()))
        await db.commit()

        # 3. Queue for processing
        asyncio.create_task(process_job(job_id))

        return job_id

    except Exception:
        # Clean up file if db insert failed
        dest_path.unlink(missing_ok=True)
        raise
```

**Phase impact:** Phase 2 (Job Queue)

---

### JQ-2: Duplicate Processing After Restart

**What goes wrong:**
After restart, pending/running jobs are reprocessed, but some may have already completed or partially completed.

**Why it happens:**
Status wasn't updated to "completed" before crash. Or job was completed but status update failed.

**Consequences:**
- Same audio transcribed multiple times
- Wasted compute resources
- Potential inconsistent results (different runs may produce slightly different output)

**Prevention:**
```python
# 1. Check for existing output before reprocessing
async def process_job(job_id: str):
    job = await get_job(job_id)
    output_path = Path(job.output_path)

    if output_path.exists() and output_path.stat().st_size > 0:
        # Output exists, just update status
        await update_job_status(job_id, "completed")
        return

    # ... proceed with transcription

# 2. Use idempotent operations
# Transcription is naturally idempotent - same input produces same output
```

**Phase impact:** Phase 2 (Job Queue)

---

## Webhook Delivery Pitfalls

### WH-1: Blocking Event Loop During Webhook Delivery

**What goes wrong:**
Synchronous HTTP calls to webhook URLs block the event loop.

**Why it happens:**
Using `requests` library instead of `httpx` or `aiohttp` for webhook calls.

**Consequences:**
- Event loop blocked during webhook delivery
- Slow webhook endpoints slow down entire API
- Timeouts cascade to other operations

**Prevention:**
```python
import httpx

async def deliver_webhook(job_id: str, callback_url: str, payload: dict):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(callback_url, json=payload)
            response.raise_for_status()
            await record_webhook_success(job_id, callback_url)
        except httpx.RequestError as e:
            await record_webhook_failure(job_id, callback_url, str(e))
            # Queue for retry
```

**Phase impact:** Phase 3 (Webhooks)

---

### WH-2: Webhook Retry Storms

**What goes wrong:**
Fixed retry intervals cause thundering herd when webhook endpoint recovers.

**Why it happens:**
All failed webhooks retry at same time after fixed interval.

**Consequences:**
- Webhook endpoint overwhelmed when it recovers
- Immediate re-failure
- Wasted resources on pointless retries

**Prevention:**
```python
import random

def calculate_retry_delay(attempt: int) -> float:
    """Exponential backoff with jitter"""
    base_delay = min(300, 2 ** attempt)  # Max 5 minutes
    jitter = random.uniform(0.5, 1.5)
    return base_delay * jitter

# Retry schedule: ~2s, ~4s, ~8s, ~16s, ~32s... up to 5 min
```

**Phase impact:** Phase 3 (Webhooks)

---

### WH-3: Webhook Delivery to Offline Endpoints

**What goes wrong:**
In offline-first context, webhook callbacks will frequently fail because the recipient may be offline or unreachable.

**Why it happens:**
Cesar is designed for offline use. If user provides webhook URL, that endpoint may not be reachable.

**Consequences:**
- Webhook delivery always fails
- Retry queue grows unbounded
- Resources wasted on retries

**Prevention:**
```python
# 1. Limit retry attempts
MAX_WEBHOOK_ATTEMPTS = 5

# 2. Implement dead letter queue
async def handle_webhook_permanent_failure(job_id: str, callback_url: str):
    await db.execute("""
        INSERT INTO webhook_failures (job_id, callback_url, failed_at, attempts)
        VALUES (?, ?, ?, ?)
    """, (job_id, callback_url, datetime.now(), MAX_WEBHOOK_ATTEMPTS))

    # Job result is still available via polling
    logger.warning(f"Webhook delivery failed permanently for job {job_id}")

# 3. Document that polling is the reliable fallback
# Webhooks are "best effort" in offline-first design
```

**Phase impact:** Phase 3 (Webhooks) - document as known limitation

---

## Model Loading Pitfalls

### ML-1: Slow Cold Start

**What goes wrong:**
First request waits for model to load. Model loading takes 5-30+ seconds depending on size.

**Why it happens:**
Model loaded lazily on first transcription request.

**Consequences:**
- First request has very long latency
- Health checks may fail during startup
- User perceives API as slow/broken

**Warning signs:**
- First request takes 10x+ longer than subsequent
- Health endpoint reports ready before model loaded
- Timeouts on first request after restart

**Prevention:**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: preload model
    logger.info("Loading transcription model...")
    transcriber.load_model()  # Explicit load
    logger.info("Model loaded, API ready")

    yield

    # Shutdown: cleanup
    transcriber.unload_model()

app = FastAPI(lifespan=lifespan)

# Health endpoint distinguishes startup states
@app.get("/health")
async def health():
    if not transcriber.model_loaded:
        return JSONResponse(
            {"status": "starting", "model_loaded": False},
            status_code=503
        )
    return {"status": "healthy", "model_loaded": True}
```

**Phase impact:** Phase 1 (Core API)

**Sources:**
- [FastAPI Lifespan Events](https://www.sarimahmed.net/blog/fastapi-lifespan/)
- [Loading Models into FastAPI Apps](https://apxml.com/courses/fastapi-ml-deployment/chapter-3-integrating-ml-models/loading-models-fastapi)

---

### ML-2: Memory Pressure from Large Models

**What goes wrong:**
Larger Whisper models (medium, large) consume significant RAM. Combined with uploaded files and transcription buffers, may exceed available memory.

**Why it happens:**
- `large` model: ~3GB+ RAM (CPU), more on GPU
- Audio files loaded for processing
- Multiple job files in temp storage

**Consequences:**
- OOM killer terminates process
- System becomes unresponsive
- Swap thrashing slows everything

**Warning signs:**
- Memory usage approaching system limits
- Swap usage increasing
- OOM kills in system logs

**Prevention:**
```python
# 1. Document memory requirements per model
MODEL_MEMORY = {
    "tiny": "~1GB",
    "base": "~1.5GB",
    "small": "~2GB",
    "medium": "~5GB",
    "large": "~10GB"
}

# 2. Check available memory on startup
import psutil

def check_memory_for_model(model_size: str):
    available = psutil.virtual_memory().available
    required = MODEL_MEMORY_BYTES[model_size]

    if available < required * 1.5:  # 50% headroom
        logger.warning(
            f"Low memory for {model_size} model. "
            f"Available: {available/1e9:.1f}GB, "
            f"Recommended: {required*1.5/1e9:.1f}GB"
        )

# 3. Limit concurrent jobs based on memory
```

**Phase impact:** Phase 1 (Core API) - configuration validation

---

## Error Handling Pitfalls

### EH-1: Partial State on Failure

**What goes wrong:**
Multi-step operations leave partial state when intermediate step fails:
1. File uploaded (success)
2. Job created in DB (success)
3. Background task started (fails)

Result: Job exists but will never process.

**Why it happens:**
No transaction spanning async operations. No compensation logic.

**Consequences:**
- Jobs stuck in "pending" forever
- Inconsistent state between subsystems
- User confusion

**Prevention:**
```python
# Use try/except with explicit compensation
async def create_job(file: UploadFile) -> str:
    file_path = None
    job_id = None

    try:
        # Step 1: Save file
        file_path = await save_upload(file)

        # Step 2: Create job record
        job_id = await create_job_record(file_path)

        # Step 3: Start processing
        asyncio.create_task(process_job(job_id))

        return job_id

    except Exception as e:
        # Compensate in reverse order
        if job_id:
            await delete_job_record(job_id)
        if file_path:
            Path(file_path).unlink(missing_ok=True)
        raise
```

**Phase impact:** Phase 1 and 2 (throughout)

---

### EH-2: Swallowed Exceptions in Background Tasks

**What goes wrong:**
Exceptions in `asyncio.create_task()` are silently swallowed unless explicitly handled.

**Why it happens:**
Background tasks run independently. If they raise exceptions and no one awaits them, the exception is logged but not handled.

**Consequences:**
- Jobs fail silently
- No error recorded in database
- User sees job stuck in "running"

**Warning signs:**
- "Task exception was never retrieved" in logs
- Jobs stuck in running status
- No error messages in job records

**Prevention:**
```python
async def process_job_wrapper(job_id: str):
    """Wrapper that ensures exceptions are recorded"""
    try:
        await process_job(job_id)
    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        await update_job_status(
            job_id,
            "failed",
            error=str(e)
        )

# Use wrapper when creating tasks
asyncio.create_task(process_job_wrapper(job_id))
```

**Phase impact:** Phase 2 (Job Queue)

---

## Prevention Summary by Phase

| Phase | Pitfalls to Address | Key Prevention Patterns |
|-------|---------------------|------------------------|
| Phase 1: Core API | CP-1, FH-1, FH-3, ML-1, ML-2, AS-1, AS-2 | `run_in_threadpool`, streaming uploads, lifespan preloading, semaphore |
| Phase 2: Job Queue | CP-2, CP-3, FH-2, JQ-1, JQ-2, EH-1, EH-2 | WAL mode, heartbeats, atomic operations, explicit error handling |
| Phase 3: Operations | WH-1, WH-2, WH-3 | async HTTP client, exponential backoff, DLQ, polling fallback |

## Testing Recommendations

1. **Event loop blocking test:** Start transcription, verify health endpoint responds
2. **Concurrent upload test:** Upload multiple large files simultaneously
3. **Crash recovery test:** Kill process mid-transcription, verify zombie detection on restart
4. **SQLite contention test:** Concurrent status updates under load
5. **Memory test:** Monitor memory during model load and large file processing
6. **Webhook failure test:** Configure unreachable webhook, verify retry behavior and eventual DLQ

## Sources

**FastAPI/Async:**
- [FastAPI Concurrency and async/await](https://fastapi.tiangolo.com/async/)
- [Starlette run_in_threadpool](https://sentry.io/answers/fastapi-difference-between-run-in-executor-and-run-in-threadpool/)
- [FastAPI Lifespan Events](https://www.sarimahmed.net/blog/fastapi-lifespan/)

**SQLite:**
- [SQLite Write-Ahead Logging](https://sqlite.org/wal.html)
- [aiosqlite Documentation](https://aiosqlite.omnilib.dev/en/stable/)
- [SkyPilot: SQLite Concurrency](https://blog.skypilot.co/abusing-sqlite-to-handle-concurrency/)

**Job Queues:**
- [Apache Airflow: Zombie Tasks](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html)
- [effectum: SQLite Job Queue](https://github.com/dimfeld/effectum)
- [persist-queue: Python SQLite Queue](https://pypi.org/project/persist-queue/)

**File Handling:**
- [FastAPI File Uploads](https://betterstack.com/community/guides/scaling-python/uploading-files-using-fastapi/)

**Webhooks:**
- [Webhook Retry Logic Best Practices](https://sparkco.ai/blog/mastering-webhook-retry-logic-strategies-and-best-practices)

**Model Loading:**
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
- [Loading ML Models in FastAPI](https://apxml.com/courses/fastapi-ml-deployment/chapter-3-integrating-ml-models/loading-models-fastapi)
