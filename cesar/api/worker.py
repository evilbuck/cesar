"""
Background worker for processing transcription jobs.

Provides the BackgroundWorker class that polls for queued jobs
and processes them sequentially using AudioTranscriber.
"""
import asyncio
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from cesar.api.models import JobStatus
from cesar.api.repository import JobRepository
from cesar.transcriber import AudioTranscriber
from cesar.youtube_handler import (
    download_youtube_audio,
    YouTubeDownloadError,
    FFmpegNotFoundError,
)

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Background worker that processes transcription jobs sequentially.

    The worker polls the repository for queued jobs and processes them
    one at a time in FIFO order. It runs transcription in a thread pool
    to avoid blocking the event loop.

    Example:
        repo = JobRepository(Path("jobs.db"))
        await repo.connect()
        worker = BackgroundWorker(repo)

        # Run worker (blocks until shutdown)
        await worker.run()

        # From another task/signal handler:
        await worker.shutdown()
    """

    def __init__(self, repository: JobRepository, poll_interval: float = 1.0):
        """Initialize worker with repository and poll interval.

        Args:
            repository: JobRepository instance for job persistence
            poll_interval: Seconds to wait between polls when no jobs available
        """
        self.repository = repository
        self.poll_interval = poll_interval
        self._shutdown_event = asyncio.Event()
        self._current_job_id: Optional[str] = None

    @property
    def is_processing(self) -> bool:
        """Check if worker is currently processing a job.

        Returns:
            True if a job is being processed, False otherwise
        """
        return self._current_job_id is not None

    @property
    def current_job_id(self) -> Optional[str]:
        """Get the ID of the job currently being processed.

        Returns:
            Job ID if processing, None otherwise
        """
        return self._current_job_id

    async def run(self) -> None:
        """Run the worker loop until shutdown is requested.

        Continuously polls for queued jobs and processes them sequentially.
        The loop exits gracefully when shutdown() is called.
        """
        logger.info("Background worker starting")

        try:
            while not self._shutdown_event.is_set():
                # Poll for next job
                job = await self.repository.get_next_queued()

                if job:
                    # Process the job
                    await self._process_job(job)
                else:
                    # No job available, wait for poll interval or shutdown
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self.poll_interval
                        )
                    except asyncio.TimeoutError:
                        # Timeout is expected - continue polling
                        pass
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
        finally:
            logger.info("Background worker stopped")

    async def shutdown(self) -> None:
        """Request graceful shutdown of the worker.

        Sets the shutdown event to stop the worker loop.
        The current job will complete before shutdown.
        """
        logger.info("Shutdown requested")
        self._shutdown_event.set()

    async def _process_job(self, job) -> None:
        """Process a single transcription job.

        Handles YouTube downloads for DOWNLOADING status jobs, then runs transcription.
        Updates job status to PROCESSING, runs transcription in thread pool,
        and updates job with results or error message.

        Args:
            job: Job instance to process
        """
        self._current_job_id = job.id
        logger.info(f"Processing job {job.id}: {job.audio_path}")

        try:
            # Handle YouTube download phase
            if job.status == JobStatus.DOWNLOADING:
                # Update progress to 0 (starting download)
                job.download_progress = 0
                job.started_at = datetime.utcnow()
                await self.repository.update(job)

                # Download YouTube audio (blocking, run in thread pool)
                try:
                    audio_path = await asyncio.to_thread(
                        download_youtube_audio,
                        job.audio_path  # Contains the URL
                    )
                    # Update progress to 100 (download complete)
                    job.download_progress = 100
                    job.audio_path = str(audio_path)  # Replace URL with file path
                    job.status = JobStatus.PROCESSING
                    await self.repository.update(job)
                except (YouTubeDownloadError, FFmpegNotFoundError) as e:
                    job.status = JobStatus.ERROR
                    job.completed_at = datetime.utcnow()
                    job.error_message = str(e)
                    await self.repository.update(job)
                    return
            else:
                # Regular job - update to PROCESSING
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.utcnow()
                await self.repository.update(job)

            # Run transcription in thread pool (blocking operation)
            result = await asyncio.to_thread(
                self._run_transcription,
                job.audio_path,
                job.model_size
            )

            # Update to COMPLETED status
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result_text = result["text"]
            job.detected_language = result["language"]
            await self.repository.update(job)

            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            # Update to ERROR status
            logger.error(f"Job {job.id} failed: {e}", exc_info=True)
            job.status = JobStatus.ERROR
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            await self.repository.update(job)

        finally:
            self._current_job_id = None

    def _run_transcription(self, audio_path: str, model_size: str) -> Dict[str, str]:
        """Run transcription synchronously (blocking operation).

        This method is called in a thread pool to avoid blocking the event loop.

        Args:
            audio_path: Path to audio file
            model_size: Whisper model size to use

        Returns:
            Dictionary with "text" and "language" keys

        Raises:
            FileNotFoundError: If audio file doesn't exist
            ValueError: If audio file is invalid
            RuntimeError: If transcription fails
        """
        # Create temporary output file
        fd, temp_output = tempfile.mkstemp(suffix='.txt')
        temp_output_path = Path(temp_output)

        try:
            # Close the file descriptor (AudioTranscriber will open the file itself)
            import os
            os.close(fd)

            # Create transcriber and run transcription
            transcriber = AudioTranscriber(model_size=model_size)
            result = transcriber.transcribe_file(audio_path, str(temp_output_path))

            # Read transcription text
            with open(temp_output_path, 'r', encoding='utf-8') as f:
                text = f.read()

            return {
                "text": text,
                "language": result.get("language", "unknown")
            }

        finally:
            # Clean up temp file
            temp_output_path.unlink(missing_ok=True)
