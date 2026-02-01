"""
Background worker for processing transcription jobs.

Provides the BackgroundWorker class that polls for queued jobs
and processes them sequentially using AudioTranscriber.
"""
import asyncio
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from cesar.api.models import JobStatus
from cesar.api.repository import JobRepository
from cesar.config import CesarConfig
from cesar.diarization import SpeakerDiarizer, DiarizationError, AuthenticationError
from cesar.orchestrator import TranscriptionOrchestrator
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

    def __init__(
        self,
        repository: JobRepository,
        poll_interval: float = 1.0,
        config: Optional[CesarConfig] = None
    ):
        """Initialize worker with repository and poll interval.

        Args:
            repository: JobRepository instance for job persistence
            poll_interval: Seconds to wait between polls when no jobs available
            config: Optional CesarConfig for HF token resolution
        """
        self.repository = repository
        self.poll_interval = poll_interval
        self.config = config
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

    def _get_hf_token(self) -> Optional[str]:
        """Resolve HuggingFace token from config, env, or cache.

        Resolution order:
        1. self.config.hf_token if config provided
        2. HF_TOKEN environment variable
        3. ~/.cache/huggingface/token file

        Returns:
            HF token or None if not found
        """
        # Check config first
        if self.config and self.config.hf_token:
            return self.config.hf_token

        # Try environment variable
        env_token = os.getenv('HF_TOKEN')
        if env_token:
            return env_token

        # Try cached token
        token_path = Path.home() / '.cache' / 'huggingface' / 'token'
        if token_path.exists():
            return token_path.read_text().strip()

        return None

    def _update_progress(
        self,
        job,
        phase: str,
        overall_pct: int,
        phase_pct: int
    ) -> None:
        """Update job progress tracking fields.

        Args:
            job: Job instance to update
            phase: Current processing phase (downloading, transcribing, diarizing, formatting)
            overall_pct: Overall progress percentage (0-100)
            phase_pct: Current phase progress percentage (0-100)

        Note:
            Actual DB update happens at status transitions, not on every progress update.
        """
        job.progress = int(overall_pct)
        job.progress_phase = phase
        job.progress_phase_pct = int(phase_pct)

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

        Handles YouTube downloads for DOWNLOADING status jobs, then runs transcription
        with optional diarization. Updates job status and handles partial failures
        gracefully (transcription OK but diarization failed).

        Args:
            job: Job instance to process
        """
        self._current_job_id = job.id
        logger.info(f"Processing job {job.id}: {job.audio_path}")

        try:
            # Check for retry scenario: job has result_text but diarization_error
            is_retry = (
                job.result_text is not None and
                job.diarization_error is not None
            )

            # Handle YouTube download phase
            if job.status == JobStatus.DOWNLOADING:
                # Update progress to 0 (starting download)
                job.download_progress = 0
                self._update_progress(job, "downloading", 0, 0)
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
                    self._update_progress(job, "transcribing", 0, 0)
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
                self._update_progress(job, "transcribing", 0, 0)
                await self.repository.update(job)

            # Run transcription with orchestrator in thread pool (blocking operation)
            result = await asyncio.to_thread(
                self._run_transcription_with_orchestrator,
                job.audio_path,
                job.model_size,
                job.diarize,
                job.min_speakers,
                job.max_speakers,
                is_retry
            )

            # Update job with results
            job.completed_at = datetime.utcnow()
            job.result_text = result["text"]
            job.detected_language = result.get("language", "unknown")

            # Handle diarization-specific results
            if result.get("diarization_error_code"):
                # Diarization was requested but failed
                job.status = JobStatus.PARTIAL
                job.diarization_error_code = result["diarization_error_code"]
                job.diarization_error = result.get("diarization_error", "Diarization failed")
                job.diarized = False
                job.speaker_count = None
            elif result.get("diarization_succeeded") is False and job.diarize:
                # Orchestrator reported diarization failure
                job.status = JobStatus.PARTIAL
                job.diarization_error = "Diarization failed during processing"
                job.diarization_error_code = "diarization_failed"
                job.diarized = False
                job.speaker_count = None
            else:
                # Success (or diarization not requested)
                job.status = JobStatus.COMPLETED
                if result.get("diarization_succeeded"):
                    job.diarized = True
                    job.speaker_count = result.get("speaker_count", 0)
                else:
                    job.diarized = False
                    job.speaker_count = None

            self._update_progress(job, "formatting", 100, 100)
            await self.repository.update(job)

            logger.info(f"Job {job.id} completed with status {job.status.value}")

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

    def _run_transcription_with_orchestrator(
        self,
        audio_path: str,
        model_size: str,
        diarize: bool,
        min_speakers: Optional[int],
        max_speakers: Optional[int],
        is_retry: bool = False
    ) -> Dict:
        """Run transcription with optional diarization using orchestrator.

        This method is called in a thread pool to avoid blocking the event loop.
        Uses TranscriptionOrchestrator when diarization is requested.

        Args:
            audio_path: Path to audio file
            model_size: Whisper model size to use
            diarize: Whether to enable speaker diarization
            min_speakers: Minimum expected speakers (optional)
            max_speakers: Maximum expected speakers (optional)
            is_retry: Whether this is a retry of a partial job

        Returns:
            Dictionary with transcription results:
            - text: Transcription text
            - language: Detected language
            - diarization_succeeded: Whether diarization worked (if requested)
            - speaker_count: Number of speakers (if diarization succeeded)
            - diarization_error_code: Error code if diarization failed
            - diarization_error: Error message if diarization failed
        """
        # Create temporary output file
        fd, temp_output = tempfile.mkstemp(suffix='.md' if diarize else '.txt')
        temp_output_path = Path(temp_output)

        try:
            os.close(fd)

            # Create transcriber
            transcriber = AudioTranscriber(model_size=model_size)

            if not diarize:
                # Simple transcription without diarization
                result = transcriber.transcribe_file(audio_path, str(temp_output_path))

                with open(temp_output_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                return {
                    "text": text,
                    "language": result.get("language", "unknown"),
                    "diarization_succeeded": False,
                    "speaker_count": None
                }

            # Diarization requested - check for HF token
            hf_token = self._get_hf_token()
            if not hf_token:
                # No HF token available - run transcription only, report partial
                result = transcriber.transcribe_file(audio_path, str(temp_output_path))

                with open(temp_output_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                return {
                    "text": text,
                    "language": result.get("language", "unknown"),
                    "diarization_succeeded": False,
                    "diarization_error_code": "hf_token_required",
                    "diarization_error": (
                        "HuggingFace token required for speaker diarization. "
                        "Set hf_token in config or HF_TOKEN environment variable."
                    )
                }

            # Create diarizer and orchestrator
            try:
                diarizer = SpeakerDiarizer(hf_token=hf_token)
                orchestrator = TranscriptionOrchestrator(
                    transcriber=transcriber,
                    diarizer=diarizer
                )

                # Run orchestration
                orch_result = orchestrator.orchestrate(
                    audio_path=Path(audio_path),
                    output_path=temp_output_path,
                    enable_diarization=True,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )

                # Read the result text
                with open(orch_result.output_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                return {
                    "text": text,
                    "language": "unknown",  # orchestrator doesn't return language
                    "diarization_succeeded": orch_result.diarization_succeeded,
                    "speaker_count": orch_result.speakers_detected if orch_result.diarization_succeeded else None
                }

            except AuthenticationError as e:
                # HF token invalid - run transcription only
                logger.warning(f"HuggingFace authentication failed: {e}")
                result = transcriber.transcribe_file(audio_path, str(temp_output_path))

                with open(temp_output_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                return {
                    "text": text,
                    "language": result.get("language", "unknown"),
                    "diarization_succeeded": False,
                    "diarization_error_code": "hf_token_invalid",
                    "diarization_error": str(e)
                }

            except DiarizationError as e:
                # Generic diarization failure - run transcription only
                logger.warning(f"Diarization failed: {e}")
                result = transcriber.transcribe_file(audio_path, str(temp_output_path))

                with open(temp_output_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                return {
                    "text": text,
                    "language": result.get("language", "unknown"),
                    "diarization_succeeded": False,
                    "diarization_error_code": "diarization_failed",
                    "diarization_error": str(e)
                }

        finally:
            # Clean up temp file(s)
            temp_output_path.unlink(missing_ok=True)
            # Also try to clean up .txt if we created .md
            if diarize:
                Path(str(temp_output_path).replace('.md', '.txt')).unlink(missing_ok=True)
