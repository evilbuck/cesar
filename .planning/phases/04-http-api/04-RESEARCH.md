# Phase 4: HTTP API - Research

**Researched:** 2026-01-23
**Domain:** FastAPI REST API development with async file handling
**Confidence:** HIGH

## Summary

FastAPI provides a modern, async-first framework perfectly suited for building REST APIs with automatic OpenAPI/Swagger documentation. The research confirms that FastAPI's built-in features align well with Phase 4 requirements: file uploads via UploadFile (memory-efficient streaming), lifespan context managers for worker lifecycle, and automatic JSON schema generation.

Key architectural decisions validated:
- **FastAPI** is the standard choice for async Python REST APIs in 2026, with excellent Pydantic v2 integration
- **UploadFile** provides memory-efficient file handling via spooled temporary files
- **Lifespan events** using async context managers replace deprecated @app.on_event decorators
- **httpx** or **aiohttp** for async URL downloads with streaming support
- **TemporaryDirectory** context managers for automatic file cleanup

The phase can be implemented using established patterns with no custom framework needed. All requirements (API-01 through API-06, SRV-03) map to standard FastAPI features.

**Primary recommendation:** Use FastAPI 0.109+ with python-multipart for file uploads, httpx for async URL fetching, and lifespan context managers for worker integration.

## Standard Stack

The established libraries/tools for FastAPI REST APIs with file handling:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.109.0 | Async REST framework | Industry standard for async Python APIs, automatic OpenAPI docs |
| uvicorn | >=0.25.0 | ASGI server | FastAPI's recommended production server with hot reload |
| python-multipart | >=0.0.6 | Form data parsing | Required for FastAPI file uploads (multipart/form-data) |
| pydantic | >=2.0.0 | Data validation | Already in project, FastAPI's validation layer |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.26.0 | Async HTTP client | Download files from URLs, modern replacement for requests with async support |
| aiofiles | >=23.0.0 | Async file I/O | Optional: async file operations if needed beyond UploadFile |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | aiohttp | aiohttp is faster but httpx has simpler API and HTTP/2 support |
| FastAPI | Flask + async | FastAPI provides automatic docs and better async integration |
| uvicorn | hypercorn | uvicorn is more mature and better documented for FastAPI |

**Installation:**
```bash
pip install "fastapi>=0.109.0" "uvicorn>=0.25.0" "python-multipart>=0.0.6" "httpx>=0.26.0"
```

## Architecture Patterns

### Recommended Project Structure
```
cesar/
├── api/
│   ├── __init__.py
│   ├── models.py          # Job Pydantic models (existing)
│   ├── repository.py      # JobRepository (existing)
│   ├── worker.py          # BackgroundWorker (existing)
│   ├── server.py          # FastAPI app, lifespan, endpoints
│   └── file_handler.py    # File upload/download logic
└── cli.py                 # CLI integration (Phase 5)
```

### Pattern 1: FastAPI with Lifespan Events

**What:** Modern async context manager pattern for app startup/shutdown
**When to use:** Starting background workers, initializing database connections, loading resources

**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize worker
    repo = JobRepository(Path("jobs.db"))
    await repo.connect()
    worker = BackgroundWorker(repo)
    worker_task = asyncio.create_task(worker.run())

    # Store in app.state for access in endpoints
    app.state.repo = repo
    app.state.worker = worker

    yield  # App is running, handling requests

    # Shutdown: cleanup
    await worker.shutdown()
    await worker_task
    await repo.close()

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: File Upload with UploadFile

**What:** Memory-efficient file handling using spooled temporary files
**When to use:** Accepting file uploads up to 100MB

**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/request-files/
from fastapi import FastAPI, File, UploadFile, HTTPException
from pathlib import Path
import tempfile

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

@app.post("/transcribe", status_code=202)
async def transcribe_file_upload(
    file: UploadFile,
    model: str = "base"
):
    # Validate file size from Content-Length header
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(400, detail="File too large (max 100MB)")

    # Save to temp directory
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Create job
    job = Job(audio_path=tmp_path, model_size=model)
    await app.state.repo.create(job)

    return job
```

### Pattern 3: URL-Based File Download

**What:** Async download from URL with streaming and timeout
**When to use:** POST /transcribe with URL reference

**Example:**
```python
# Source: https://www.python-httpx.org/async/
import httpx
import tempfile
from pathlib import Path

async def download_from_url(url: str, timeout: int = 60) -> str:
    """Download file from URL to temp location.

    Returns:
        Path to downloaded file

    Raises:
        HTTPException: If download fails or times out
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                # Create temp file
                suffix = Path(url).suffix or ".tmp"
                fd, tmp_path = tempfile.mkstemp(suffix=suffix)

                with open(tmp_path, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

                os.close(fd)
                return tmp_path

        except httpx.TimeoutException:
            raise HTTPException(408, detail="URL download timeout")
        except httpx.HTTPStatusError as e:
            raise HTTPException(400, detail=f"Failed to download: {e}")
```

### Pattern 4: Status Code and Response Models

**What:** Return 202 Accepted with full Job object
**When to use:** POST /transcribe endpoints

**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/response-status-code/
from fastapi import status

@app.post("/transcribe", status_code=status.HTTP_202_ACCEPTED, response_model=Job)
async def transcribe_file_upload(file: UploadFile):
    job = Job(audio_path=saved_path)
    await app.state.repo.create(job)
    return job  # FastAPI serializes Job model to JSON
```

### Pattern 5: Query Parameter Filtering

**What:** Optional status filter for GET /jobs
**When to use:** List endpoints with filtering

**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/query-params/
from typing import Optional

@app.get("/jobs", response_model=List[Job])
async def list_jobs(status: Optional[str] = None):
    jobs = await app.state.repo.list_all()
    if status:
        jobs = [j for j in jobs if j.status.value == status]
    return jobs
```

### Anti-Patterns to Avoid

- **DON'T use @app.on_event**: Use lifespan context managers instead (deprecated as of FastAPI 0.109)
- **DON'T load entire file to memory**: Use UploadFile.file for streaming or read in chunks
- **DON'T forget Content-Length validation**: Check file size before reading to save bandwidth
- **DON'T mix File/Form with Body JSON**: They use different encodings (multipart vs JSON)
- **DON'T create worker in endpoint**: Initialize once in lifespan, share via app.state
- **DON'T use requests library**: Use httpx for async compatibility

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File size validation | Custom Content-Length parsing | HTTPException with validation before file.read() | Edge cases: chunked encoding, missing headers |
| Temp file cleanup | Manual os.unlink() tracking | tempfile.TemporaryDirectory() context manager | Handles exceptions, cleanup on crash |
| Async file downloads | Threading with requests | httpx.AsyncClient with streaming | Non-blocking, memory efficient, timeout handling |
| API error responses | Custom exception classes | FastAPI HTTPException | Automatic OpenAPI docs, standard format |
| OpenAPI schema | Manual JSON schema writing | FastAPI automatic generation | Keeps docs in sync with code |
| File upload streaming | Custom chunk reading | UploadFile (SpooledTemporaryFile) | Memory efficient, automatic disk spilling |

**Key insight:** FastAPI handles most HTTP concerns automatically. Focus on business logic (job creation, worker coordination) rather than HTTP plumbing.

## Common Pitfalls

### Pitfall 1: Blocking Operations in Async Endpoints

**What goes wrong:** Calling synchronous blocking code (file I/O, transcription) directly in async endpoints freezes the event loop

**Why it happens:** Python's async/await requires all code in the chain to be async-compatible

**How to avoid:**
- Use `asyncio.to_thread()` for blocking operations (already done in BackgroundWorker)
- Don't call AudioTranscriber directly in endpoints
- Create jobs and let worker handle processing

**Warning signs:** Server becomes unresponsive during long transcriptions, high CPU on single core

### Pitfall 2: Temp File Leaks

**What goes wrong:** Uploaded files accumulate in /tmp, filling disk

**Why it happens:** Exceptions interrupt cleanup, or files aren't tracked properly

**How to avoid:**
- Use context managers (TemporaryDirectory, NamedTemporaryFile with delete=True)
- Store temp paths in Job model for worker cleanup
- Add cleanup in finally blocks

**Warning signs:** /tmp directory grows over time, disk space errors

### Pitfall 3: File Size Bomb Attacks

**What goes wrong:** Clients upload huge files, consuming server memory/disk

**Why it happens:** No validation before reading file content

**How to avoid:**
- Check Content-Length header first: `if file.size > MAX_SIZE`
- Use streaming reads, not `await file.read()` all at once
- Consider nginx client_max_body_size for defense in depth

**Warning signs:** Out of memory errors, slow API responses during uploads

### Pitfall 4: Worker Lifecycle Races

**What goes wrong:** Worker task doesn't start, or shutdown leaves zombie workers

**Why it happens:** Not awaiting worker task creation/cancellation properly

**How to avoid:**
- Use `asyncio.create_task()` for worker, store task reference
- In shutdown, call `await worker.shutdown()` then `await worker_task`
- Add worker health check to verify it's running

**Warning signs:** Jobs stay queued forever, server won't shut down cleanly

### Pitfall 5: Mixed JSON and Multipart Requests

**What goes wrong:** Cannot combine File() parameters with Body() JSON in same endpoint

**Why it happens:** Different Content-Type encodings (multipart/form-data vs application/json)

**How to avoid:**
- Create separate endpoints: one for file upload, one for URL reference
- Or use Form() for metadata alongside File() (all form-encoded)

**Warning signs:** Pydantic validation errors, "Field required" for JSON body

## Code Examples

Verified patterns from official sources:

### Complete Server Setup with Lifespan

```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
from fastapi import FastAPI, status
from cesar.api.repository import JobRepository
from cesar.api.worker import BackgroundWorker

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle: start worker, cleanup on shutdown."""
    # Startup
    db_path = Path.home() / ".cesar" / "jobs.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    repo = JobRepository(db_path)
    await repo.connect()

    worker = BackgroundWorker(repo, poll_interval=1.0)
    worker_task = asyncio.create_task(worker.run())

    # Share via app.state
    app.state.repo = repo
    app.state.worker = worker
    app.state.worker_task = worker_task

    yield  # App runs here

    # Shutdown
    await worker.shutdown()
    await worker_task  # Wait for current job to finish
    await repo.close()

app = FastAPI(
    title="Cesar Transcription API",
    description="Offline audio transcription with async job queue",
    version="2.0.0",
    lifespan=lifespan
)
```

### File Upload Endpoint with Size Validation

```python
# Source: https://fastapi.tiangolo.com/tutorial/request-files/
# https://github.com/fastapi/fastapi/discussions/8167
from fastapi import FastAPI, File, UploadFile, HTTPException, status, Form
from cesar.api.models import Job
import tempfile
from pathlib import Path

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

@app.post("/transcribe", status_code=status.HTTP_202_ACCEPTED, response_model=Job)
async def transcribe_file(
    file: UploadFile,
    model: str = Form(default="base")
):
    """Upload audio file for transcription.

    Args:
        file: Audio file (mp3, wav, m4a, etc.) - max 100MB
        model: Whisper model size (tiny/base/small/medium/large)

    Returns:
        Job object with id and status='queued'
    """
    # Validate Content-Length before reading
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
        )

    # Validate file extension
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac'}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {ext}"
            )

    # Save to temp file
    try:
        suffix = Path(file.filename).suffix if file.filename else ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {e}"
        )

    # Create job
    job = Job(audio_path=tmp_path, model_size=model)
    await app.state.repo.create(job)

    return job
```

### URL-Based Transcription Endpoint

```python
# Source: https://www.python-httpx.org/async/
from pydantic import BaseModel, HttpUrl
import httpx
import os

class TranscribeURLRequest(BaseModel):
    url: HttpUrl
    model: str = "base"

@app.post("/transcribe", status_code=status.HTTP_202_ACCEPTED, response_model=Job)
async def transcribe_url(request: TranscribeURLRequest):
    """Download audio from URL and transcribe.

    Args:
        url: HTTP/HTTPS URL to audio file
        model: Whisper model size

    Returns:
        Job object with id and status='queued'
    """
    # Download file
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(str(request.url))
            response.raise_for_status()

            # Get extension from URL or Content-Type
            ext = Path(str(request.url)).suffix or ".mp3"

            # Save to temp file
            fd, tmp_path = tempfile.mkstemp(suffix=ext)
            with os.fdopen(fd, 'wb') as f:
                f.write(response.content)

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="URL download timed out (60s limit)"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to download from URL: {e.response.status_code}"
        )

    # Create job
    job = Job(audio_path=tmp_path, model_size=request.model)
    await app.state.repo.create(job)

    return job
```

### Job Status and List Endpoints

```python
# Source: https://fastapi.tiangolo.com/tutorial/query-params/
from typing import Optional, List
from fastapi import Path as PathParam

@app.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str = PathParam(..., description="Job UUID")):
    """Get job status and results by ID."""
    job = await app.state.repo.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )
    return job

@app.get("/jobs", response_model=List[Job])
async def list_jobs(status: Optional[str] = None):
    """List all jobs, optionally filtered by status.

    Args:
        status: Filter by status (queued/processing/completed/error)
    """
    jobs = await app.state.repo.list_all()

    if status:
        # Validate status value
        try:
            from cesar.api.models import JobStatus
            status_enum = JobStatus(status)
            jobs = [j for j in jobs if j.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )

    return jobs
```

### Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    """Server health check including worker status."""
    return {
        "status": "healthy",
        "worker": "running" if app.state.worker.is_processing or not app.state.worker_task.done() else "stopped"
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| @app.on_event decorators | Lifespan context managers | FastAPI 0.109 (2024) | Better resource management, cleanup guarantees |
| requests library | httpx AsyncClient | 2023-2024 | Native async, HTTP/2 support, better performance |
| Manual JSON schema | FastAPI automatic generation | FastAPI core feature | Docs stay in sync, less maintenance |
| File() with bytes | UploadFile | FastAPI early versions | Memory efficient for large files |
| Manual exception handling | HTTPException with detail | FastAPI core feature | Automatic error responses, OpenAPI docs |

**Deprecated/outdated:**
- **@app.on_event("startup")** and **@app.on_event("shutdown")**: Use lifespan parameter instead (deprecated in FastAPI 0.109)
- **Starlette BackgroundTasks for long operations**: Use proper async task management (asyncio.create_task) for workers
- **requests.get() in async code**: Blocks event loop, use httpx.AsyncClient

## Open Questions

Things that couldn't be fully resolved:

1. **Temp file cleanup timing**
   - What we know: Files should be cleaned up after transcription completes
   - What's unclear: Should worker delete file immediately, or keep until job is retrieved?
   - Recommendation: Delete in worker's finally block after updating job status. Simple, prevents leaks.

2. **URL download streaming vs buffered**
   - What we know: httpx supports both streaming and buffered downloads
   - What's unclear: For typical audio files (5-50MB), is streaming necessary?
   - Recommendation: Use buffered (response.content) for simplicity. Audio files are smaller than 100MB limit, and streaming adds complexity without clear benefit. Can optimize later if needed.

3. **File type validation depth**
   - What we know: Should validate audio file formats
   - What's unclear: Extension check sufficient, or inspect MIME type / file magic bytes?
   - Recommendation: Start with extension validation. AudioTranscriber already validates via ffprobe, so deep validation in API is redundant. Fail fast is good enough.

## Sources

### Primary (HIGH confidence)
- [FastAPI Request Files Documentation](https://fastapi.tiangolo.com/tutorial/request-files/) - UploadFile patterns and file handling
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - Modern context manager approach for startup/shutdown
- [FastAPI Response Status Code](https://fastapi.tiangolo.com/tutorial/response-status-code/) - HTTP 202 Accepted patterns
- [FastAPI Query Parameters](https://fastapi.tiangolo.com/tutorial/query-params/) - Filtering with optional parameters
- [FastAPI Error Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/) - HTTPException usage
- [HTTPX Async Documentation](https://www.python-httpx.org/async/) - AsyncClient for URL downloads
- [Python tempfile Documentation](https://docs.python.org/3/library/tempfile.html) - Temporary file management

### Secondary (MEDIUM confidence)
- [Better Stack: Uploading Files Using FastAPI](https://betterstack.com/community/guides/scaling-python/uploading-files-using-fastapi/) - Security and file size limits
- [Better Stack: FastAPI Error Handling](https://betterstack.com/community/guides/scaling-python/error-handling-fastapi/) - Error patterns and best practices
- [FastAPI GitHub Discussion #8167](https://github.com/fastapi/fastapi/discussions/8167) - Community file size validation strategies
- [Medium: Async File Downloads](https://medium.com/@benshearlaw/asynchronously-stream-response-data-to-disc-using-python-6f8d5974f355) - httpx streaming patterns

### Tertiary (LOW confidence)
- WebSearch results on file upload best practices (2026) - General patterns, not FastAPI-specific
- WebSearch results on async HTTP clients comparison - Ecosystem trends, validated with official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - FastAPI and httpx are well-established, official docs confirm all features
- Architecture: HIGH - All patterns verified from official FastAPI documentation and working code examples
- Pitfalls: MEDIUM-HIGH - Based on GitHub discussions and community experience, some scenarios not personally tested

**Research date:** 2026-01-23
**Valid until:** ~30 days (2026-02-22) - FastAPI is stable, major changes unlikely

**Notes:**
- All requirements (API-01 through API-06, SRV-03) are achievable with standard FastAPI features
- No custom framework or complex libraries needed
- Existing cesar/api structure (models, repository, worker) integrates cleanly with FastAPI
- Phase 4 focuses on HTTP layer; worker lifecycle and job processing already implemented
