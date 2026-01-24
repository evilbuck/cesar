"""
Unit tests for cesar serve command
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from cesar.api.models import Job, JobStatus
from cesar.api.repository import JobRepository
from cesar.cli import cli


class TestServeCommand(unittest.TestCase):
    """Test cesar serve CLI command"""

    def setUp(self):
        self.runner = CliRunner()

    def test_serve_help_shows_options(self):
        """Test that serve --help shows all available options"""
        result = self.runner.invoke(cli, ['serve', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--port', result.output)
        self.assertIn('--host', result.output)
        self.assertIn('--reload', result.output)
        self.assertIn('--workers', result.output)

    def test_serve_help_shows_defaults(self):
        """Test that serve --help shows default values"""
        result = self.runner.invoke(cli, ['serve', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('-p, --port', result.output)
        self.assertIn('[default: 5000]', result.output)
        self.assertIn('-h, --host', result.output)
        self.assertIn('[default: 127.0.0.1]', result.output)
        self.assertIn('[default: 1]', result.output)  # workers default

    @patch('cesar.cli.uvicorn.run')
    def test_serve_calls_uvicorn_with_defaults(self, mock_run):
        """Test that serve command calls uvicorn.run with default arguments"""
        result = self.runner.invoke(cli, ['serve'])
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs['host'], '127.0.0.1')
        self.assertEqual(call_kwargs['port'], 5000)
        self.assertEqual(call_kwargs['workers'], 1)
        self.assertEqual(call_kwargs['reload'], False)

    @patch('cesar.cli.uvicorn.run')
    def test_serve_respects_port_flag(self, mock_run):
        """Test that serve --port sets custom port"""
        result = self.runner.invoke(cli, ['serve', '--port', '8080'])
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs['port'], 8080)

    @patch('cesar.cli.uvicorn.run')
    def test_serve_respects_host_flag(self, mock_run):
        """Test that serve --host sets custom host"""
        result = self.runner.invoke(cli, ['serve', '--host', '0.0.0.0'])
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs['host'], '0.0.0.0')

    @patch('cesar.cli.uvicorn.run')
    def test_serve_respects_reload_flag(self, mock_run):
        """Test that serve --reload enables auto-reload"""
        result = self.runner.invoke(cli, ['serve', '--reload'])
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs['reload'], True)

    @patch('cesar.cli.uvicorn.run')
    def test_serve_respects_workers_flag(self, mock_run):
        """Test that serve --workers sets worker count"""
        result = self.runner.invoke(cli, ['serve', '--workers', '4'])
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs['workers'], 4)

    @patch('cesar.cli.uvicorn.run')
    def test_serve_uses_import_string(self, mock_run):
        """Test that serve uses import string (not app instance) for reload support"""
        result = self.runner.invoke(cli, ['serve'])
        # First positional arg should be the import string
        call_args = mock_run.call_args.args
        self.assertEqual(call_args[0], "cesar.api.server:app")

    @patch('cesar.cli.uvicorn.run')
    def test_serve_sets_graceful_shutdown(self, mock_run):
        """Test that serve configures graceful shutdown timeout"""
        result = self.runner.invoke(cli, ['serve'])
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs['timeout_graceful_shutdown'], 30)


class TestJobRecovery(unittest.TestCase):
    """Test job recovery on server startup"""

    def test_processing_job_requeued_on_startup(self):
        """Test that PROCESSING jobs are re-queued on server startup"""
        asyncio.run(self._test_recovery())

    async def _test_recovery(self):
        """Async test helper for job recovery"""
        from datetime import datetime

        # Create in-memory database
        repo = JobRepository(":memory:")
        await repo.connect()

        # Create job in PROCESSING state (simulates crash)
        # Set started_at to simulate that worker had started processing
        job = Job(
            audio_path="/tmp/test.mp3",
            status=JobStatus.PROCESSING,
            started_at=datetime.utcnow()
        )
        await repo.create(job)

        # Verify job is PROCESSING
        fetched = await repo.get(job.id)
        self.assertEqual(fetched.status, JobStatus.PROCESSING)
        self.assertIsNotNone(fetched.started_at)

        # Simulate the recovery logic from lifespan
        all_jobs = await repo.list_all()
        for j in all_jobs:
            if j.status == JobStatus.PROCESSING:
                j.status = JobStatus.QUEUED
                j.started_at = None
                await repo.update(j)

        # Verify job was re-queued
        recovered = await repo.get(job.id)
        self.assertEqual(recovered.status, JobStatus.QUEUED)
        self.assertIsNone(recovered.started_at)

        await repo.close()

    def test_non_processing_jobs_unchanged(self):
        """Test that non-PROCESSING jobs are not modified during recovery"""
        asyncio.run(self._test_non_processing_unchanged())

    async def _test_non_processing_unchanged(self):
        """Async test helper for non-processing jobs"""
        repo = JobRepository(":memory:")
        await repo.connect()

        # Create jobs in different states
        queued_job = Job(audio_path="/tmp/queued.mp3", status=JobStatus.QUEUED)
        completed_job = Job(audio_path="/tmp/completed.mp3", status=JobStatus.COMPLETED)
        error_job = Job(audio_path="/tmp/error.mp3", status=JobStatus.ERROR)

        await repo.create(queued_job)
        await repo.create(completed_job)
        await repo.create(error_job)

        # Simulate recovery logic
        all_jobs = await repo.list_all()
        for j in all_jobs:
            if j.status == JobStatus.PROCESSING:
                j.status = JobStatus.QUEUED
                j.started_at = None
                await repo.update(j)

        # Verify jobs unchanged
        fetched_queued = await repo.get(queued_job.id)
        fetched_completed = await repo.get(completed_job.id)
        fetched_error = await repo.get(error_job.id)

        self.assertEqual(fetched_queued.status, JobStatus.QUEUED)
        self.assertEqual(fetched_completed.status, JobStatus.COMPLETED)
        self.assertEqual(fetched_error.status, JobStatus.ERROR)

        await repo.close()


if __name__ == '__main__':
    unittest.main()
