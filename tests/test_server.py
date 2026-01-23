"""
Tests for FastAPI server and health endpoint.

Uses FastAPI TestClient with mocked worker and repository
to avoid actual database/transcription operations.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestHealthEndpoint(unittest.TestCase):
    """Tests for GET /health endpoint and OpenAPI documentation."""

    def setUp(self):
        """Set up test client with mocked dependencies."""
        # Create mocks for repository and worker
        self.mock_repo = MagicMock()
        self.mock_repo.connect = AsyncMock()
        self.mock_repo.close = AsyncMock()

        self.mock_worker = MagicMock()
        self.mock_worker.run = AsyncMock()
        self.mock_worker.shutdown = AsyncMock()

        # Mock the worker task
        self.mock_worker_task = MagicMock()
        self.mock_worker_task.done.return_value = False

        # Patch the imports in server module
        self.repo_patcher = patch("cesar.api.server.JobRepository")
        self.worker_patcher = patch("cesar.api.server.BackgroundWorker")

        self.mock_repo_class = self.repo_patcher.start()
        self.mock_worker_class = self.worker_patcher.start()

        self.mock_repo_class.return_value = self.mock_repo
        self.mock_worker_class.return_value = self.mock_worker

        # Import app after patching
        from cesar.api.server import app

        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        """Stop all patches."""
        self.repo_patcher.stop()
        self.worker_patcher.stop()

    def test_health_returns_200(self):
        """GET /health should return 200 status code."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_health_response_format(self):
        """GET /health response should have 'status' and 'worker' keys."""
        response = self.client.get("/health")
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("worker", data)

    def test_health_status_is_healthy(self):
        """GET /health status should be 'healthy'."""
        response = self.client.get("/health")
        data = response.json()
        self.assertEqual(data["status"], "healthy")

    def test_health_worker_status(self):
        """GET /health worker should be 'running' or 'stopped'."""
        response = self.client.get("/health")
        data = response.json()
        self.assertIn(data["worker"], ["running", "stopped"])

    def test_openapi_docs_available(self):
        """GET /docs should return 200 (Swagger UI)."""
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)

    def test_openapi_json_available(self):
        """GET /openapi.json should return 200 with OpenAPI schema."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Verify it's a valid OpenAPI schema
        self.assertIn("openapi", data)
        self.assertIn("info", data)
        self.assertEqual(data["info"]["title"], "Cesar Transcription API")
        self.assertEqual(data["info"]["version"], "2.0.0")


class TestAppConfiguration(unittest.TestCase):
    """Tests for FastAPI app configuration."""

    def test_app_title(self):
        """App should have correct title."""
        from cesar.api.server import app

        self.assertEqual(app.title, "Cesar Transcription API")

    def test_app_version(self):
        """App should have correct version."""
        from cesar.api.server import app

        self.assertEqual(app.version, "2.0.0")

    def test_app_description(self):
        """App should have correct description."""
        from cesar.api.server import app

        self.assertEqual(app.description, "Offline audio transcription with async job queue")


if __name__ == "__main__":
    unittest.main()
