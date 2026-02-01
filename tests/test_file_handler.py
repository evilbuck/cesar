"""
Tests for file_handler module YouTube URL handling.

Tests the download_from_url function's routing to youtube_handler
for YouTube URLs and proper error handling.
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from fastapi import HTTPException


class TestYouTubeDownload:
    """Tests for YouTube URL handling in download_from_url."""

    @pytest.mark.asyncio
    @patch('cesar.api.file_handler.download_youtube_audio')
    @patch('cesar.api.file_handler.is_youtube_url')
    async def test_youtube_url_routed_to_handler(self, mock_is_youtube, mock_download):
        """Test that YouTube URLs are routed to youtube_handler."""
        mock_is_youtube.return_value = True
        mock_download.return_value = Path('/tmp/audio.m4a')

        from cesar.api.file_handler import download_from_url
        result = await download_from_url('https://www.youtube.com/watch?v=test123')

        mock_is_youtube.assert_called_once_with('https://www.youtube.com/watch?v=test123')
        mock_download.assert_called_once()
        assert result == '/tmp/audio.m4a'

    @pytest.mark.asyncio
    @patch('cesar.api.file_handler.download_youtube_audio')
    @patch('cesar.api.file_handler.is_youtube_url')
    async def test_youtube_ffmpeg_missing_returns_503(self, mock_is_youtube, mock_download):
        """Test that missing FFmpeg returns 503."""
        from cesar.youtube_handler import FFmpegNotFoundError

        mock_is_youtube.return_value = True
        mock_download.side_effect = FFmpegNotFoundError("FFmpeg not found")

        from cesar.api.file_handler import download_from_url
        with pytest.raises(HTTPException) as exc_info:
            await download_from_url('https://www.youtube.com/watch?v=test123')

        assert exc_info.value.status_code == 503
        assert 'FFmpeg' in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch('cesar.api.file_handler.download_youtube_audio')
    @patch('cesar.api.file_handler.is_youtube_url')
    async def test_youtube_download_error_returns_400(self, mock_is_youtube, mock_download):
        """Test that download errors return 400."""
        from cesar.youtube_handler import YouTubeUnavailableError

        mock_is_youtube.return_value = True
        mock_download.side_effect = YouTubeUnavailableError("Video unavailable")

        from cesar.api.file_handler import download_from_url
        with pytest.raises(HTTPException) as exc_info:
            await download_from_url('https://www.youtube.com/watch?v=test123')

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    @patch('cesar.api.file_handler.is_youtube_url')
    async def test_non_youtube_url_uses_regular_download(self, mock_is_youtube):
        """Test that non-YouTube URLs use regular HTTP download."""
        mock_is_youtube.return_value = False

        # This will fail because the URL doesn't exist, but proves routing works
        from cesar.api.file_handler import download_from_url

        with pytest.raises(HTTPException):
            await download_from_url('https://example.com/audio.mp3')

        mock_is_youtube.assert_called_once()
