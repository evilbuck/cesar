# Phase 3: Background Worker - Research

**Researched:** 2026-01-23
**Domain:** Async background worker for sequential job processing
**Confidence:** HIGH

## Summary

Phase 3 implements a background worker that processes transcription jobs sequentially. The key challenge is integrating synchronous code (faster-whisper transcription) with an async application (FastAPI). The worker must:

1. Run continuously in the background while the API handles requests
2. Process jobs one at a time in FIFO order
3. Execute blocking transcription without freezing the event loop
4. Support graceful shutdown when the server stops

The standard approach uses Python's native asyncio primitives: `asyncio.create_task()` for the background worker loop, `asyncio.to_thread()` for offloading blocking transcription to a thread pool, and `asyncio.Event` for shutdown signaling. Integration with FastAPI happens via the lifespan context manager.

**Primary recommendation:** Build a simple worker class with an async `run()` loop that polls `get_next_queued()`, executes transcription via `to_thread()`, and responds to a shutdown event. Start the worker in FastAPI's lifespan handler.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **asyncio** | stdlib | Background task orchestration | Native Python async, no dependencies, well-documented |
| **concurrent.futures** | stdlib | Thread pool for blocking code | Used by `asyncio.to_thread()` internally |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **contextlib** | stdlib | `@asynccontextmanager` decorator | For lifespan handler if not using FastAPI's |
| **logging** | stdlib | Worker diagnostics | Debug job processing flow |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native asyncio | Celery | Celery adds Redis/RabbitMQ dependency - overkill for sequential processing |
| Native asyncio | ARQ | ARQ is async-native but adds Redis dependency |
| Native asyncio | aiojobs | Good for many concurrent jobs; we want sequential, simpler approach works |
| `to_thread()` | `ProcessPoolExecutor` | Processes help with CPU-bound work but transcription is I/O-bound (file read + inference); threading sufficient |
| Simple loop | asyncio.Queue | Queue useful for producer-consumer with memory buffer; we use SQLite as durable queue |

**Installation:**
```bash
# No additional packages needed - all stdlib
# Phase 2 already has aiosqlite for database access
```

## Architecture Patterns

### Recommended Project Structure
```
cesar/
  api/
    __init__.py
    models.py           # Existing Job model
    database.py         # Existing schema
    repository.py       # Existing JobRepository
    worker.py           # NEW: BackgroundWorker class
```

### Pattern 1: Async Worker Loop with Shutdown Event

**What:** A worker class with an async `run()` method that loops until signaled to stop
**When to use:** Always - this is the standard pattern for background processing in asyncio
**Example:**
```python
# Source: https://docs.python.org/3/library/asyncio-task.html
# Source: https://fastapi.tiangolo.com/advanced/events/
import asyncio
import logging
from datetime import datetime
from typing import Optional

from cesar.api.models import Job, JobStatus
from cesar.api.repository import JobRepository
from cesar.transcriber import AudioTranscriber

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Background worker that processes transcription jobs sequentially."""

    def __init__(self, repository: JobRepository, poll_interval: float = 1.0):
        """Initialize worker with repository and polling interval.

        Args:
            repository: JobRepository instance for database access
            poll_interval: Seconds between polling for new jobs
        """
        self.repository = repository
        self.poll_interval = poll_interval
        self._shutdown_event = asyncio.Event()
        self._current_job: Optional[Job] = None

    async def run(self) -> None:
        """Main worker loop. Runs until shutdown is signaled."""
        logger.info("Background worker started")

        while not self._shutdown_event.is_set():
            try:
                # Check for next job
                job = await self.repository.get_next_queued()

                if job is None:
                    # No jobs, wait before polling again
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self.poll_interval
                        )
                    except asyncio.TimeoutError:
                        pass  # Timeout expected, continue loop
                    continue

                # Process the job
                await self._process_job(job)

            except Exception as e:
                logger.exception(f"Worker loop error: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info("Background worker stopped")

    async def shutdown(self) -> None:
        """Signal the worker to stop gracefully."""
        logger.info("Shutdown signal received")
        self._shutdown_event.set()

    async def _process_job(self, job: Job) -> None:
        """Process a single transcription job."""
        self._current_job = job
        logger.info(f"Processing job {job.id}")

        try:
            # Mark as processing
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()
            await self.repository.update(job)

            # Run blocking transcription in thread pool
            result = await asyncio.to_thread(
                self._transcribe_sync,
                job.audio_path,
                job.model_size
            )

            # Mark as completed
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result_text = result["text"]
            job.detected_language = result["language"]
            await self.repository.update(job)

            logger.info(f"Job {job.id} completed")

        except Exception as e:
            # Mark as error
            job.status = JobStatus.ERROR
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            await self.repository.update(job)
            logger.error(f"Job {job.id} failed: {e}")

        finally:
            self._current_job = None

    def _transcribe_sync(self, audio_path: str, model_size: str) -> dict:
        """Synchronous transcription wrapper. Runs in thread pool."""
        # Create temp file for output (or use in-memory)
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            output_path = f.name

        try:
            transcriber = AudioTranscriber(model_size=model_size)
            result = transcriber.transcribe_file(audio_path, output_path)

            # Read the transcription result
            with open(output_path, 'r', encoding='utf-8') as f:
                text = f.read()

            return {
                "text": text,
                "language": result.get("language", "unknown")
            }
        finally:
            import os
            os.unlink(output_path)
```

### Pattern 2: FastAPI Lifespan Integration

**What:** Start worker as background task in lifespan, cancel on shutdown
**When to use:** When integrating with FastAPI (Phase 4+)
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio

from cesar.api.database import get_default_db_path
from cesar.api.repository import JobRepository
from cesar.api.worker import BackgroundWorker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: start worker on startup, stop on shutdown."""
    # Startup
    db_path = get_default_db_path()
    repository = JobRepository(db_path)
    await repository.connect()

    worker = BackgroundWorker(repository)
    worker_task = asyncio.create_task(worker.run())

    # Store in app state for access if needed
    app.state.repository = repository
    app.state.worker = worker
    app.state.worker_task = worker_task

    yield

    # Shutdown
    await worker.shutdown()

    # Wait for worker to finish current job (with timeout)
    try:
        await asyncio.wait_for(worker_task, timeout=30.0)
    except asyncio.TimeoutError:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    await repository.close()


app = FastAPI(lifespan=lifespan)
```

### Pattern 3: Graceful Shutdown with asyncio.Event

**What:** Use `asyncio.Event` to signal worker to stop, allowing current job to complete
**When to use:** Always - ensures jobs aren't left in inconsistent state
**Example:**
```python
# Source: https://docs.python.org/3/library/asyncio-sync.html
import asyncio

class Worker:
    def __init__(self):
        self._shutdown_event = asyncio.Event()

    async def run(self):
        while not self._shutdown_event.is_set():
            # Poll for work
            job = await self.get_job()
            if job:
                await self.process(job)
            else:
                # Wait for shutdown or timeout
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    pass  # Continue polling

    async def shutdown(self):
        self._shutdown_event.set()
```

### Anti-Patterns to Avoid

- **Using `time.sleep()` in async code:** Blocks the event loop. Always use `await asyncio.sleep()`.
- **Running transcription directly in async function:** Blocks event loop for minutes. Use `asyncio.to_thread()`.
- **Using `task.cancel()` without waiting:** Can leave database in inconsistent state. Always wait for graceful shutdown first.
- **Polling too frequently:** Wastes CPU. 1-second poll interval is reasonable; shutdown event allows immediate response.
- **Creating new transcriber per job:** Model loading is slow. Could cache transcriber instance (but watch memory).
- **Ignoring exceptions in worker loop:** Silent failures. Always log and continue.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Running blocking code async | Custom threading wrapper | `asyncio.to_thread()` | Handles thread pool, context propagation |
| Background task creation | Manual thread management | `asyncio.create_task()` | Proper exception handling, cancellation support |
| Graceful shutdown signaling | Boolean flags with polling | `asyncio.Event` | Thread-safe, supports `wait_for` with timeout |
| Lifecycle management | Custom start/stop methods | FastAPI lifespan | Guaranteed cleanup, ASGI-compliant |
| Job persistence queue | In-memory queue | SQLite (existing) | Survives restarts, already implemented |

**Key insight:** Python 3.9+ `asyncio.to_thread()` is the blessed way to run blocking code. It's simpler than `loop.run_in_executor()` and handles context variables correctly.

## Common Pitfalls

### Pitfall 1: Blocking the Event Loop

**What goes wrong:** Calling synchronous `transcriber.transcribe_file()` directly in an async function freezes the entire application.
**Why it happens:** Async functions run in the event loop. Blocking calls prevent other coroutines from executing.
**How to avoid:**
  - Always use `asyncio.to_thread()` for blocking operations
  - Enable asyncio debug mode during development: `asyncio.run(main(), debug=True)`
**Warning signs:** API becomes unresponsive during transcription; other requests timeout.

### Pitfall 2: Not Handling Worker Shutdown Gracefully

**What goes wrong:** Server shutdown while job is processing leaves job stuck in PROCESSING state forever.
**Why it happens:** `task.cancel()` immediately stops the worker without cleanup.
**How to avoid:**
  - Use `asyncio.Event` to signal shutdown
  - Wait for current job to complete (with reasonable timeout)
  - Only `cancel()` as last resort after timeout
**Warning signs:** Jobs in PROCESSING state after server restart.

### Pitfall 3: Race Condition on Job Pickup

**What goes wrong:** In multi-worker scenarios (not our case), multiple workers could pick up the same job.
**Why it happens:** `get_next_queued()` and status update aren't atomic.
**How to avoid:**
  - For single worker (our case): Not an issue
  - For multiple workers: Use `UPDATE ... RETURNING` with status check in single query
  - Or use database-level locking (SQLite doesn't support `SELECT FOR UPDATE`)
**Warning signs:** Same job processed multiple times (only relevant if we add parallelism later).

### Pitfall 4: Memory Leak from Transcriber Instance

**What goes wrong:** Creating new `AudioTranscriber` per job loads the model repeatedly, causing memory bloat.
**Why it happens:** Whisper models are large (base ~140MB, large ~3GB). Model stays in memory.
**How to avoid:**
  - Option 1: Create transcriber once in worker `__init__`, reuse for all jobs
  - Option 2: Create per job but ensure cleanup (current approach is fine for sequential processing)
  - Option 3: Lazy load on first use, keep cached
**Warning signs:** Memory usage grows over time; OOM errors.

### Pitfall 5: Lost Task Reference (Fire-and-Forget Danger)

**What goes wrong:** Background task silently disappears, exceptions go unnoticed.
**Why it happens:** `asyncio.create_task()` returns Task object. If not stored, can be garbage collected.
**How to avoid:**
  - Always store task reference: `worker_task = asyncio.create_task(worker.run())`
  - Add done callback for error logging
  - Await task during shutdown
**Warning signs:** Worker stops unexpectedly with no error logs.

## Code Examples

Verified patterns from official sources:

### Complete Worker Class

```python
# Source: https://docs.python.org/3/library/asyncio-task.html
# Source: https://fastapi.tiangolo.com/advanced/events/
"""
Background worker for sequential job processing.

Runs in the event loop, executes blocking transcription in thread pool,
supports graceful shutdown.
"""
import asyncio
import logging
import tempfile
import os
from datetime import datetime
from typing import Optional

from cesar.api.models import Job, JobStatus
from cesar.api.repository import JobRepository
from cesar.transcriber import AudioTranscriber

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Background worker that processes transcription jobs sequentially.

    Example:
        repository = JobRepository(db_path)
        await repository.connect()

        worker = BackgroundWorker(repository)
        task = asyncio.create_task(worker.run())

        # ... later ...
        await worker.shutdown()
        await task
    """

    def __init__(
        self,
        repository: JobRepository,
        poll_interval: float = 1.0,
        model_size: str = "base"
    ):
        """Initialize worker.

        Args:
            repository: JobRepository for database access
            poll_interval: Seconds between polling when idle
            model_size: Default Whisper model size if job doesn't specify
        """
        self.repository = repository
        self.poll_interval = poll_interval
        self.default_model_size = model_size
        self._shutdown_event = asyncio.Event()
        self._current_job_id: Optional[str] = None

    @property
    def is_processing(self) -> bool:
        """Check if worker is currently processing a job."""
        return self._current_job_id is not None

    @property
    def current_job_id(self) -> Optional[str]:
        """Get ID of job currently being processed, or None."""
        return self._current_job_id

    async def run(self) -> None:
        """Main worker loop. Runs until shutdown() is called."""
        logger.info("Background worker started")

        while not self._shutdown_event.is_set():
            try:
                job = await self.repository.get_next_queued()

                if job is None:
                    # No jobs available, wait before polling again
                    # Use wait_for to respond quickly to shutdown
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self.poll_interval
                        )
                    except asyncio.TimeoutError:
                        pass
                    continue

                await self._process_job(job)

            except asyncio.CancelledError:
                logger.info("Worker cancelled")
                raise
            except Exception as e:
                logger.exception(f"Worker error: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info("Background worker stopped")

    async def shutdown(self) -> None:
        """Signal the worker to stop after current job completes."""
        logger.info("Worker shutdown requested")
        self._shutdown_event.set()

    async def _process_job(self, job: Job) -> None:
        """Process a single transcription job.

        Updates job status to PROCESSING, runs transcription,
        then updates to COMPLETED or ERROR.
        """
        self._current_job_id = job.id
        logger.info(f"Starting job {job.id}: {job.audio_path}")

        try:
            # Transition to PROCESSING
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()
            await self.repository.update(job)

            # Run blocking transcription in thread pool
            model_size = job.model_size or self.default_model_size
            result = await asyncio.to_thread(
                self._run_transcription,
                job.audio_path,
                model_size
            )

            # Transition to COMPLETED
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result_text = result["text"]
            job.detected_language = result["language"]
            await self.repository.update(job)

            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            # Transition to ERROR
            job.status = JobStatus.ERROR
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)

            try:
                await self.repository.update(job)
            except Exception as update_error:
                logger.error(f"Failed to update job {job.id} error state: {update_error}")

            logger.error(f"Job {job.id} failed: {e}")

        finally:
            self._current_job_id = None

    def _run_transcription(self, audio_path: str, model_size: str) -> dict:
        """Run transcription synchronously. Called in thread pool.

        Args:
            audio_path: Path to audio file
            model_size: Whisper model size

        Returns:
            Dict with 'text' and 'language' keys
        """
        # Create temporary output file
        fd, output_path = tempfile.mkstemp(suffix='.txt')
        os.close(fd)

        try:
            transcriber = AudioTranscriber(model_size=model_size)
            result = transcriber.transcribe_file(audio_path, output_path)

            # Read transcription text
            with open(output_path, 'r', encoding='utf-8') as f:
                text = f.read().strip()

            return {
                "text": text,
                "language": result.get("language", "unknown")
            }

        finally:
            # Clean up temp file
            try:
                os.unlink(output_path)
            except OSError:
                pass
```

### Testing Async Worker

```python
# Source: https://docs.python.org/3/library/unittest.html#unittest.IsolatedAsyncioTestCase
import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from cesar.api.models import Job, JobStatus
from cesar.api.worker import BackgroundWorker


class TestBackgroundWorker(unittest.IsolatedAsyncioTestCase):
    """Unit tests for BackgroundWorker."""

    async def test_worker_processes_queued_job(self):
        """Test worker picks up and processes a queued job."""
        # Mock repository
        mock_repo = MagicMock()
        job = Job(audio_path="/test/audio.mp3", model_size="tiny")

        # Return job once, then None
        mock_repo.get_next_queued = AsyncMock(side_effect=[job, None])
        mock_repo.update = AsyncMock(return_value=job)

        worker = BackgroundWorker(mock_repo, poll_interval=0.1)

        # Mock transcription
        with patch.object(worker, '_run_transcription') as mock_transcribe:
            mock_transcribe.return_value = {"text": "Hello", "language": "en"}

            # Run worker briefly
            task = asyncio.create_task(worker.run())
            await asyncio.sleep(0.2)
            await worker.shutdown()
            await task

        # Verify job was updated to PROCESSING then COMPLETED
        assert mock_repo.update.call_count >= 2

    async def test_worker_graceful_shutdown(self):
        """Test worker stops gracefully on shutdown signal."""
        mock_repo = MagicMock()
        mock_repo.get_next_queued = AsyncMock(return_value=None)

        worker = BackgroundWorker(mock_repo, poll_interval=0.1)
        task = asyncio.create_task(worker.run())

        # Signal shutdown
        await asyncio.sleep(0.05)
        await worker.shutdown()

        # Worker should stop within poll interval
        await asyncio.wait_for(task, timeout=1.0)

    async def test_worker_handles_transcription_error(self):
        """Test worker marks job as ERROR when transcription fails."""
        mock_repo = MagicMock()
        job = Job(audio_path="/nonexistent/audio.mp3")

        mock_repo.get_next_queued = AsyncMock(side_effect=[job, None])
        mock_repo.update = AsyncMock(return_value=job)

        worker = BackgroundWorker(mock_repo, poll_interval=0.1)

        # Mock transcription to fail
        with patch.object(worker, '_run_transcription') as mock_transcribe:
            mock_transcribe.side_effect = FileNotFoundError("Audio file not found")

            task = asyncio.create_task(worker.run())
            await asyncio.sleep(0.2)
            await worker.shutdown()
            await task

        # Check job was marked as ERROR
        update_calls = mock_repo.update.call_args_list
        final_job = update_calls[-1][0][0]
        assert final_job.status == JobStatus.ERROR
        assert "not found" in final_job.error_message.lower()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `loop.run_in_executor(None, fn)` | `asyncio.to_thread(fn)` | Python 3.9 (2020) | Simpler API, proper context propagation |
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.95 (2023) | Colocates startup/shutdown, safer resource management |
| Manual thread creation | `asyncio.create_task()` | Python 3.7 (2018) | Proper exception handling, cancellation |
| Boolean stop flags | `asyncio.Event` | Always available | Thread-safe, supports `wait_for` |

**Deprecated/outdated:**
- **`@app.on_event("startup")`**: Still works but `lifespan` parameter is preferred
- **`loop.run_in_executor()`**: Still works but `to_thread()` is simpler for functions
- **`asyncio.ensure_future()`**: Replaced by `create_task()` for coroutines

## Open Questions

Things that couldn't be fully resolved:

1. **Transcriber instance caching**
   - What we know: Creating new `AudioTranscriber` loads model (~seconds for small, longer for large)
   - What's unclear: Memory impact of keeping model loaded vs. reload overhead
   - Recommendation: Start simple (create per job). Profile later if slow. For Phase 3, simplicity wins.

2. **Recovery of stuck PROCESSING jobs**
   - What we know: If server crashes during transcription, job stays in PROCESSING
   - What's unclear: Best strategy for detecting/recovering orphaned jobs
   - Recommendation: For v2.0, manual intervention is acceptable. Could add startup check that resets PROCESSING jobs to QUEUED.

3. **Worker pool for parallel processing**
   - What we know: Requirements specify sequential (one at a time) processing
   - What's unclear: Future need for parallelism
   - Recommendation: Keep design extensible but don't over-engineer. Current approach allows future parallelism by spawning multiple workers.

## Sources

### Primary (HIGH confidence)
- [Python asyncio-task documentation](https://docs.python.org/3/library/asyncio-task.html) - `create_task()`, `to_thread()`, cancellation
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - Lifespan context manager pattern
- [Python asyncio Event Loop](https://docs.python.org/3/library/asyncio-eventloop.html) - `run_in_executor()`, event loop APIs

### Secondary (MEDIUM confidence)
- [Graceful Shutdowns with asyncio](https://roguelynn.com/words/asyncio-graceful-shutdowns/) - Signal handling patterns
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) - Understanding built-in limitations
- [Running a background worker in Python with asyncio](https://medium.com/@burak.sezer/running-a-background-worker-in-python-with-asyncio-75231a1a9c45) - Worker loop patterns

### Tertiary (LOW confidence)
- [aiojobs documentation](https://aiojobs.readthedocs.io/) - Advanced job scheduling (not needed for our use case)
- [FastAPI + Celery](https://testdriven.io/blog/fastapi-and-celery/) - Alternative architecture (rejected - too complex)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Native asyncio is well-documented, no external dependencies
- Architecture: HIGH - Pattern verified against official Python and FastAPI docs
- Pitfalls: HIGH - Common issues well-known, solutions verified

**Research date:** 2026-01-23
**Valid until:** 90 days (stable Python/asyncio APIs, infrequent breaking changes)
