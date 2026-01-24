# Phase 5: CLI Integration - Research

**Researched:** 2026-01-23
**Domain:** Click CLI integration with Uvicorn/FastAPI server
**Confidence:** HIGH

## Summary

This research investigated how to implement a Click command (`cesar serve`) that starts a FastAPI application using Uvicorn programmatically. The standard approach is to use `uvicorn.run()` with configuration parameters passed from Click options. Uvicorn provides built-in graceful shutdown handling for SIGINT (Ctrl+C) signals, with configurable timeout periods. The key architectural decision for this phase is whether to support multiple workers, which has significant implications for the background transcription worker.

**Primary recommendation:** Use `uvicorn.run()` with single worker (default) for simplicity and background worker compatibility. Multi-worker support should be deferred or carefully implemented with process-safe job coordination.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| uvicorn | >=0.25.0 | ASGI server | Industry standard for FastAPI, built-in signal handling and graceful shutdown |
| click | >=8.0.0 | CLI framework | Already used in project, simple integration with `uvicorn.run()` |
| fastapi | >=0.109.0 | Web framework | Already in use (Phase 4), lifespan events handle worker lifecycle |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| gunicorn | latest | Process manager | Only if production multi-worker needed (adds complexity) |
| uvicorn-worker | latest | Gunicorn worker class | Only with gunicorn for production deployments |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| uvicorn.run() | uvicorn.Server() | More control but requires manual event loop management |
| Single process | Multiple workers | Better throughput but requires process-safe job coordination |
| Built-in reload | External file watcher | More complex but potentially more reliable |

**Installation:**
Already installed via project dependencies in pyproject.toml.

## Architecture Patterns

### Recommended Project Structure
```
cesar/
├── cli.py              # Click command group (existing)
│   ├── transcribe()    # Existing transcription command
│   └── serve()         # NEW: Server command
├── api/
│   └── server.py       # FastAPI app (existing from Phase 4)
```

### Pattern 1: Click Command with uvicorn.run()
**What:** Click command that calls `uvicorn.run()` with parameters from CLI flags
**When to use:** Standard approach for all FastAPI CLIs
**Example:**
```python
# Source: FastAPI Manual Deployment Docs
# https://fastapi.tiangolo.com/deployment/manually/

import uvicorn
import click

@click.command()
@click.option('--port', '-p', default=5000, help='Port to bind to')
@click.option('--host', '-h', default='127.0.0.1', help='Host to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
@click.option('--workers', default=1, help='Number of workers')
def serve(port, host, reload, workers):
    """Start the HTTP API server."""
    uvicorn.run(
        "cesar.api.server:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level="info"
    )
```

### Pattern 2: Lifespan Context Manager for Worker Lifecycle
**What:** Use FastAPI's `@asynccontextmanager` lifespan to start/stop background worker
**When to use:** Always - this is the modern FastAPI approach (replaces deprecated `@app.on_event`)
**Example:**
```python
# Source: FastAPI Lifespan Events
# https://fastapi.tiangolo.com/advanced/events/

from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize worker
    worker = BackgroundWorker(repo)
    worker_task = asyncio.create_task(worker.run())
    app.state.worker = worker
    app.state.worker_task = worker_task

    yield  # App is running

    # Shutdown: cleanup
    await worker.shutdown()
    await worker_task

app = FastAPI(lifespan=lifespan)
```

### Pattern 3: Signal Handling via Uvicorn (Built-in)
**What:** Uvicorn automatically handles SIGINT/SIGTERM and triggers lifespan shutdown
**When to use:** Always - no custom signal handlers needed
**How it works:**
- User presses Ctrl+C → Uvicorn receives SIGINT
- Uvicorn stops accepting new connections
- Uvicorn waits for in-flight requests (up to `timeout_graceful_shutdown`)
- Uvicorn calls lifespan shutdown (after `yield`)
- Lifespan shutdown stops worker and waits for completion

### Anti-Patterns to Avoid
- **Custom signal handlers:** Don't add signal.signal() handlers - Uvicorn manages this
- **Blocking shutdown:** Don't use time.sleep() in shutdown - use async await
- **Ignoring workers parameter:** Using `workers > 1` breaks shared state (SQLite, app.state)
- **Using deprecated events:** Don't use `@app.on_event("startup"/"shutdown")` - use lifespan
- **Mixing reload and workers:** These are mutually exclusive in Uvicorn

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Server process management | Custom daemon, pidfile system | systemd, Docker, supervisor | Battle-tested, handles crashes, logs, restart |
| Graceful shutdown | Custom SIGTERM handlers | Uvicorn's built-in shutdown + lifespan | Already handles connection draining, timeout |
| Log formatting | Custom log formatters | Uvicorn's built-in access logs | Follows standard formats (combined, JSON available) |
| Development reload | Custom file watchers | `--reload` flag | Uvicorn uses watchfiles, handles virtual envs |
| Multi-process | Custom fork/spawn logic | `--workers` or gunicorn | Handles process lifecycle, health checks, restarts |

**Key insight:** Uvicorn is a production-grade ASGI server with years of edge case handling. Custom solutions will miss important cases (connection draining, graceful shutdown timeouts, worker health checks, signal handling on Windows, etc.).

## Common Pitfalls

### Pitfall 1: Multiple Workers Break Background Worker
**What goes wrong:** User runs `cesar serve --workers 4` and gets 4 independent background workers, all trying to process the same jobs from SQLite database
**Why it happens:** Each worker process is independent with its own memory space and app.state. Uvicorn uses "spawn" (not fork), so each worker initializes its own BackgroundWorker instance
**How to avoid:** Either:
  1. Default to `workers=1` and document single-worker limitation
  2. Remove `--workers` flag entirely
  3. Add process-safe job locking (Redis, PostgreSQL advisory locks) before enabling workers
**Warning signs:** Duplicate job processing, database lock errors, jobs marked as processing multiple times

### Pitfall 2: Reload Mode Breaks Worker State
**What goes wrong:** File change triggers reload, old worker process terminates abruptly, in-progress jobs are left in "processing" state forever
**Why it happens:** Reload kills the process and starts fresh - no graceful shutdown
**How to avoid:** Document that `--reload` is for API development only, not for testing transcription jobs. Add startup logic to reset "processing" jobs to "queued" status
**Warning signs:** Jobs stuck in "processing" status after reload, orphaned temp files

### Pitfall 3: Blocking Shutdown on Long Transcriptions
**What goes wrong:** User presses Ctrl+C, server prints "Shutting down..." but hangs for minutes waiting for long transcription to complete
**Why it happens:** `asyncio.to_thread()` cannot be cancelled - thread continues until transcription completes
**How to avoid:**
  1. Accept this limitation and document it (simple approach)
  2. Set `timeout_graceful_shutdown` to reasonable value (e.g., 30s) - Uvicorn will force-kill after timeout
  3. Implement job re-queuing on forced shutdown (detect "processing" jobs on startup, mark as "queued")
**Warning signs:** Unresponsive shutdown, users pressing Ctrl+C multiple times

### Pitfall 4: Import String vs App Instance
**What goes wrong:** Passing `app` instance to `uvicorn.run(app, reload=True)` causes import errors or reload failures
**Why it happens:** Reload requires import string format ("module:app") to re-import after file changes
**How to avoid:** Always use import string format: `"cesar.api.server:app"`, not the imported object
**Warning signs:** "Cannot pickle" errors, reload not triggering, import errors on reload

### Pitfall 5: Database Connections Not Closed
**What goes wrong:** After shutdown, SQLite database file remains locked or shows connection warnings
**Why it happens:** Lifespan shutdown cleanup didn't await repo.close(), or error occurred before cleanup
**How to avoid:** Ensure lifespan shutdown always calls `await repo.close()` even if worker shutdown fails (use try/finally)
**Warning signs:** "Database is locked" errors, connection pool exhaustion warnings

### Pitfall 6: Silent Failures in Lifespan Startup
**What goes wrong:** Server starts successfully but worker never processes jobs, no error messages
**Why it happens:** Exception in lifespan startup is caught but server continues running without worker
**How to avoid:** Ensure lifespan startup errors propagate (don't catch broadly), add logging for worker start confirmation
**Warning signs:** Server responds to health check but jobs stay queued forever

## Code Examples

Verified patterns from official sources:

### Minimal Click Command for FastAPI Server
```python
# Source: Uvicorn Settings Documentation
# https://uvicorn.dev/settings/

import click
import uvicorn

@click.command()
@click.option('--port', '-p', default=5000, help='Port to bind to')
@click.option('--host', '-h', default='127.0.0.1', help='Host to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
@click.option('--workers', type=int, default=1, help='Number of workers')
def serve(port: int, host: str, reload: bool, workers: int):
    """Start the Cesar HTTP API server."""
    # Print startup message
    print(f"Listening on http://{host}:{port}")

    # Start server (blocks until shutdown)
    uvicorn.run(
        "cesar.api.server:app",  # Import string (required for reload)
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level="info",
        access_log=True  # Log all requests
    )
```

### Job Re-queuing on Startup (Recovery Pattern)
```python
# Pattern for handling orphaned "processing" jobs
# Source: Common practice in job queue systems

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to database
    repo = JobRepository(db_path)
    await repo.connect()

    # Re-queue any jobs left in "processing" state
    # (from unclean shutdown or crashes)
    processing_jobs = await repo.list_all()
    processing_jobs = [j for j in processing_jobs if j.status == JobStatus.PROCESSING]
    for job in processing_jobs:
        logger.warning(f"Re-queuing orphaned job {job.id}")
        job.status = JobStatus.QUEUED
        job.started_at = None
        await repo.update(job)

    # Start worker
    worker = BackgroundWorker(repo)
    worker_task = asyncio.create_task(worker.run())
    app.state.worker = worker
    app.state.worker_task = worker_task

    yield

    # Shutdown: cleanup
    await worker.shutdown()
    await worker_task
    await repo.close()
```

### Graceful Shutdown with Timeout
```python
# Source: Uvicorn Deployment Documentation
# https://www.uvicorn.org/deployment/

# Configure graceful shutdown timeout
uvicorn.run(
    "cesar.api.server:app",
    host="127.0.0.1",
    port=5000,
    timeout_graceful_shutdown=30,  # Wait 30s for shutdown before force-kill
    timeout_keep_alive=5,  # Close idle connections after 5s
)

# In lifespan shutdown:
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... startup ...
    yield

    # Shutdown with logging
    logger.info("Shutting down...")

    # Worker shutdown completes current job
    await worker.shutdown()  # Sets shutdown event
    await worker_task  # Waits for current job to finish

    # If job takes > timeout_graceful_shutdown, Uvicorn force-kills
    # On next startup, job will be re-queued by recovery logic
```

### Conditional Workers Based on Context
```python
# Pattern for warning about multi-worker issues
@click.command()
@click.option('--workers', type=int, default=1)
def serve(workers: int):
    if workers > 1:
        click.echo("WARNING: Multiple workers not recommended with background job queue.", err=True)
        click.echo("Each worker will run its own job processor.", err=True)
        click.echo("Use --workers 1 for proper job coordination.", err=True)
        if not click.confirm("Continue anyway?"):
            return

    uvicorn.run("cesar.api.server:app", workers=workers)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | Lifespan context manager | FastAPI 0.95.0+ | Lifespan is async-safe, ensures cleanup |
| Gunicorn required | Uvicorn built-in workers | Uvicorn 0.12+ | Simpler deployment, Windows compatible |
| Custom signal handlers | Uvicorn built-in handling | Always standard | Fewer bugs, proper connection draining |
| Pre-fork workers | Spawn-based workers | Uvicorn design | Cross-platform (Windows support) |
| `uvicorn.run(app)` | `uvicorn.run("module:app")` | When reload needed | Import string required for reload |

**Deprecated/outdated:**
- `@app.on_event("startup")` and `@app.on_event("shutdown")`: Use lifespan instead (deprecated in FastAPI 0.95.0+)
- `uvicorn.workers` in gunicorn: Use external `uvicorn-worker` package instead
- Mixing lifespan with on_event decorators: Choose one approach, not both

## Open Questions

Things that couldn't be fully resolved:

1. **Default value for timeout_graceful_shutdown**
   - What we know: Uvicorn accepts `--timeout-graceful-shutdown` parameter
   - What's unclear: Official documentation doesn't specify default value (may be unlimited)
   - Recommendation: Explicitly set to 30 seconds for predictable behavior, document that long transcriptions may be interrupted

2. **Multi-worker job coordination strategy**
   - What we know: Multiple workers each create their own BackgroundWorker, causing duplicate processing
   - What's unclear: Best approach for process-safe coordination (Redis locks, PostgreSQL advisory locks, or prohibit multi-worker)
   - Recommendation: Start with single worker (workers=1), document limitation, defer multi-worker support to later phase

3. **Cancelling in-progress transcriptions**
   - What we know: `asyncio.to_thread()` cannot cancel running threads, transcription will complete
   - What's unclear: Whether to implement cancellation-checking in transcriber (would require refactor)
   - Recommendation: Accept that shutdown waits for current job, implement job re-queuing for timeout scenarios

## Sources

### Primary (HIGH confidence)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - Lifespan context manager pattern (current standard)
- [FastAPI Manual Deployment](https://fastapi.tiangolo.com/deployment/manually/) - uvicorn.run() usage
- [Uvicorn Settings](https://www.uvicorn.org/settings/) - Complete configuration options including timeout_graceful_shutdown
- [Uvicorn Deployment](https://www.uvicorn.org/deployment/) - Workers, signal handling, graceful shutdown

### Secondary (MEDIUM confidence)
- [FastAPI Server Workers](https://fastapi.tiangolo.com/deployment/server-workers/) - Multi-worker patterns
- [Graceful Shutdowns with asyncio - roguelynn](https://roguelynn.com/words/asyncio-graceful-shutdowns/) - Signal handling patterns
- [GeeksforGeeks FastAPI-Uvicorn](https://www.geeksforgeeks.org/python/fastapi-uvicorn/) - Basic integration examples
- [Medium: Mastering Gunicorn and Uvicorn](https://medium.com/@iklobato/mastering-gunicorn-and-uvicorn-the-right-way-to-deploy-fastapi-applications-aaa06849841e) - Production deployment patterns

### Tertiary (LOW confidence, marked for validation)
- WebSearch results about multi-worker coordination with SQLite - anecdotal evidence of issues
- Various GitHub discussions about cancellation challenges - specific to use cases, may not apply

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - uvicorn.run() is documented official approach
- Architecture: HIGH - Lifespan pattern is current FastAPI standard, well documented
- Pitfalls: HIGH - Multi-worker issues verified in official docs and GitHub issues
- Job re-queuing: MEDIUM - Pattern is common but implementation details are project-specific
- Timeout defaults: LOW - Default value for timeout_graceful_shutdown not found in docs

**Research date:** 2026-01-23
**Valid until:** 2026-02-23 (30 days - relatively stable technology stack)
