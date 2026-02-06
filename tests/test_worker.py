"""
Unit tests for BackgroundWorker.

Tests worker behavior: job processing, graceful shutdown, error handling,
FIFO order, properties, recovery after error, and multiple jobs.
"""
import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from cesar.api import BackgroundWorker, Job, JobRepository, JobStatus


class TestBackgroundWorker(unittest.IsolatedAsyncioTestCase):
    """Test cases for BackgroundWorker behavior."""

    async def asyncSetUp(self):
        """Set up fresh repository and worker for each test."""
        self.repo = JobRepository(":memory:")
        await self.repo.connect()
        self.worker = BackgroundWorker(self.repo, poll_interval=0.1)

    async def asyncTearDown(self):
        """Close repository connection after each test."""
        await self.repo.close()

    async def test_worker_processes_queued_job(self):
        """Test worker processes a queued job and updates status to COMPLETED."""
        # Create a job (diarize defaults to True, but we disable to test simple path)
        job = Job(audio_path="/test/audio.mp3", model_size="base", diarize=False)
        await self.repo.create(job)

        # Mock _run_transcription_with_orchestrator to return fake result
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            return_value={
                "text": "Hello world",
                "language": "en",
                "diarization_succeeded": False,
                "speaker_count": None
            }
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait briefly for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job was updated to COMPLETED
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.COMPLETED)
        self.assertEqual(retrieved.result_text, "Hello world")
        self.assertEqual(retrieved.detected_language, "en")
        self.assertIsNotNone(retrieved.started_at)
        self.assertIsNotNone(retrieved.completed_at)

    async def test_worker_graceful_shutdown(self):
        """Test worker stops gracefully when shutdown is requested."""
        # Start worker (no jobs available)
        worker_task = asyncio.create_task(self.worker.run())

        # Wait briefly
        await asyncio.sleep(0.05)

        # Request shutdown
        await self.worker.shutdown()

        # Verify worker stops within timeout
        try:
            await asyncio.wait_for(worker_task, timeout=1.0)
        except asyncio.TimeoutError:
            self.fail("Worker did not stop within timeout")

    async def test_worker_handles_transcription_error(self):
        """Test worker marks job as ERROR when transcription fails."""
        # Create a job
        job = Job(audio_path="/nonexistent/audio.mp3", model_size="base", diarize=False)
        await self.repo.create(job)

        # Mock _run_transcription_with_orchestrator to raise exception
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            side_effect=FileNotFoundError("Audio file not found")
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait briefly for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job was updated to ERROR
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.ERROR)
        self.assertIsNotNone(retrieved.error_message)
        self.assertIn("Audio file not found", retrieved.error_message)
        self.assertIsNotNone(retrieved.completed_at)
        self.assertIsNone(retrieved.result_text)

    async def test_worker_fifo_order(self):
        """Test worker processes jobs in FIFO order (oldest first)."""
        # Create 3 jobs with delays to ensure different timestamps
        job1 = Job(audio_path="/test/audio1.mp3", diarize=False)
        await self.repo.create(job1)
        await asyncio.sleep(0.01)

        job2 = Job(audio_path="/test/audio2.mp3", diarize=False)
        await self.repo.create(job2)
        await asyncio.sleep(0.01)

        job3 = Job(audio_path="/test/audio3.mp3", diarize=False)
        await self.repo.create(job3)

        # Track processing order
        processed_order = []

        def mock_transcription(audio_path, model_size, diarize, min_speakers, max_speakers, is_retry):
            processed_order.append(audio_path)
            return {
                "text": f"Transcription of {audio_path}",
                "language": "en",
                "diarization_succeeded": False,
                "speaker_count": None
            }

        # Mock _run_transcription_with_orchestrator
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            side_effect=mock_transcription
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for all jobs to process
            await asyncio.sleep(0.5)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify FIFO order (oldest first)
        self.assertEqual(len(processed_order), 3)
        self.assertEqual(processed_order[0], "/test/audio1.mp3")
        self.assertEqual(processed_order[1], "/test/audio2.mp3")
        self.assertEqual(processed_order[2], "/test/audio3.mp3")

    async def test_worker_is_processing_property(self):
        """Test is_processing and current_job_id properties during processing."""
        # Create a job
        job = Job(audio_path="/test/audio.mp3", diarize=False)
        await self.repo.create(job)

        # Track property values during processing
        property_checks = []

        async def check_properties():
            """Helper to check properties while worker is running."""
            await asyncio.sleep(0.15)  # Wait for job to start processing
            property_checks.append({
                "is_processing": self.worker.is_processing,
                "current_job_id": self.worker.current_job_id
            })

        # Mock _run_transcription_with_orchestrator to sleep briefly
        def mock_transcription(audio_path, model_size, diarize, min_speakers, max_speakers, is_retry):
            import time
            time.sleep(0.2)  # Simulate processing
            return {
                "text": "Hello",
                "language": "en",
                "diarization_succeeded": False,
                "speaker_count": None
            }

        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            side_effect=mock_transcription
        ):
            # Start worker and property checker
            worker_task = asyncio.create_task(self.worker.run())
            checker_task = asyncio.create_task(check_properties())

            # Wait for checker to complete
            await checker_task

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify properties were set during processing
        self.assertEqual(len(property_checks), 1)
        self.assertTrue(property_checks[0]["is_processing"])
        self.assertEqual(property_checks[0]["current_job_id"], job.id)

        # Verify properties reset after completion
        self.assertFalse(self.worker.is_processing)
        self.assertIsNone(self.worker.current_job_id)

    async def test_worker_continues_after_error(self):
        """Test worker continues processing after a job fails."""
        # Create 2 jobs
        job1 = Job(audio_path="/test/audio1.mp3", diarize=False)
        await self.repo.create(job1)
        await asyncio.sleep(0.01)

        job2 = Job(audio_path="/test/audio2.mp3", diarize=False)
        await self.repo.create(job2)

        # Mock: first job fails, second succeeds
        call_count = [0]

        def mock_transcription(audio_path, model_size, diarize, min_speakers, max_speakers, is_retry):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First job failed")
            return {
                "text": "Second job success",
                "language": "en",
                "diarization_succeeded": False,
                "speaker_count": None
            }

        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            side_effect=mock_transcription
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for both jobs to process
            await asyncio.sleep(0.5)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify first job failed
        job1_retrieved = await self.repo.get(job1.id)
        self.assertEqual(job1_retrieved.status, JobStatus.ERROR)
        self.assertIn("First job failed", job1_retrieved.error_message)

        # Verify second job succeeded
        job2_retrieved = await self.repo.get(job2.id)
        self.assertEqual(job2_retrieved.status, JobStatus.COMPLETED)
        self.assertEqual(job2_retrieved.result_text, "Second job success")

    async def test_multiple_jobs_queued(self):
        """Test worker processes multiple queued jobs sequentially."""
        # Create 3 jobs
        jobs = []
        for i in range(3):
            job = Job(audio_path=f"/test/audio{i}.mp3", diarize=False)
            await self.repo.create(job)
            jobs.append(job)
            await asyncio.sleep(0.01)

        # Mock transcription
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            return_value={
                "text": "Transcribed",
                "language": "en",
                "diarization_succeeded": False,
                "speaker_count": None
            }
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for all jobs to process
            await asyncio.sleep(0.5)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify all jobs completed
        for job in jobs:
            retrieved = await self.repo.get(job.id)
            self.assertEqual(retrieved.status, JobStatus.COMPLETED)
            self.assertEqual(retrieved.result_text, "Transcribed")
            self.assertIsNotNone(retrieved.started_at)
            self.assertIsNotNone(retrieved.completed_at)

    async def test_worker_processes_downloading_job(self):
        """Test worker processes DOWNLOADING job through download and transcription."""
        from pathlib import Path

        # Create a job with DOWNLOADING status
        job = Job(
            audio_path="https://www.youtube.com/watch?v=test",
            model_size="base",
            status=JobStatus.DOWNLOADING,
            download_progress=0,
            diarize=False
        )
        await self.repo.create(job)

        # Mock download_youtube_audio to return a path
        mock_download_path = Path("/tmp/downloaded_audio.m4a")

        with patch('cesar.api.worker.download_youtube_audio', return_value=mock_download_path):
            with patch.object(
                self.worker, '_run_transcription_with_orchestrator',
                return_value={
                    "text": "YouTube transcription",
                    "language": "en",
                    "diarization_succeeded": False,
                    "speaker_count": None
                }
            ):
                # Start worker task
                worker_task = asyncio.create_task(self.worker.run())

                # Wait for processing
                await asyncio.sleep(0.3)

                # Shutdown worker
                await self.worker.shutdown()
                await worker_task

        # Verify job transitions: DOWNLOADING -> PROCESSING -> COMPLETED
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.COMPLETED)
        self.assertEqual(retrieved.download_progress, 100)
        self.assertEqual(retrieved.audio_path, str(mock_download_path))
        self.assertEqual(retrieved.result_text, "YouTube transcription")
        self.assertIsNotNone(retrieved.started_at)
        self.assertIsNotNone(retrieved.completed_at)

    async def test_worker_downloading_error_sets_error_status(self):
        """Test worker sets ERROR status when YouTube download fails."""
        from cesar.youtube_handler import YouTubeDownloadError

        # Create a job with DOWNLOADING status
        job = Job(
            audio_path="https://www.youtube.com/watch?v=invalid",
            model_size="base",
            status=JobStatus.DOWNLOADING,
            download_progress=0,
            diarize=False
        )
        await self.repo.create(job)

        # Mock download to fail
        with patch('cesar.api.worker.download_youtube_audio', side_effect=YouTubeDownloadError("Video unavailable")):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job marked as ERROR with message
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.ERROR)
        self.assertIn("Video unavailable", retrieved.error_message)
        self.assertIsNotNone(retrieved.completed_at)
        self.assertIsNone(retrieved.result_text)

    async def test_worker_queued_job_unchanged(self):
        """Test existing QUEUED job behavior still works (regression test)."""
        # Create a regular QUEUED job
        job = Job(audio_path="/test/audio.mp3", model_size="base", diarize=False)
        await self.repo.create(job)

        # Verify initial status
        self.assertEqual(job.status, JobStatus.QUEUED)
        self.assertIsNone(job.download_progress)

        # Mock transcription
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            return_value={
                "text": "Regular transcription",
                "language": "en",
                "diarization_succeeded": False,
                "speaker_count": None
            }
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job completed normally
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.COMPLETED)
        self.assertEqual(retrieved.result_text, "Regular transcription")
        self.assertIsNone(retrieved.download_progress)  # Should remain None for regular jobs
        self.assertIsNotNone(retrieved.started_at)
        self.assertIsNotNone(retrieved.completed_at)


class TestBackgroundWorkerTranscription(unittest.TestCase):
    """Test cases for _run_transcription method."""

    @patch('cesar.api.worker.AudioTranscriber')
    def test_run_transcription_success(self, mock_transcriber_class):
        """Test _run_transcription creates temp file and calls transcriber."""
        # Mock transcriber instance
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.return_value = {
            "language": "en",
            "audio_duration": 10.0
        }
        mock_transcriber_class.return_value = mock_transcriber

        # Create worker (no need for real repo)
        worker = BackgroundWorker(repository=MagicMock(), poll_interval=1.0)

        # Mock file operations
        with patch('builtins.open', unittest.mock.mock_open(read_data='Test transcription')):
            with patch('tempfile.mkstemp', return_value=(1, '/tmp/test.txt')):
                with patch('os.close'):
                    with patch('pathlib.Path.unlink'):
                        result = worker._run_transcription('/test/audio.mp3', 'base')

        # Verify result
        self.assertEqual(result["text"], "Test transcription")
        self.assertEqual(result["language"], "en")

        # Verify transcriber was called
        mock_transcriber_class.assert_called_once_with(model_size='base')
        mock_transcriber.transcribe_file.assert_called_once()

    @patch('cesar.api.worker.AudioTranscriber')
    def test_run_transcription_cleans_up_temp_file(self, mock_transcriber_class):
        """Test _run_transcription cleans up temp file even on error."""
        # Mock transcriber to raise exception
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = RuntimeError("Transcription failed")
        mock_transcriber_class.return_value = mock_transcriber

        worker = BackgroundWorker(repository=MagicMock(), poll_interval=1.0)

        # Mock file operations
        mock_unlink = MagicMock()
        with patch('tempfile.mkstemp', return_value=(1, '/tmp/test.txt')):
            with patch('os.close'):
                with patch('pathlib.Path.unlink', mock_unlink):
                    with self.assertRaises(RuntimeError):
                        worker._run_transcription('/test/audio.mp3', 'base')

        # Verify temp file was cleaned up despite error
        mock_unlink.assert_called_once()


class TestBackgroundWorkerDiarization(unittest.IsolatedAsyncioTestCase):
    """Test cases for worker diarization functionality."""

    async def asyncSetUp(self):
        """Set up fresh repository and worker for each test."""
        self.repo = JobRepository(":memory:")
        await self.repo.connect()
        self.worker = BackgroundWorker(self.repo, poll_interval=0.1)

    async def asyncTearDown(self):
        """Close repository connection after each test."""
        await self.repo.close()

    async def test_diarize_disabled_completes_normally(self):
        """Test job with diarize=False completes with COMPLETED status."""
        # Create job with diarization disabled
        job = Job(audio_path="/test/audio.mp3", model_size="base", diarize=False)
        await self.repo.create(job)

        # Mock _run_transcription_with_orchestrator to return simple result
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            return_value={
                "text": "Hello world",
                "language": "en",
                "diarization_succeeded": False,
                "speaker_count": None
            }
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job completed
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.COMPLETED)
        self.assertEqual(retrieved.result_text, "Hello world")
        self.assertEqual(retrieved.diarized, False)
        self.assertIsNone(retrieved.speaker_count)

    async def test_diarize_enabled_no_hf_token_sets_partial(self):
        """Test job with diarize=True but no HF token sets PARTIAL status."""
        # Create job with diarization enabled
        job = Job(audio_path="/test/audio.mp3", model_size="base", diarize=True)
        await self.repo.create(job)

        # Mock _run_transcription_with_orchestrator to return hf_token_required error
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            return_value={
                "text": "Transcribed without speakers",
                "language": "en",
                "diarization_succeeded": False,
                "diarization_error_code": "hf_token_required",
                "diarization_error": "HuggingFace token required for speaker diarization."
            }
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job is PARTIAL with transcription but diarization error
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.PARTIAL)
        self.assertEqual(retrieved.result_text, "Transcribed without speakers")
        self.assertEqual(retrieved.diarization_error_code, "hf_token_required")
        self.assertIsNotNone(retrieved.diarization_error)
        self.assertEqual(retrieved.diarized, False)

    async def test_diarize_enabled_success(self):
        """Test job with diarize=True and successful diarization."""
        # Create job with diarization enabled and speaker range
        job = Job(
            audio_path="/test/audio.mp3",
            model_size="base",
            diarize=True,
            min_speakers=2,
            max_speakers=4
        )
        await self.repo.create(job)

        # Mock _run_transcription_with_orchestrator to return success
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            return_value={
                "text": "### Speaker 1\n\nHello\n\n### Speaker 2\n\nHi there",
                "language": "unknown",
                "diarization_succeeded": True,
                "speaker_count": 2
            }
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job is COMPLETED with diarization
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.COMPLETED)
        self.assertIn("Speaker 1", retrieved.result_text)
        self.assertEqual(retrieved.diarized, True)
        self.assertEqual(retrieved.speaker_count, 2)

    async def test_diarize_fallback_sets_partial(self):
        """Test job with diarization failure (orchestrator returns diarization_succeeded=False)."""
        # Create job with diarization enabled
        job = Job(audio_path="/test/audio.mp3", model_size="base", diarize=True)
        await self.repo.create(job)

        # Mock _run_transcription_with_orchestrator to return fallback result
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            return_value={
                "text": "# Transcript\n\n(Speaker detection unavailable)\n\nHello world",
                "language": "en",
                "diarization_succeeded": False,
                "speaker_count": None
            }
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job is PARTIAL
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.PARTIAL)
        self.assertIn("Hello world", retrieved.result_text)
        self.assertEqual(retrieved.diarized, False)
        self.assertEqual(retrieved.diarization_error_code, "diarization_failed")

    async def test_diarize_authentication_error_sets_partial(self):
        """Test job with invalid HF token sets PARTIAL with hf_token_invalid."""
        # Create job with diarization enabled
        job = Job(audio_path="/test/audio.mp3", model_size="base", diarize=True)
        await self.repo.create(job)

        # Mock _run_transcription_with_orchestrator to return auth error
        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            return_value={
                "text": "Transcribed without speakers",
                "language": "en",
                "diarization_succeeded": False,
                "diarization_error_code": "hf_token_invalid",
                "diarization_error": "HuggingFace authentication failed."
            }
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify job is PARTIAL with auth error code
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.PARTIAL)
        self.assertEqual(retrieved.result_text, "Transcribed without speakers")
        self.assertEqual(retrieved.diarization_error_code, "hf_token_invalid")
        self.assertEqual(retrieved.diarized, False)

    async def test_retry_job_detection(self):
        """Test retry scenario where job has result_text but diarization_error."""
        # Create job that simulates a partial failure (has result but error)
        job = Job(
            audio_path="/test/audio.mp3",
            model_size="base",
            diarize=True,
            status=JobStatus.QUEUED,
            result_text="Previous transcription",
            diarization_error="HF token was missing",
            diarization_error_code="hf_token_required"
        )
        await self.repo.create(job)

        # Track is_retry parameter
        received_params = {}

        def mock_transcription_with_orchestrator(
            audio_path, model_size, diarize, min_speakers, max_speakers, is_retry
        ):
            received_params['is_retry'] = is_retry
            return {
                "text": "### Speaker 1\n\nRetried with diarization",
                "language": "unknown",
                "diarization_succeeded": True,
                "speaker_count": 1
            }

        with patch.object(
            self.worker, '_run_transcription_with_orchestrator',
            side_effect=mock_transcription_with_orchestrator
        ):
            # Start worker task
            worker_task = asyncio.create_task(self.worker.run())

            # Wait for processing
            await asyncio.sleep(0.3)

            # Shutdown worker
            await self.worker.shutdown()
            await worker_task

        # Verify is_retry was True
        self.assertTrue(received_params.get('is_retry', False))

        # Verify job is now COMPLETED with diarization
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.COMPLETED)
        self.assertIn("Retried with diarization", retrieved.result_text)
        self.assertEqual(retrieved.diarized, True)


class TestBackgroundWorkerHFTokenResolution(unittest.TestCase):
    """Test cases for _get_hf_token method."""

    def test_hf_token_from_config(self):
        """Test HF token resolution from config."""
        from cesar.config import CesarConfig

        config = CesarConfig(hf_token="token_from_config")
        worker = BackgroundWorker(repository=MagicMock(), config=config)

        self.assertEqual(worker._get_hf_token(), "token_from_config")

    def test_hf_token_from_env(self):
        """Test HF token resolution from environment variable."""
        worker = BackgroundWorker(repository=MagicMock(), config=None)

        with patch.dict('os.environ', {'HF_TOKEN': 'token_from_env'}):
            self.assertEqual(worker._get_hf_token(), "token_from_env")

    def test_hf_token_from_cache(self):
        """Test HF token resolution from cached file."""
        worker = BackgroundWorker(repository=MagicMock(), config=None)

        # Mock environment to have no HF_TOKEN
        with patch.dict('os.environ', {}, clear=True):
            # Mock Path.exists to return True for token file
            with patch('pathlib.Path.exists', return_value=True):
                # Mock read_text to return cached token
                with patch('pathlib.Path.read_text', return_value='token_from_cache\n'):
                    self.assertEqual(worker._get_hf_token(), "token_from_cache")

    def test_hf_token_none_when_not_found(self):
        """Test HF token is None when no source available."""
        worker = BackgroundWorker(repository=MagicMock(), config=None)

        # Mock environment to have no HF_TOKEN
        with patch.dict('os.environ', {}, clear=True):
            # Mock Path.exists to return False for token file
            with patch('pathlib.Path.exists', return_value=False):
                self.assertIsNone(worker._get_hf_token())

    def test_hf_token_config_priority(self):
        """Test config token takes priority over env and cache."""
        from cesar.config import CesarConfig

        config = CesarConfig(hf_token="token_from_config")
        worker = BackgroundWorker(repository=MagicMock(), config=config)

        with patch.dict('os.environ', {'HF_TOKEN': 'token_from_env'}):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.read_text', return_value='token_from_cache'):
                    # Config should take priority
                    self.assertEqual(worker._get_hf_token(), "token_from_config")


if __name__ == "__main__":
    unittest.main()
