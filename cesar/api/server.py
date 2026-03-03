"""
Cesar Transcription API Server with Web Frontend.

Provides the HTTP API with async job queue and serves the static web frontend.
Designed for VPS deployment (CPU or GPU).
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, status
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from cesar.api.models import Job, JobStatus
from cesar.api.repository import JobRepository
from cesar.api.worker import BackgroundWorker
from cesar.youtube_handler import YouTubeDownloadError, check_ffmpeg_available, is_youtube_url
from cesar.api.file_handler import download_from_url, save_upload_file

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "cesar" / "jobs.db"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage server lifecycle: start worker on startup, cleanup on shutdown."""
    db_path = getattr(app.state, "db_path", DEFAULT_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Connecting to database: {db_path}")
    repo = JobRepository(db_path)
    await repo.connect()

    # Re-queue orphaned jobs from crashes
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

    app.state.repo = repo
    app.state.worker = worker
    app.state.worker_task = worker_task

    yield

    # Shutdown
    logger.info("Shutting down background worker")
    await worker.shutdown()
    await worker_task
    logger.info("Closing database connection")
    await repo.close()
    logger.info("Server shutdown complete")


app = FastAPI(
    title="Cesar Transcription API",
    description="Offline audio transcription with async job queue",
    version="2.2.0",
    lifespan=lifespan,
)


@app.exception_handler(YouTubeDownloadError)
async def youtube_error_handler(request: Request, exc: YouTubeDownloadError):
    """Handle YouTube errors with structured JSON response."""
    return JSONResponse(
        status_code=getattr(exc, 'http_status', 400),
        content={
            "error_type": getattr(exc, 'error_type', 'youtube_error'),
            "message": str(exc),
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint with device info."""
    worker_task = getattr(app.state, "worker_task", None)
    worker_status = "stopped" if worker_task is None or worker_task.done() else "running"
    
    ffmpeg_available, ffmpeg_message = check_ffmpeg_available()
    
    # Get device info
    from cesar.device_detection import OptimalConfiguration
    config = OptimalConfiguration()
    device = config.get_optimal_device()
    
    return {
        "status": "healthy",
        "worker": worker_status,
        "device": device,
        "youtube": {
            "available": ffmpeg_available,
            "message": "YouTube transcription supported" if ffmpeg_available else ffmpeg_message,
        },
    }


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str = PathParam(..., description="Job UUID")):
    """Get job status and results by ID."""
    job = await app.state.repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@app.get("/jobs", response_model=List[Job])
async def list_jobs(status: Optional[str] = None):
    """List all jobs, optionally filtered by status."""
    jobs = await app.state.repo.list_all()

    if status:
        valid_statuses = [s.value for s in JobStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid: {', '.join(valid_statuses)}",
            )
        jobs = [job for job in jobs if job.status.value == status]

    return jobs


@app.post("/transcribe", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def transcribe_file_upload(
    file: UploadFile,
    model: str = Form(default="base"),
):
    """Upload audio file for transcription."""
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
    """Download audio from URL and transcribe."""
    if is_youtube_url(request.url):
        job = Job(
            audio_path=request.url,
            model_size=request.model,
            status=JobStatus.DOWNLOADING,
            download_progress=0,
        )
        await app.state.repo.create(job)
        return job
    else:
        tmp_path = await download_from_url(request.url)
        job = Job(audio_path=tmp_path, model_size=request.model)
        await app.state.repo.create(job)
        return job


# Serve web frontend
@app.get("/")
async def serve_frontend():
    """Serve the main web frontend."""
    return FileResponse(WEB_DIR / "index.html")


# Mount static files
app.mount("/", StaticFiles(directory=WEB_DIR), name="static")
