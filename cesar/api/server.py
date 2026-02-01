"""
FastAPI server for Cesar Transcription API.

Provides the HTTP server with lifespan events for worker lifecycle
management and health monitoring endpoints.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional, Tuple, Union

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, status
from fastapi import Path as PathParam
from fastapi.responses import JSONResponse

from pydantic import BaseModel, Field, model_validator

from cesar.api.file_handler import download_from_url, save_upload_file
from cesar.api.models import Job, JobStatus
from cesar.api.repository import JobRepository
from cesar.api.worker import BackgroundWorker
from cesar.config import (
    CesarConfig,
    ConfigError,
    load_config,
    get_api_config_path,
)
from cesar.youtube_handler import YouTubeDownloadError, check_ffmpeg_available, is_youtube_url

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "cesar" / "jobs.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage server lifecycle: start worker on startup, cleanup on shutdown.

    This async context manager:
    - Loads configuration from config.toml in current directory
    - Initializes JobRepository and connects to database
    - Creates and starts BackgroundWorker in a task
    - Stores components in app.state for endpoint access
    - On shutdown: stops worker gracefully and closes database

    Args:
        app: FastAPI application instance
    """
    # Load configuration
    config_path = get_api_config_path()
    try:
        config = load_config(config_path)
        if config_path.exists():
            logger.info(f"Loaded config from {config_path}")
        else:
            logger.debug("No config file found, using defaults")
    except ConfigError as e:
        logger.error(f"Config error: {e}")
        raise  # Let server fail to start on invalid config

    # Store config in app.state for endpoint access (used in Phase 13)
    app.state.config = config

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
    worker = BackgroundWorker(repo, config=config)
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


@app.exception_handler(YouTubeDownloadError)
async def youtube_error_handler(request: Request, exc: YouTubeDownloadError):
    """Handle YouTube errors with structured JSON response.

    Returns error_type and message for programmatic error handling.
    Uses http_status from exception class attributes.
    """
    return JSONResponse(
        status_code=getattr(exc, 'http_status', 400),
        content={
            "error_type": getattr(exc, 'error_type', 'youtube_error'),
            "message": str(exc),
        }
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
    diarize: bool = Form(default=True),
    min_speakers: Optional[int] = Form(default=None),
    max_speakers: Optional[int] = Form(default=None),
):
    """Upload audio file for transcription.

    Accepts multipart/form-data with an audio file and optional model parameter.
    The file is saved to a temporary location and a job is created for processing.

    Args:
        file: Audio file to transcribe (mp3, wav, m4a, ogg, flac, aac, wma, webm)
        model: Whisper model size (tiny, base, small, medium, large)
        diarize: Enable speaker diarization (default: True)
        min_speakers: Minimum number of speakers to detect
        max_speakers: Maximum number of speakers to detect

    Returns:
        Job: Created job with queued status

    Raises:
        HTTPException: 413 if file too large (max 100MB)
        HTTPException: 400 if invalid file type or speaker range invalid
    """
    # Validate speaker range at request time
    if (min_speakers is not None and max_speakers is not None and
        min_speakers > max_speakers):
        raise HTTPException(
            status_code=400,
            detail=f"min_speakers ({min_speakers}) cannot exceed max_speakers ({max_speakers})"
        )

    tmp_path = await save_upload_file(file)
    job = Job(
        audio_path=tmp_path,
        model_size=model,
        diarize=diarize,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )
    await app.state.repo.create(job)
    return job


class DiarizeOptions(BaseModel):
    """Diarization options when using object form.

    Allows fine-grained control over speaker diarization including
    minimum and maximum speaker counts.
    """

    enabled: bool = True
    min_speakers: Optional[int] = Field(default=None, ge=1)
    max_speakers: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode='after')
    def validate_speaker_range(self) -> 'DiarizeOptions':
        """Validate min_speakers <= max_speakers when both are set."""
        if (self.min_speakers is not None and
            self.max_speakers is not None and
            self.min_speakers > self.max_speakers):
            raise ValueError(
                f"min_speakers ({self.min_speakers}) cannot exceed "
                f"max_speakers ({self.max_speakers})"
            )
        return self


class TranscribeURLRequest(BaseModel):
    """Request body for URL-based transcription."""

    url: str
    model: str = "base"
    diarize: Union[bool, DiarizeOptions] = True

    def get_diarize_enabled(self) -> bool:
        """Get whether diarization is enabled.

        Returns:
            True if diarization is enabled, False otherwise
        """
        if isinstance(self.diarize, bool):
            return self.diarize
        return self.diarize.enabled

    def get_speaker_range(self) -> Tuple[Optional[int], Optional[int]]:
        """Get min/max speaker range for diarization.

        Returns:
            Tuple of (min_speakers, max_speakers), both may be None
        """
        if isinstance(self.diarize, bool):
            return (None, None)
        return (self.diarize.min_speakers, self.diarize.max_speakers)


@app.post("/transcribe/url", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def transcribe_from_url(request: TranscribeURLRequest):
    """Download audio from URL and transcribe.

    Accepts a JSON body with URL and optional model parameter.

    For YouTube URLs: Creates job with DOWNLOADING status and lets worker handle download.
    For regular URLs: Downloads first, then creates job with QUEUED status.

    Args:
        request: Request body with url, optional model, and diarization options

    Returns:
        Job: Created job with downloading status (YouTube) or queued status (regular URL)

    Raises:
        HTTPException: 408 if URL download times out
        HTTPException: 400 if download fails or invalid file type
    """
    # Extract diarization parameters from request
    diarize_enabled = request.get_diarize_enabled()
    min_speakers, max_speakers = request.get_speaker_range()

    if is_youtube_url(request.url):
        # YouTube: Create job with DOWNLOADING status, let worker handle download
        job = Job(
            audio_path=request.url,  # Store URL, not file path
            model_size=request.model,
            status=JobStatus.DOWNLOADING,
            download_progress=0,
            diarize=diarize_enabled,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        await app.state.repo.create(job)
        return job
    else:
        # Regular URL: Download first, then queue
        tmp_path = await download_from_url(request.url)
        job = Job(
            audio_path=tmp_path,
            model_size=request.model,
            diarize=diarize_enabled,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        await app.state.repo.create(job)
        return job
