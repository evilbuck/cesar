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
        # Create a job
        job = Job(audio_path="/test/audio.mp3", model_size="base")
        await self.repo.create(job)

        # Mock _run_transcription to return fake result
        with patch.object(
            self.worker, '_run_transcription',
            return_value={"text": "Hello world", "language": "en"}
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
        job = Job(audio_path="/nonexistent/audio.mp3", model_size="base")
        await self.repo.create(job)

        # Mock _run_transcription to raise exception
        with patch.object(
            self.worker, '_run_transcription',
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
        job1 = Job(audio_path="/test/audio1.mp3")
        await self.repo.create(job1)
        await asyncio.sleep(0.01)

        job2 = Job(audio_path="/test/audio2.mp3")
        await self.repo.create(job2)
        await asyncio.sleep(0.01)

        job3 = Job(audio_path="/test/audio3.mp3")
        await self.repo.create(job3)

        # Track processing order
        processed_order = []

        def mock_transcription(audio_path, model_size):
            processed_order.append(audio_path)
            return {"text": f"Transcription of {audio_path}", "language": "en"}

        # Mock _run_transcription
        with patch.object(
            self.worker, '_run_transcription',
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
        job = Job(audio_path="/test/audio.mp3")
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

        # Mock _run_transcription to sleep briefly
        def mock_transcription(audio_path, model_size):
            import time
            time.sleep(0.2)  # Simulate processing
            return {"text": "Hello", "language": "en"}

        with patch.object(
            self.worker, '_run_transcription',
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
        job1 = Job(audio_path="/test/audio1.mp3")
        await self.repo.create(job1)
        await asyncio.sleep(0.01)

        job2 = Job(audio_path="/test/audio2.mp3")
        await self.repo.create(job2)

        # Mock: first job fails, second succeeds
        call_count = [0]

        def mock_transcription(audio_path, model_size):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("First job failed")
            return {"text": "Second job success", "language": "en"}

        with patch.object(
            self.worker, '_run_transcription',
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
            job = Job(audio_path=f"/test/audio{i}.mp3")
            await self.repo.create(job)
            jobs.append(job)
            await asyncio.sleep(0.01)

        # Mock transcription
        with patch.object(
            self.worker, '_run_transcription',
            return_value={"text": "Transcribed", "language": "en"}
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


if __name__ == "__main__":
    unittest.main()
