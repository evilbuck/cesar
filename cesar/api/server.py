"""
FastAPI server for Cesar Transcription API.

Provides the HTTP server with lifespan events for worker lifecycle
management and health monitoring endpoints.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from cesar.api.repository import JobRepository
from cesar.api.worker import BackgroundWorker

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "cesar" / "jobs.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage server lifecycle: start worker on startup, cleanup on shutdown.

    This async context manager:
    - Initializes JobRepository and connects to database
    - Creates and starts BackgroundWorker in a task
    - Stores components in app.state for endpoint access
    - On shutdown: stops worker gracefully and closes database

    Args:
        app: FastAPI application instance
    """
    # Startup: initialize repository and worker
    db_path = getattr(app.state, "db_path", DEFAULT_DB_PATH)

    # Ensure database directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Connecting to database: {db_path}")
    repo = JobRepository(db_path)
    await repo.connect()

    logger.info("Starting background worker")
    worker = BackgroundWorker(repo)
    worker_task = asyncio.create_task(worker.run())

    # Store in app.state for endpoint access
    app.state.repo = repo
    app.state.worker = worker
    app.state.worker_task = worker_task

    yield  # App is running, handling requests

    # Shutdown: cleanup
    logger.info("Shutting down background worker")
    await worker.shutdown()
    await worker_task
    logger.info("Closing database connection")
    await repo.close()
    logger.info("Server shutdown complete")


app = FastAPI(
    title="Cesar Transcription API",
    description="Offline audio transcription with async job queue",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint.

    Returns server health status and worker state.

    Returns:
        dict: Health status with "status" and "worker" keys
            - status: "healthy" when server is operational
            - worker: "running" if worker task is active, "stopped" if done
    """
    worker_task = getattr(app.state, "worker_task", None)

    if worker_task is None:
        worker_status = "stopped"
    elif worker_task.done():
        worker_status = "stopped"
    else:
        worker_status = "running"

    return {
        "status": "healthy",
        "worker": worker_status,
    }
