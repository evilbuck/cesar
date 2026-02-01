"""
Tests for FastAPI server and health endpoint.

Uses FastAPI TestClient with mocked worker and repository
to avoid actual database/transcription operations.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from cesar.api.models import Job, JobStatus


class TestHealthEndpoint(unittest.TestCase):
    """Tests for GET /health endpoint and OpenAPI documentation."""

    def setUp(self):
        """Set up test client with mocked dependencies."""
        # Create mocks for repository and worker
        self.mock_repo = MagicMock()
        self.mock_repo.connect = AsyncMock()
        self.mock_repo.close = AsyncMock()
        self.mock_repo.get = AsyncMock()
        self.mock_repo.list_all = AsyncMock()
        self.mock_repo.create = AsyncMock()

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
        # Use context manager to ensure lifespan runs
        self._client_cm = TestClient(app)
        self.client = self._client_cm.__enter__()

    def tearDown(self):
        """Stop all patches and close client."""
        self._client_cm.__exit__(None, None, None)
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

    @patch('cesar.api.server.check_ffmpeg_available')
    def test_health_reports_youtube_available(self, mock_ffmpeg):
        """Test health endpoint reports YouTube available when FFmpeg present."""
        mock_ffmpeg.return_value = (True, "")

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("youtube", data)
        self.assertTrue(data["youtube"]["available"])
        self.assertIn("supported", data["youtube"]["message"].lower())

    @patch('cesar.api.server.check_ffmpeg_available')
    def test_health_reports_youtube_unavailable(self, mock_ffmpeg):
        """Test health endpoint reports YouTube unavailable when FFmpeg missing."""
        mock_ffmpeg.return_value = (False, "FFmpeg not found")

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("youtube", data)
        self.assertFalse(data["youtube"]["available"])
        self.assertIn("FFmpeg", data["youtube"]["message"])

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


class TestGetJobEndpoint(unittest.TestCase):
    """Tests for GET /jobs/{job_id} endpoint."""

    def setUp(self):
        """Set up test client with mocked dependencies."""
        # Create mocks for repository and worker
        self.mock_repo = MagicMock()
        self.mock_repo.connect = AsyncMock()
        self.mock_repo.close = AsyncMock()
        self.mock_repo.get = AsyncMock()
        self.mock_repo.list_all = AsyncMock()
        self.mock_repo.create = AsyncMock()

        self.mock_worker = MagicMock()
        self.mock_worker.run = AsyncMock()
        self.mock_worker.shutdown = AsyncMock()

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
        # Use context manager to ensure lifespan runs
        self._client_cm = TestClient(app)
        self.client = self._client_cm.__enter__()

    def tearDown(self):
        """Stop all patches and close client."""
        self._client_cm.__exit__(None, None, None)
        self.repo_patcher.stop()
        self.worker_patcher.stop()

    def test_get_job_not_found(self):
        """GET /jobs/{id} should return 404 for non-existent job ID."""
        self.mock_repo.get.return_value = None

        response = self.client.get("/jobs/nonexistent-id")

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("Job not found", data["detail"])

    def test_get_job_success(self):
        """GET /jobs/{id} should return job details when job exists."""
        test_job = Job(
            id="test-uuid-123",
            audio_path="/path/to/audio.mp3",
            model_size="base",
            status=JobStatus.QUEUED,
        )
        self.mock_repo.get.return_value = test_job

        response = self.client.get("/jobs/test-uuid-123")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "test-uuid-123")
        self.assertEqual(data["audio_path"], "/path/to/audio.mp3")
        self.assertEqual(data["status"], "queued")

    def test_get_job_response_format(self):
        """GET /jobs/{id} response should have all Job fields."""
        test_job = Job(
            id="test-uuid-456",
            audio_path="/path/to/audio.mp3",
            model_size="small",
            status=JobStatus.COMPLETED,
            result_text="Hello world",
            detected_language="en",
        )
        self.mock_repo.get.return_value = test_job

        response = self.client.get("/jobs/test-uuid-456")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Verify all expected fields are present
        self.assertIn("id", data)
        self.assertIn("status", data)
        self.assertIn("audio_path", data)
        self.assertIn("model_size", data)
        self.assertIn("created_at", data)
        self.assertIn("started_at", data)
        self.assertIn("completed_at", data)
        self.assertIn("result_text", data)
        self.assertIn("detected_language", data)
        self.assertIn("error_message", data)


class TestListJobsEndpoint(unittest.TestCase):
    """Tests for GET /jobs endpoint."""

    def setUp(self):
        """Set up test client with mocked dependencies."""
        # Create mocks for repository and worker
        self.mock_repo = MagicMock()
        self.mock_repo.connect = AsyncMock()
        self.mock_repo.close = AsyncMock()
        self.mock_repo.get = AsyncMock()
        self.mock_repo.list_all = AsyncMock()
        self.mock_repo.create = AsyncMock()

        self.mock_worker = MagicMock()
        self.mock_worker.run = AsyncMock()
        self.mock_worker.shutdown = AsyncMock()

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
        # Use context manager to ensure lifespan runs
        self._client_cm = TestClient(app)
        self.client = self._client_cm.__enter__()

    def tearDown(self):
        """Stop all patches and close client."""
        self._client_cm.__exit__(None, None, None)
        self.repo_patcher.stop()
        self.worker_patcher.stop()

    def test_list_jobs_empty(self):
        """GET /jobs should return empty list when no jobs exist."""
        self.mock_repo.list_all.return_value = []

        response = self.client.get("/jobs")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, [])

    def test_list_jobs_multiple(self):
        """GET /jobs should return all jobs."""
        jobs = [
            Job(id="job-1", audio_path="/path/1.mp3", status=JobStatus.QUEUED),
            Job(id="job-2", audio_path="/path/2.mp3", status=JobStatus.COMPLETED),
            Job(id="job-3", audio_path="/path/3.mp3", status=JobStatus.ERROR),
        ]
        self.mock_repo.list_all.return_value = jobs

        response = self.client.get("/jobs")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]["id"], "job-1")
        self.assertEqual(data[1]["id"], "job-2")
        self.assertEqual(data[2]["id"], "job-3")

    def test_list_jobs_filter_queued(self):
        """GET /jobs?status=queued should filter by status."""
        jobs = [
            Job(id="job-1", audio_path="/path/1.mp3", status=JobStatus.QUEUED),
            Job(id="job-2", audio_path="/path/2.mp3", status=JobStatus.COMPLETED),
            Job(id="job-3", audio_path="/path/3.mp3", status=JobStatus.QUEUED),
        ]
        self.mock_repo.list_all.return_value = jobs

        response = self.client.get("/jobs?status=queued")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertTrue(all(job["status"] == "queued" for job in data))

    def test_list_jobs_filter_completed(self):
        """GET /jobs?status=completed should filter by status."""
        jobs = [
            Job(id="job-1", audio_path="/path/1.mp3", status=JobStatus.QUEUED),
            Job(id="job-2", audio_path="/path/2.mp3", status=JobStatus.COMPLETED),
            Job(id="job-3", audio_path="/path/3.mp3", status=JobStatus.QUEUED),
        ]
        self.mock_repo.list_all.return_value = jobs

        response = self.client.get("/jobs?status=completed")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "job-2")
        self.assertEqual(data[0]["status"], "completed")

    def test_list_jobs_filter_invalid(self):
        """GET /jobs?status=invalid should return 400."""
        self.mock_repo.list_all.return_value = []

        response = self.client.get("/jobs?status=invalid")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("Invalid status", data["detail"])

    def test_list_jobs_filter_processing(self):
        """GET /jobs?status=processing should filter by status."""
        jobs = [
            Job(id="job-1", audio_path="/path/1.mp3", status=JobStatus.PROCESSING),
            Job(id="job-2", audio_path="/path/2.mp3", status=JobStatus.COMPLETED),
        ]
        self.mock_repo.list_all.return_value = jobs

        response = self.client.get("/jobs?status=processing")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "job-1")
        self.assertEqual(data[0]["status"], "processing")


class TestTranscribeFileUpload(unittest.TestCase):
    """Tests for POST /transcribe file upload endpoint."""

    def setUp(self):
        """Set up test client with mocked dependencies."""
        # Create mocks for repository and worker
        self.mock_repo = MagicMock()
        self.mock_repo.connect = AsyncMock()
        self.mock_repo.close = AsyncMock()
        self.mock_repo.get = AsyncMock()
        self.mock_repo.list_all = AsyncMock()
        self.mock_repo.create = AsyncMock()

        self.mock_worker = MagicMock()
        self.mock_worker.run = AsyncMock()
        self.mock_worker.shutdown = AsyncMock()

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
        # Use context manager to ensure lifespan runs
        self._client_cm = TestClient(app)
        self.client = self._client_cm.__enter__()

    def tearDown(self):
        """Stop all patches and close client."""
        self._client_cm.__exit__(None, None, None)
        self.repo_patcher.stop()
        self.worker_patcher.stop()

    def test_transcribe_file_success(self):
        """POST /transcribe with valid audio file returns 202 with job."""
        # Create small test file content
        file_content = b"fake audio content"
        files = {"file": ("test.mp3", file_content, "audio/mpeg")}

        response = self.client.post("/transcribe", files=files)

        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["model_size"], "base")
        # Verify repo.create was called
        self.mock_repo.create.assert_called_once()

    def test_transcribe_file_custom_model(self):
        """POST /transcribe with model=small passes model correctly."""
        file_content = b"fake audio content"
        files = {"file": ("test.mp3", file_content, "audio/mpeg")}
        data = {"model": "small"}

        response = self.client.post("/transcribe", files=files, data=data)

        self.assertEqual(response.status_code, 202)
        resp_data = response.json()
        self.assertEqual(resp_data["model_size"], "small")

    def test_transcribe_file_invalid_extension(self):
        """POST /transcribe with .exe file returns 400."""
        file_content = b"fake executable content"
        files = {"file": ("malware.exe", file_content, "application/octet-stream")}

        response = self.client.post("/transcribe", files=files)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("Invalid file type", data["detail"])

    def test_transcribe_file_too_large(self):
        """POST /transcribe with file exceeding 100MB returns 413."""
        # Patch MAX_FILE_SIZE for test (to avoid creating 100MB file)
        with patch("cesar.api.file_handler.MAX_FILE_SIZE", 100):
            # Create file content larger than our test limit
            file_content = b"x" * 200
            files = {"file": ("test.mp3", file_content, "audio/mpeg")}

            response = self.client.post("/transcribe", files=files)

            self.assertEqual(response.status_code, 413)
            data = response.json()
            self.assertIn("detail", data)
            self.assertIn("File too large", data["detail"])

    def test_transcribe_file_wav_extension(self):
        """POST /transcribe with .wav file is accepted."""
        file_content = b"fake wav content"
        files = {"file": ("test.wav", file_content, "audio/wav")}

        response = self.client.post("/transcribe", files=files)

        self.assertEqual(response.status_code, 202)

    def test_transcribe_file_m4a_extension(self):
        """POST /transcribe with .m4a file is accepted."""
        file_content = b"fake m4a content"
        files = {"file": ("test.m4a", file_content, "audio/m4a")}

        response = self.client.post("/transcribe", files=files)

        self.assertEqual(response.status_code, 202)

    def test_transcribe_file_response_has_job_fields(self):
        """POST /transcribe response should have all Job fields."""
        file_content = b"fake audio content"
        files = {"file": ("test.mp3", file_content, "audio/mpeg")}

        response = self.client.post("/transcribe", files=files)

        self.assertEqual(response.status_code, 202)
        data = response.json()
        # Verify all expected fields are present
        self.assertIn("id", data)
        self.assertIn("status", data)
        self.assertIn("audio_path", data)
        self.assertIn("model_size", data)
        self.assertIn("created_at", data)


class TestTranscribeURL(unittest.TestCase):
    """Tests for POST /transcribe/url endpoint."""

    def setUp(self):
        """Set up test client with mocked dependencies."""
        # Create mocks for repository and worker
        self.mock_repo = MagicMock()
        self.mock_repo.connect = AsyncMock()
        self.mock_repo.close = AsyncMock()
        self.mock_repo.get = AsyncMock()
        self.mock_repo.list_all = AsyncMock()
        self.mock_repo.create = AsyncMock()

        self.mock_worker = MagicMock()
        self.mock_worker.run = AsyncMock()
        self.mock_worker.shutdown = AsyncMock()

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
        # Use context manager to ensure lifespan runs
        self._client_cm = TestClient(app)
        self.client = self._client_cm.__enter__()

    def tearDown(self):
        """Stop all patches and close client."""
        self._client_cm.__exit__(None, None, None)
        self.repo_patcher.stop()
        self.worker_patcher.stop()

    @patch("cesar.api.file_handler.httpx.AsyncClient")
    def test_transcribe_url_success(self, mock_httpx_client):
        """POST /transcribe/url with valid URL returns 202 with job."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio content"
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_httpx_client.return_value = mock_client_instance

        response = self.client.post(
            "/transcribe/url",
            json={"url": "http://example.com/audio.mp3"},
        )

        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["model_size"], "base")
        # Verify repo.create was called
        self.mock_repo.create.assert_called_once()

    @patch("cesar.api.file_handler.httpx.AsyncClient")
    def test_transcribe_url_timeout(self, mock_httpx_client):
        """POST /transcribe/url with timeout returns 408."""
        import httpx

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        mock_httpx_client.return_value = mock_client_instance

        response = self.client.post(
            "/transcribe/url",
            json={"url": "http://example.com/audio.mp3"},
        )

        self.assertEqual(response.status_code, 408)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("timeout", data["detail"].lower())

    @patch("cesar.api.file_handler.httpx.AsyncClient")
    def test_transcribe_url_not_found(self, mock_httpx_client):
        """POST /transcribe/url with 404 from URL returns 400."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_httpx_client.return_value = mock_client_instance

        response = self.client.post(
            "/transcribe/url",
            json={"url": "http://example.com/nonexistent.mp3"},
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("Failed to download", data["detail"])

    def test_transcribe_url_invalid_extension(self):
        """POST /transcribe/url with .exe URL returns 400."""
        response = self.client.post(
            "/transcribe/url",
            json={"url": "http://example.com/malware.exe"},
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("Invalid file type", data["detail"])

    @patch("cesar.api.file_handler.httpx.AsyncClient")
    def test_transcribe_url_custom_model(self, mock_httpx_client):
        """POST /transcribe/url with model=large passes model correctly."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio content"
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_httpx_client.return_value = mock_client_instance

        response = self.client.post(
            "/transcribe/url",
            json={"url": "http://example.com/audio.wav", "model": "large"},
        )

        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["model_size"], "large")

    def test_transcribe_url_missing_url(self):
        """POST /transcribe/url without URL returns 422."""
        response = self.client.post(
            "/transcribe/url",
            json={"model": "base"},
        )

        self.assertEqual(response.status_code, 422)

    @patch("cesar.api.file_handler.httpx.AsyncClient")
    def test_transcribe_url_response_has_job_fields(self, mock_httpx_client):
        """POST /transcribe/url response should have all Job fields."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio content"
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_httpx_client.return_value = mock_client_instance

        response = self.client.post(
            "/transcribe/url",
            json={"url": "http://example.com/audio.mp3"},
        )

        self.assertEqual(response.status_code, 202)
        data = response.json()
        # Verify all expected fields are present
        self.assertIn("id", data)
        self.assertIn("status", data)
        self.assertIn("audio_path", data)
        self.assertIn("model_size", data)
        self.assertIn("created_at", data)

    def test_transcribe_url_youtube_creates_downloading_status(self):
        """POST /transcribe/url with YouTube URL returns job with status=DOWNLOADING."""
        response = self.client.post(
            "/transcribe/url",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["status"], "downloading")
        self.assertEqual(data["download_progress"], 0)
        self.assertEqual(data["audio_path"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        # Verify repo.create was called
        self.mock_repo.create.assert_called_once()

    @patch("cesar.api.file_handler.httpx.AsyncClient")
    def test_transcribe_url_regular_creates_queued_status(self, mock_httpx_client):
        """POST /transcribe/url with regular URL returns job with status=QUEUED."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio content"
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.get = AsyncMock(return_value=mock_response)

        mock_httpx_client.return_value = mock_client_instance

        response = self.client.post(
            "/transcribe/url",
            json={"url": "http://example.com/audio.mp3"},
        )

        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["status"], "queued")
        self.assertIsNone(data["download_progress"])


if __name__ == "__main__":
    unittest.main()
