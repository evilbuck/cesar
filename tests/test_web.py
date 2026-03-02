"""Tests for the web frontend serving."""
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient


class TestWebFrontend(unittest.TestCase):
    """Test that the web frontend is served correctly."""

    def setUp(self):
        """Set up test client with mocked lifespan."""
        # We need to create the app without the lifespan to avoid DB initialization
        from fastapi import FastAPI
        from cesar.api.server import WEB_DIR

        self.web_dir = WEB_DIR

    def test_web_directory_exists(self):
        """Web directory should exist."""
        self.assertTrue(self.web_dir.exists(), f"Web directory not found: {self.web_dir}")

    def test_index_html_exists(self):
        """index.html should exist in web directory."""
        index = self.web_dir / "index.html"
        self.assertTrue(index.exists(), f"index.html not found: {index}")

    def test_index_html_contains_tailwind(self):
        """index.html should include Tailwind CSS."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        self.assertIn("tailwindcss", content)

    def test_index_html_contains_youtube_input(self):
        """index.html should have YouTube URL input."""
        index = self.web_dir / "index.html"
        content = content = index.read_text()
        self.assertIn("youtube-url", content)
        self.assertIn("YouTube", content)

    def test_index_html_contains_file_upload(self):
        """index.html should have file upload functionality."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        self.assertIn("file-input", content)
        self.assertIn("upload", content.lower())

    def test_index_html_contains_model_selector(self):
        """index.html should have model size selector."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        self.assertIn("model-select", content)
        for model in ["tiny", "base", "small", "medium", "large"]:
            self.assertIn(model, content)

    def test_index_html_contains_progress_display(self):
        """index.html should have progress display elements."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        self.assertIn("progress-section", content)
        self.assertIn("progress-bar", content)

    def test_index_html_contains_download_button(self):
        """index.html should have download functionality."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        self.assertIn("downloadResult", content)
        self.assertIn("download", content.lower())

    def test_index_html_contains_donation_section(self):
        """index.html should have donation section."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        self.assertIn("coffee", content.lower())

    def test_index_html_contains_api_integration(self):
        """index.html should integrate with backend API endpoints."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        # Should call the transcribe endpoints
        self.assertIn("/transcribe/url", content)
        self.assertIn("/transcribe", content)
        # Should poll job status
        self.assertIn("/jobs/", content)

    def test_index_html_contains_error_handling(self):
        """index.html should have error display."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        self.assertIn("error-section", content)
        self.assertIn("error-text", content)

    def test_index_html_contains_copy_button(self):
        """index.html should have copy to clipboard functionality."""
        index = self.web_dir / "index.html"
        content = index.read_text()
        self.assertIn("copyResult", content)
        self.assertIn("clipboard", content)


@pytest.mark.asyncio
class TestWebEndpoint:
    """Test the web frontend endpoint via HTTPX/TestClient."""

    @pytest.fixture
    def app(self):
        """Create a test app with mocked lifespan."""
        from contextlib import asynccontextmanager
        from fastapi import FastAPI
        from fastapi.responses import FileResponse
        from cesar.api.server import WEB_DIR

        @asynccontextmanager
        async def test_lifespan(app):
            yield

        test_app = FastAPI(lifespan=test_lifespan)

        @test_app.get("/")
        async def serve_frontend():
            return FileResponse(WEB_DIR / "index.html")

        return test_app

    @pytest.fixture
    def client(self, app):
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_root_serves_html(self, client):
        """GET / should serve index.html."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_root_contains_app_title(self, client):
        """Root page should contain the app title."""
        response = client.get("/")
        assert "Cesar" in response.text

    def test_root_contains_tailwind(self, client):
        """Root page should include Tailwind CSS."""
        response = client.get("/")
        assert "tailwindcss" in response.text


if __name__ == "__main__":
    unittest.main()
