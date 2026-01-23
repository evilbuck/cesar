# Stack Research: Async Transcription API

**Project:** Cesar v2.0 - HTTP API Layer
**Researched:** 2026-01-23
**Research Mode:** Stack dimension for async job queue API
**Overall Confidence:** HIGH

## Executive Summary

This document recommends a technology stack for adding an async HTTP API with job queue capabilities to the existing Cesar transcription CLI. The key constraint is **no external services** (no Redis, no Celery workers, no cloud dependencies) to maintain the offline-first, pipx-installable nature of the project.

The recommended approach uses FastAPI for the HTTP layer, aiosqlite for async SQLite persistence, and `ProcessPoolExecutor` for running CPU-intensive faster-whisper transcriptions without blocking the async event loop.

**Key architectural insight:** faster-whisper is CPU-bound (not I/O-bound). The GIL means threading won't help. We must use process-based parallelism via `ProcessPoolExecutor` to prevent transcription from blocking the HTTP server.

---

## Recommended Stack

### Core API Framework

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **FastAPI** | `>=0.128.0` | HTTP API framework | Industry standard for async Python APIs. Automatic OpenAPI docs, Pydantic validation, native async support. Comes bundled with uvicorn for serving. |
| **uvicorn** | `>=0.32.0` | ASGI server | Included with FastAPI[standard]. Single-process deployment suitable for local/offline use. |
| **pydantic** | `>=2.0.0` | Data validation | Already implicit via FastAPI. Strong typing for job schemas, request/response models. |

**Installation:**
```bash
pip install "fastapi[standard]>=0.128.0"
```

This single install provides: FastAPI, uvicorn, httpx (for webhooks), python-multipart (for file uploads), and Pydantic.

**Source:** [FastAPI PyPI](https://pypi.org/project/fastapi/) confirms v0.128.0 as current, requires Python 3.9+.

### Database & Persistence

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **aiosqlite** | `>=0.22.0` | Async SQLite access | Provides async/await interface to SQLite without blocking the event loop. Uses a single background thread per connection. |
| **sqlite3** | stdlib | Database engine | Zero-dependency, file-based, no server process. Perfect for offline-first constraint. |

**Why aiosqlite over synchronous sqlite3:**
- FastAPI endpoints are async; blocking sqlite3 calls would freeze the event loop
- aiosqlite wraps sqlite3 in a background thread, making it non-blocking
- Performance is equivalent for typical job queue operations (fetchone/fetchall are fast; only __aiter__/fetchone row-by-row is slower)
- Connection pooling via `aiosqlitepool` available if needed for high-traffic scenarios

**Source:** [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) - "uses a single, shared thread per connection"

**Schema Pattern:**
```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,           -- UUID
    status TEXT NOT NULL,          -- pending, processing, completed, failed
    audio_source_type TEXT,        -- upload, url
    audio_path TEXT,               -- local path to audio file
    model TEXT DEFAULT 'base',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    result_path TEXT,              -- path to transcription output
    error TEXT,
    webhook_url TEXT,              -- optional callback URL
    progress REAL DEFAULT 0        -- 0-100
);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created ON jobs(created_at);
```

---

## Background Processing

This is the critical section. faster-whisper transcription is **CPU-bound**, which requires special handling in an async context.

### The Problem

| Task Type | GIL Impact | Solution |
|-----------|------------|----------|
| I/O-bound (network, disk) | Releases GIL during wait | `asyncio` / `ThreadPoolExecutor` |
| CPU-bound (transcription) | Holds GIL continuously | `ProcessPoolExecutor` (separate process) |

Whisper transcription:
- Loads model weights into memory (~1-7GB depending on model size)
- Performs tensor operations entirely on CPU/GPU
- Does NOT release the GIL during computation
- A 5-minute audio file can take 30-120 seconds to transcribe

If we run transcription in the same process as FastAPI (even in a thread), it blocks the event loop for the entire duration.

### Recommended Solution: ProcessPoolExecutor

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **ProcessPoolExecutor** | stdlib | CPU-intensive work | Bypasses GIL for true parallel execution. Each worker is a separate Python process. |
| **asyncio.run_in_executor** | stdlib | Async bridge | Integrates ProcessPoolExecutor with FastAPI's event loop without blocking. |

**Source:** [Python Event Loop docs](https://docs.python.org/3/library/asyncio-eventloop.html) - "CPU-bound operations will block the event loop: in general it is preferable to run them in a process pool."

**Pattern - Application Setup:**
```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup():
    # Initialize with 1-2 workers (transcription is memory-intensive)
    # max_workers=2 allows 2 concurrent transcriptions
    app.state.executor = ProcessPoolExecutor(
        max_workers=2,
        initializer=init_transcription_worker
    )

@app.on_event("shutdown")
async def shutdown():
    app.state.executor.shutdown(wait=True)
```

**Pattern - Running Transcription:**
```python
async def run_transcription(job_id: str, audio_path: str, model: str) -> dict:
    """Run transcription in worker process, non-blocking to event loop."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        app.state.executor,
        transcribe_in_worker,  # Must be top-level function (picklable)
        job_id, audio_path, model
    )
    return result
```

**Pattern - Worker Module (cesar/api/worker.py):**
```python
"""Worker functions that run in ProcessPoolExecutor.

IMPORTANT: These functions run in a SEPARATE PROCESS.
- Cannot access FastAPI app state
- Cannot access async event loop
- Must use synchronous code only
- Must be picklable (top-level functions, not lambdas/closures)
"""
from pathlib import Path

# Global transcriber instance, initialized once per worker process
_transcriber = None
_current_model = None

def init_transcription_worker():
    """Called once when worker process starts.

    Pre-loading model here avoids 10-30 second load time on first job.
    """
    global _transcriber, _current_model
    from cesar.transcriber import AudioTranscriber
    _transcriber = AudioTranscriber(model_size="base")
    _transcriber._load_model()  # Eagerly load
    _current_model = "base"

def transcribe_in_worker(job_id: str, audio_path: str, model: str) -> dict:
    """Synchronous transcription function for worker process."""
    global _transcriber, _current_model

    # Reload model if different size requested
    if _transcriber is None or model != _current_model:
        from cesar.transcriber import AudioTranscriber
        _transcriber = AudioTranscriber(model_size=model)
        _transcriber._load_model()
        _current_model = model

    # Run transcription (this blocks, but that's OK in worker process)
    output_dir = Path("~/.local/share/cesar/results").expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job_id}.txt"

    result = _transcriber.transcribe_file(
        str(audio_path),
        str(output_path),
        progress_callback=None  # No callback in worker process
    )

    return {
        "job_id": job_id,
        "result_path": str(output_path),
        "language": result["language"],
        "duration": result["audio_duration"],
        "processing_time": result["processing_time"],
    }
```

**Source:** [FastAPI ML Model Serving](https://luis-sena.medium.com/how-to-optimize-fastapi-for-ml-model-serving-6f75fb9e040d) - "you need to load the model inside the worker to avoid IPC and other issues"

### Why NOT ThreadPoolExecutor

| Aspect | ThreadPoolExecutor | ProcessPoolExecutor |
|--------|-------------------|---------------------|
| GIL | Shared (blocks during CPU work) | Separate per process |
| Memory | Shared | Separate (model loaded per worker) |
| IPC overhead | None | Small (pickle args/results) |
| Startup time | Fast | Slow (process spawn) |
| Use case | I/O-bound tasks | CPU-bound tasks |

For transcription, ProcessPoolExecutor is required. The memory cost (each worker has its own model copy) is acceptable given typical usage (1-2 concurrent transcriptions).

### Why NOT Celery/Redis/RQ

| Solution | Why Avoid |
|----------|-----------|
| **Celery** | Requires Redis or RabbitMQ broker. External process to manage. Violates offline-first constraint. |
| **RQ** | Requires Redis. Same issue. |
| **Dramatiq** | Requires Redis or RabbitMQ. Same issue. |
| **Huey** | Supports SQLite backend but less mature. Adds dependency for marginal benefit over ProcessPoolExecutor. |

**When to reconsider Celery:** Multi-machine deployment, distributed workers, persistent queue across process restarts with guaranteed delivery, job retries with backoff.

**Source:** [FastAPI Background Tasks docs](https://fastapi.tiangolo.com/tutorial/background-tasks/) - "If you need to perform heavy background computation... you might benefit from using other bigger tools like Celery."

### Why NOT FastAPI BackgroundTasks

FastAPI's built-in `BackgroundTasks` runs in the same process:

```python
# DON'T DO THIS for CPU-intensive work
from fastapi import BackgroundTasks

@app.post("/jobs")
async def create_job(background_tasks: BackgroundTasks):
    background_tasks.add_task(transcribe, ...)  # BLOCKS ENTIRE APP
    return {"status": "accepted"}
```

**Problems:**
- Shares thread pool with HTTP handlers
- CPU-intensive work blocks event loop
- No persistence (jobs lost on restart)
- No progress tracking mechanism

**When to use:** Light tasks like sending emails, logging, cleanup operations.

---

## File Upload Handling

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **python-multipart** | `>=0.0.9` | Multipart form parsing | Required by FastAPI for file uploads. Included in fastapi[standard]. |
| **UploadFile** | FastAPI | Streaming uploads | Spooled file storage - memory up to limit, then disk. Handles large audio files efficiently. |

**Source:** [FastAPI Request Files](https://fastapi.tiangolo.com/tutorial/request-files/) - "UploadFile... stores in memory up to a limit, then spills to disk"

**Pattern:**
```python
from fastapi import FastAPI, UploadFile, File, Form
from pathlib import Path
import shutil
import uuid

UPLOAD_DIR = Path("~/.local/share/cesar/uploads").expanduser()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/jobs")
async def create_job(
    file: UploadFile = File(None),
    url: str = Form(None),
    model: str = Form("base"),
    webhook_url: str = Form(None),
):
    """Create transcription job from file upload or URL."""
    if file is None and url is None:
        raise HTTPException(400, "Either file or url must be provided")

    job_id = str(uuid.uuid4())

    if file:
        # Stream to disk without loading entire file into memory
        file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        audio_path = str(file_path)
        source_type = "upload"
    else:
        # Download URL to local file (in background or blocking)
        audio_path = await download_url(url, job_id)
        source_type = "url"

    # Create job record in SQLite
    await create_job_record(job_id, audio_path, source_type, model, webhook_url)

    return {"job_id": job_id, "status": "pending"}
```

**Memory considerations:**
- `UploadFile` spools to disk for files > 1MB (configurable)
- Use `shutil.copyfileobj()` to stream, not `await file.read()`
- Audio files can be 100MB+; never load entirely into memory

---

## Webhook Callbacks

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **httpx** | `>=0.28.0` | Async HTTP client | Included with fastapi[standard]. Native async support. Connection pooling. |

**Source:** [HTTPX PyPI](https://pypi.org/project/httpx/) confirms v0.28.1 as current.

**Pattern - Client Lifecycle:**
```python
import httpx
from fastapi import FastAPI

@app.on_event("startup")
async def startup():
    # Reuse client for connection pooling
    app.state.http_client = httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True
    )

@app.on_event("shutdown")
async def shutdown():
    await app.state.http_client.aclose()
```

**Pattern - Webhook Delivery:**
```python
async def send_webhook(webhook_url: str, job_id: str, status: str, result: dict = None):
    """Send webhook notification. Best-effort, don't fail job on webhook error."""
    payload = {
        "job_id": job_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if result:
        payload["result"] = result

    try:
        response = await app.state.http_client.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        logger.info(f"Webhook delivered to {webhook_url}")
    except httpx.HTTPError as e:
        # Log but don't fail - webhooks are best-effort
        logger.warning(f"Webhook delivery failed: {e}")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
```

**Webhook payload structure:**
```json
{
    "job_id": "uuid-here",
    "status": "completed",
    "timestamp": "2026-01-23T12:00:00Z",
    "result": {
        "language": "en",
        "duration": 300.5,
        "result_url": "/jobs/uuid-here/result"
    }
}
```

---

## Configuration Management

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **pydantic-settings** | `>=2.0.0` | Environment configuration | Type-safe config from env vars and files. Included in fastapi[standard]. |

**Pattern:**
```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Paths
    data_dir: Path = Path("~/.local/share/cesar").expanduser()
    db_path: Path = None  # Set in validator
    upload_dir: Path = None
    results_dir: Path = None

    # Processing
    max_workers: int = 2
    default_model: str = "base"

    # Limits
    max_upload_size_mb: int = 500

    class Config:
        env_prefix = "CESAR_"
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "jobs.db"
        self.upload_dir = self.data_dir / "uploads"
        self.upload_dir.mkdir(exist_ok=True)
        self.results_dir = self.data_dir / "results"
        self.results_dir.mkdir(exist_ok=True)

settings = Settings()
```

Environment variables:
```bash
CESAR_HOST=0.0.0.0
CESAR_PORT=8080
CESAR_MAX_WORKERS=4
CESAR_DEFAULT_MODEL=small
```

---

## Complete Dependencies

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    "click>=8.0.0",
    "rich>=13.0.0",
    "faster-whisper>=1.0.0",
]

[project.optional-dependencies]
api = [
    "fastapi[standard]>=0.128.0",
    "aiosqlite>=0.22.0",
]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.28.0",  # For testing
]
```

This approach allows:
- `pipx install cesar` - CLI only (current behavior, ~2GB install)
- `pipx install "cesar[api]"` - CLI + API server (~2.1GB install)

---

## Not Recommended

| Technology | Why Avoid |
|------------|-----------|
| **Celery + Redis** | External broker required. Violates offline-first constraint. |
| **RQ** | Requires Redis. Same issue. |
| **FastAPI BackgroundTasks** | CPU work blocks event loop. No persistence. |
| **ThreadPoolExecutor** | GIL prevents parallelism for CPU-bound work. |
| **Synchronous sqlite3** | Blocks event loop in async endpoints. |
| **Gunicorn with workers** | Overkill for single-machine. Adds complexity. uvicorn alone is sufficient. |
| **External job queue libs** | Dramatiq, Huey, etc. add dependencies for marginal benefit. |

---

## Integration with Existing Cesar Code

The existing `AudioTranscriber` class in `cesar/transcriber.py` is well-designed for reuse:

1. **Model reuse:** `_load_model()` supports lazy loading
2. **Progress callbacks:** `transcribe_file()` accepts `progress_callback` - useful for job status updates
3. **Result structure:** Returns dict with duration, language, segments, speed ratio
4. **Device detection:** `device_detection.py` handles CPU/GPU optimization automatically

**Required modifications:**
- Ensure all imports work in subprocess (watch for circular imports)
- Worker module must be importable standalone
- Consider adding `transcribe_sync()` method without callback for simpler worker usage

### Directory Structure

```
cesar/
  __init__.py
  __main__.py
  cli.py              # Click CLI (existing)
  transcriber.py      # Core logic (existing, reuse as-is)
  device_detection.py # Existing
  utils.py            # Existing
  api/
    __init__.py
    app.py            # FastAPI application factory
    config.py         # Settings via pydantic-settings
    models.py         # Pydantic request/response schemas
    routes.py         # API endpoints
    database.py       # aiosqlite operations
    worker.py         # ProcessPoolExecutor worker functions
    scheduler.py      # Background job processor
```

### New CLI Command

```python
# In cli.py
@cli.command(name="serve")
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8000, help="Port number")
@click.option("--workers", default=2, help="Max concurrent transcriptions")
def serve(host, port, workers):
    """Start the HTTP API server."""
    import uvicorn
    from cesar.api.app import create_app

    app = create_app(max_workers=workers)
    uvicorn.run(app, host=host, port=port)
```

Usage:
```bash
cesar serve --host 0.0.0.0 --port 8080 --workers 4
```

---

## API Endpoints (Preview)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/jobs` | Create transcription job (file upload or URL) |
| `GET` | `/jobs` | List jobs with filtering (status, limit, offset) |
| `GET` | `/jobs/{id}` | Get job status, progress, and metadata |
| `DELETE` | `/jobs/{id}` | Cancel pending job or delete completed job |
| `GET` | `/jobs/{id}/result` | Download transcription text file |
| `GET` | `/health` | Health check for monitoring |
| `GET` | `/models` | List available Whisper models |

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| FastAPI selection | HIGH | Official docs verified, v0.128.0 current |
| aiosqlite for persistence | HIGH | GitHub docs verified, v0.22.1 current |
| ProcessPoolExecutor for CPU work | HIGH | Python official docs, FastAPI community patterns |
| httpx for webhooks | HIGH | Bundled with FastAPI, v0.28.1 verified |
| No Celery/Redis | HIGH | Clear constraint from project requirements |
| Worker initialization pattern | MEDIUM | Multiple approaches exist; pattern from ML serving guides |
| File upload streaming | HIGH | FastAPI official docs verified |

---

## Sources

### Official Documentation
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [FastAPI Request Files](https://fastapi.tiangolo.com/tutorial/request-files/)
- [Python asyncio Event Loop - run_in_executor](https://docs.python.org/3/library/asyncio-eventloop.html)
- [Python concurrent.futures - ProcessPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html)

### Package Information
- [FastAPI PyPI](https://pypi.org/project/fastapi/) - v0.128.0 (Dec 2025)
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) - v0.22.1 (Dec 2025)
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/)
- [httpx PyPI](https://pypi.org/project/httpx/) - v0.28.1 (Dec 2024)

### Community Patterns & Best Practices
- [FastAPI Best Practices - GitHub](https://github.com/zhanymkanov/fastapi-best-practices)
- [How to Optimize FastAPI for ML Model Serving](https://luis-sena.medium.com/how-to-optimize-fastapi-for-ml-model-serving-6f75fb9e040d)
- [FastAPI Production Patterns 2025](https://orchestrator.dev/blog/2025-1-30-fastapi-production-patterns/)
- [Build a Distributed Queue with SQLite](https://dev.to/hexshift/build-a-shared-nothing-distributed-queue-with-sqlite-and-python-3p1)
- [Managing Background Tasks in FastAPI](https://leapcell.io/blog/managing-background-tasks-and-long-running-operations-in-fastapi)
- [Background Tasks in FastAPI - Better Stack](https://betterstack.com/community/guides/scaling-python/background-tasks-in-fastapi/)

---

*Research completed: 2026-01-23*
*Next step: Roadmap creation using this stack*
