"""
Integration tests for JobRepository.

Tests async CRUD operations, state transitions, and persistence.
"""
import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from cesar.api import Job, JobRepository, JobStatus


class TestJobRepository(unittest.IsolatedAsyncioTestCase):
    """Test cases for JobRepository using in-memory database."""

    async def asyncSetUp(self):
        """Set up fresh repository for each test."""
        self.repo = JobRepository(":memory:")
        await self.repo.connect()

    async def asyncTearDown(self):
        """Close repository connection after each test."""
        await self.repo.close()

    async def test_create_and_get(self):
        """Test creating a job and retrieving it by ID."""
        job = Job(audio_path="/test/audio.mp3", model_size="small")

        # Create
        created = await self.repo.create(job)
        self.assertEqual(created.id, job.id)
        self.assertEqual(created.audio_path, "/test/audio.mp3")
        self.assertEqual(created.model_size, "small")
        self.assertEqual(created.status, JobStatus.QUEUED)

        # Get
        retrieved = await self.repo.get(job.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, job.id)
        self.assertEqual(retrieved.audio_path, "/test/audio.mp3")
        self.assertEqual(retrieved.model_size, "small")
        self.assertEqual(retrieved.status, JobStatus.QUEUED)
        self.assertIsInstance(retrieved.created_at, datetime)

    async def test_create_job_fields_preserved(self):
        """Test all job fields are preserved through create/get cycle."""
        now = datetime.utcnow()
        job = Job(
            audio_path="/path/to/file.wav",
            model_size="large",
            status=JobStatus.QUEUED,
        )

        await self.repo.create(job)
        retrieved = await self.repo.get(job.id)

        self.assertEqual(retrieved.id, job.id)
        self.assertEqual(retrieved.status, JobStatus.QUEUED)
        self.assertEqual(retrieved.audio_path, "/path/to/file.wav")
        self.assertEqual(retrieved.model_size, "large")
        self.assertIsNone(retrieved.started_at)
        self.assertIsNone(retrieved.completed_at)
        self.assertIsNone(retrieved.result_text)
        self.assertIsNone(retrieved.detected_language)
        self.assertIsNone(retrieved.error_message)

    async def test_update_to_processing(self):
        """Test state transition from queued to processing."""
        job = Job(audio_path="/test/audio.mp3")
        await self.repo.create(job)

        # Transition to processing
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        await self.repo.update(job)

        # Verify
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.PROCESSING)
        self.assertIsNotNone(retrieved.started_at)
        self.assertIsInstance(retrieved.started_at, datetime)

    async def test_update_to_completed(self):
        """Test state transition from processing to completed with results."""
        job = Job(audio_path="/test/audio.mp3")
        await self.repo.create(job)

        # Transition to processing
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        await self.repo.update(job)

        # Transition to completed
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.result_text = "Hello world, this is the transcription."
        job.detected_language = "en"
        await self.repo.update(job)

        # Verify
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.COMPLETED)
        self.assertIsNotNone(retrieved.started_at)
        self.assertIsNotNone(retrieved.completed_at)
        self.assertEqual(retrieved.result_text, "Hello world, this is the transcription.")
        self.assertEqual(retrieved.detected_language, "en")
        self.assertIsNone(retrieved.error_message)

    async def test_update_to_error(self):
        """Test state transition to error with error message."""
        job = Job(audio_path="/test/audio.mp3")
        await self.repo.create(job)

        # Transition directly to error
        job.status = JobStatus.ERROR
        job.completed_at = datetime.utcnow()
        job.error_message = "Failed to process audio: file corrupted"
        await self.repo.update(job)

        # Verify
        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.status, JobStatus.ERROR)
        self.assertEqual(retrieved.error_message, "Failed to process audio: file corrupted")
        self.assertIsNotNone(retrieved.completed_at)
        self.assertIsNone(retrieved.result_text)

    async def test_list_all_empty(self):
        """Test list_all returns empty list when no jobs exist."""
        jobs = await self.repo.list_all()
        self.assertEqual(jobs, [])

    async def test_list_all_multiple_jobs(self):
        """Test list_all returns all jobs ordered by created_at DESC."""
        # Create 3 jobs with small delays to ensure different timestamps
        job1 = Job(audio_path="/test/audio1.mp3")
        await self.repo.create(job1)
        await asyncio.sleep(0.01)

        job2 = Job(audio_path="/test/audio2.mp3")
        await self.repo.create(job2)
        await asyncio.sleep(0.01)

        job3 = Job(audio_path="/test/audio3.mp3")
        await self.repo.create(job3)

        # List all
        jobs = await self.repo.list_all()
        self.assertEqual(len(jobs), 3)

        # Verify order (newest first)
        self.assertEqual(jobs[0].id, job3.id)
        self.assertEqual(jobs[1].id, job2.id)
        self.assertEqual(jobs[2].id, job1.id)

    async def test_get_next_queued_empty(self):
        """Test get_next_queued returns None when no queued jobs."""
        result = await self.repo.get_next_queued()
        self.assertIsNone(result)

    async def test_get_next_queued_returns_oldest(self):
        """Test get_next_queued returns oldest queued job."""
        # Create 3 jobs in order
        job1 = Job(audio_path="/test/audio1.mp3")
        await self.repo.create(job1)
        await asyncio.sleep(0.01)

        job2 = Job(audio_path="/test/audio2.mp3")
        await self.repo.create(job2)
        await asyncio.sleep(0.01)

        job3 = Job(audio_path="/test/audio3.mp3")
        await self.repo.create(job3)

        # Get next queued (should be oldest = job1)
        next_job = await self.repo.get_next_queued()
        self.assertIsNotNone(next_job)
        self.assertEqual(next_job.id, job1.id)

    async def test_get_next_queued_skips_processing(self):
        """Test get_next_queued skips jobs that are processing."""
        # Create 3 jobs
        job1 = Job(audio_path="/test/audio1.mp3")
        await self.repo.create(job1)
        await asyncio.sleep(0.01)

        job2 = Job(audio_path="/test/audio2.mp3")
        await self.repo.create(job2)
        await asyncio.sleep(0.01)

        job3 = Job(audio_path="/test/audio3.mp3")
        await self.repo.create(job3)

        # Mark job1 as processing
        job1.status = JobStatus.PROCESSING
        job1.started_at = datetime.utcnow()
        await self.repo.update(job1)

        # Get next queued (should be job2 now)
        next_job = await self.repo.get_next_queued()
        self.assertIsNotNone(next_job)
        self.assertEqual(next_job.id, job2.id)

    async def test_get_not_found(self):
        """Test get returns None for non-existent job ID."""
        result = await self.repo.get("non-existent-id-12345")
        self.assertIsNone(result)

    async def test_timestamps_are_datetime_objects(self):
        """Test all timestamps are datetime objects after retrieval."""
        job = Job(audio_path="/test/audio.mp3")
        await self.repo.create(job)

        # Verify created_at
        retrieved = await self.repo.get(job.id)
        self.assertIsInstance(retrieved.created_at, datetime)
        self.assertIsNotNone(retrieved.created_at)

        # Add started_at and completed_at
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        await self.repo.update(job)

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        await self.repo.update(job)

        # Verify all timestamps
        retrieved = await self.repo.get(job.id)
        self.assertIsInstance(retrieved.created_at, datetime)
        self.assertIsInstance(retrieved.started_at, datetime)
        self.assertIsInstance(retrieved.completed_at, datetime)

    async def test_create_job_with_download_progress(self):
        """Test creating a job with download_progress field."""
        job = Job(
            audio_path="https://youtube.com/watch?v=test",
            model_size="base",
            status=JobStatus.DOWNLOADING,
            download_progress=50
        )

        await self.repo.create(job)
        retrieved = await self.repo.get(job.id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.download_progress, 50)
        self.assertEqual(retrieved.status, JobStatus.DOWNLOADING)

    async def test_update_job_download_progress(self):
        """Test updating download_progress field."""
        job = Job(
            audio_path="https://youtube.com/watch?v=test",
            status=JobStatus.DOWNLOADING,
            download_progress=0
        )
        await self.repo.create(job)

        # Update progress to 100
        job.download_progress = 100
        await self.repo.update(job)

        retrieved = await self.repo.get(job.id)
        self.assertEqual(retrieved.download_progress, 100)

    async def test_get_next_queued_returns_downloading(self):
        """Test get_next_queued returns DOWNLOADING jobs."""
        # Create a DOWNLOADING job
        job = Job(
            audio_path="https://youtube.com/watch?v=test",
            status=JobStatus.DOWNLOADING,
            download_progress=0
        )
        await self.repo.create(job)

        # get_next_queued should return it
        next_job = await self.repo.get_next_queued()
        self.assertIsNotNone(next_job)
        self.assertEqual(next_job.id, job.id)
        self.assertEqual(next_job.status, JobStatus.DOWNLOADING)

    async def test_get_job_returns_download_progress(self):
        """Test retrieving job returns correct download_progress value."""
        job = Job(
            audio_path="https://youtube.com/watch?v=test",
            status=JobStatus.DOWNLOADING,
            download_progress=75
        )
        await self.repo.create(job)

        retrieved = await self.repo.get(job.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.download_progress, 75)


class TestJobRepositoryPersistence(unittest.IsolatedAsyncioTestCase):
    """Test cases for JobRepository file-based persistence."""

    async def test_persistence_across_connections(self):
        """Test jobs persist across connection close/reopen."""
        # Create temp file for database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            # First connection: create job
            repo1 = JobRepository(db_path)
            await repo1.connect()

            job = Job(audio_path="/test/audio.mp3", model_size="medium")
            await repo1.create(job)
            job_id = job.id

            await repo1.close()

            # Second connection: verify job exists
            repo2 = JobRepository(db_path)
            await repo2.connect()

            retrieved = await repo2.get(job_id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.id, job_id)
            self.assertEqual(retrieved.audio_path, "/test/audio.mp3")
            self.assertEqual(retrieved.model_size, "medium")
            self.assertEqual(retrieved.status, JobStatus.QUEUED)
            self.assertIsInstance(retrieved.created_at, datetime)

            await repo2.close()
        finally:
            # Cleanup
            db_path.unlink(missing_ok=True)
            # Also clean up WAL files
            wal_path = Path(str(db_path) + "-wal")
            shm_path = Path(str(db_path) + "-shm")
            wal_path.unlink(missing_ok=True)
            shm_path.unlink(missing_ok=True)

    async def test_persistence_with_state_transitions(self):
        """Test state transitions persist across connections."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            # First connection: create job and transition to completed
            repo1 = JobRepository(db_path)
            await repo1.connect()

            job = Job(audio_path="/test/audio.mp3")
            await repo1.create(job)
            job_id = job.id

            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()
            await repo1.update(job)

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result_text = "Persisted transcription"
            job.detected_language = "es"
            await repo1.update(job)

            await repo1.close()

            # Second connection: verify everything persisted
            repo2 = JobRepository(db_path)
            await repo2.connect()

            retrieved = await repo2.get(job_id)
            self.assertEqual(retrieved.status, JobStatus.COMPLETED)
            self.assertEqual(retrieved.result_text, "Persisted transcription")
            self.assertEqual(retrieved.detected_language, "es")
            self.assertIsInstance(retrieved.started_at, datetime)
            self.assertIsInstance(retrieved.completed_at, datetime)
            self.assertIsInstance(retrieved.created_at, datetime)

            await repo2.close()
        finally:
            db_path.unlink(missing_ok=True)
            Path(str(db_path) + "-wal").unlink(missing_ok=True)
            Path(str(db_path) + "-shm").unlink(missing_ok=True)

    async def test_persistence_with_error_state(self):
        """Test error state and message persist."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        try:
            # First connection: create job and mark as error
            repo1 = JobRepository(db_path)
            await repo1.connect()

            job = Job(audio_path="/test/audio.mp3")
            await repo1.create(job)
            job_id = job.id

            job.status = JobStatus.ERROR
            job.completed_at = datetime.utcnow()
            job.error_message = "Audio file not found"
            await repo1.update(job)

            await repo1.close()

            # Second connection: verify error state persisted
            repo2 = JobRepository(db_path)
            await repo2.connect()

            retrieved = await repo2.get(job_id)
            self.assertEqual(retrieved.status, JobStatus.ERROR)
            self.assertEqual(retrieved.error_message, "Audio file not found")
            self.assertIsInstance(retrieved.completed_at, datetime)

            await repo2.close()
        finally:
            db_path.unlink(missing_ok=True)
            Path(str(db_path) + "-wal").unlink(missing_ok=True)
            Path(str(db_path) + "-shm").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
