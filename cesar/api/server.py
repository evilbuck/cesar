"""
FastAPI server for Cesar Transcription API.

Provides the HTTP server with lifespan events for worker lifecycle
management and health monitoring endpoints.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Form, HTTPException, UploadFile, status
from fastapi import Path as PathParam

from pydantic import BaseModel

from cesar.api.file_handler import download_from_url, save_upload_file
from cesar.api.models import Job, JobStatus
from cesar.api.repository import JobRepository
from cesar.api.worker import BackgroundWorker
from cesar.youtube_handler import check_ffmpeg_available, is_youtube_url

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

    # Re-queue any jobs left in "processing" state (from unclean shutdown)
    all_jobs = await repo.list_all()
    for job in all_jobs:
        if job.status == JobStatus.PROCESSING:
            logger.warning(f"Re-queuing orphaned job {job.id}")
            job.status = JobStatus.QUEUED
            job.started_at = None
            await repo.update(job)

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

    Returns server health status, worker state, and YouTube capability.

    Returns:
        dict: Health status with:
            - status: "healthy" when server is operational
            - worker: "running" if worker task is active, "stopped" if done
            - youtube: object with ffmpeg_available and message
    """
    worker_task = getattr(app.state, "worker_task", None)

    if worker_task is None:
        worker_status = "stopped"
    elif worker_task.done():
        worker_status = "stopped"
    else:
        worker_status = "running"

    # Check YouTube capability (FFmpeg availability)
    ffmpeg_available, ffmpeg_message = check_ffmpeg_available()

    return {
        "status": "healthy",
        "worker": worker_status,
        "youtube": {
            "available": ffmpeg_available,
            "message": ffmpeg_message if not ffmpeg_available else "YouTube transcription supported",
        },
    }


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str = PathParam(..., description="Job UUID")):
    """Get job status and results by ID.

    Args:
        job_id: Unique job identifier (UUID)

    Returns:
        Job: The job with matching ID

    Raises:
        HTTPException: 404 if job not found
    """
    job = await app.state.repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@app.get("/jobs", response_model=List[Job])
async def list_jobs(status: Optional[str] = None):
    """List all jobs, optionally filtered by status.

    Args:
        status: Optional status filter (queued, processing, completed, error)

    Returns:
        List[Job]: All jobs matching the filter criteria

    Raises:
        HTTPException: 400 if invalid status provided
    """
    jobs = await app.state.repo.list_all()

    if status:
        # Validate status is a valid JobStatus value
        valid_statuses = [s.value for s in JobStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid: {', '.join(valid_statuses)}",
            )
        # Filter jobs by status
        jobs = [job for job in jobs if job.status.value == status]

    return jobs


@app.post("/transcribe", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def transcribe_file_upload(
    file: UploadFile,
    model: str = Form(default="base"),
):
    """Upload audio file for transcription.

    Accepts multipart/form-data with an audio file and optional model parameter.
    The file is saved to a temporary location and a job is created for processing.

    Args:
        file: Audio file to transcribe (mp3, wav, m4a, ogg, flac, aac, wma, webm)
        model: Whisper model size (tiny, base, small, medium, large)

    Returns:
        Job: Created job with queued status

    Raises:
        HTTPException: 413 if file too large (max 100MB)
        HTTPException: 400 if invalid file type
    """
    tmp_path = await save_upload_file(file)
    job = Job(audio_path=tmp_path, model_size=model)
    await app.state.repo.create(job)
    return job


class TranscribeURLRequest(BaseModel):
    """Request body for URL-based transcription."""

    url: str
    model: str = "base"


@app.post("/transcribe/url", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def transcribe_from_url(request: TranscribeURLRequest):
    """Download audio from URL and transcribe.

    Accepts a JSON body with URL and optional model parameter.

    For YouTube URLs: Creates job with DOWNLOADING status and lets worker handle download.
    For regular URLs: Downloads first, then creates job with QUEUED status.

    Args:
        request: Request body with url and optional model

    Returns:
        Job: Created job with downloading status (YouTube) or queued status (regular URL)

    Raises:
        HTTPException: 408 if URL download times out
        HTTPException: 400 if download fails or invalid file type
    """
    if is_youtube_url(request.url):
        # YouTube: Create job with DOWNLOADING status, let worker handle download
        job = Job(
            audio_path=request.url,  # Store URL, not file path
            model_size=request.model,
            status=JobStatus.DOWNLOADING,
            download_progress=0,
        )
        await app.state.repo.create(job)
        return job
    else:
        # Regular URL: Download first, then queue
        tmp_path = await download_from_url(request.url)
        job = Job(audio_path=tmp_path, model_size=request.model)
        await app.state.repo.create(job)
        return job
