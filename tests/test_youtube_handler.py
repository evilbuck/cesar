"""
Unit tests for youtube_handler module.

Tests YouTube URL validation, FFmpeg detection, download functionality,
and temp file cleanup. All yt-dlp operations are mocked to avoid
real network requests.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cesar.youtube_handler import (
    FFmpegNotFoundError,
    YouTubeDownloadError,
    YouTubeRateLimitError,
    YouTubeURLError,
    YouTubeUnavailableError,
    check_ffmpeg_available,
    cleanup_youtube_temp_dir,
    download_youtube_audio,
    is_youtube_url,
    require_ffmpeg,
)


class TestIsYouTubeUrl(unittest.TestCase):
    """Tests for is_youtube_url function."""

    def test_valid_watch_url(self):
        """Test standard YouTube watch URL."""
        url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        self.assertTrue(is_youtube_url(url))

    def test_valid_watch_url_no_www(self):
        """Test YouTube watch URL without www prefix."""
        url = 'https://youtube.com/watch?v=dQw4w9WgXcQ'
        self.assertTrue(is_youtube_url(url))

    def test_valid_youtu_be(self):
        """Test shortened youtu.be URL."""
        url = 'https://youtu.be/dQw4w9WgXcQ'
        self.assertTrue(is_youtube_url(url))

    def test_valid_shorts(self):
        """Test YouTube Shorts URL."""
        url = 'https://www.youtube.com/shorts/abc123XYZ'
        self.assertTrue(is_youtube_url(url))

    def test_valid_embed(self):
        """Test YouTube embed URL."""
        url = 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        self.assertTrue(is_youtube_url(url))

    def test_valid_v_url(self):
        """Test YouTube /v/ URL format."""
        url = 'https://www.youtube.com/v/dQw4w9WgXcQ'
        self.assertTrue(is_youtube_url(url))

    def test_invalid_vimeo(self):
        """Test Vimeo URL returns False."""
        url = 'https://vimeo.com/123456'
        self.assertFalse(is_youtube_url(url))

    def test_invalid_random_url(self):
        """Test random website URL returns False."""
        url = 'https://example.com/video/123'
        self.assertFalse(is_youtube_url(url))

    def test_empty_url(self):
        """Test empty string returns False."""
        self.assertFalse(is_youtube_url(''))

    def test_none_url(self):
        """Test None returns False."""
        self.assertFalse(is_youtube_url(None))

    def test_url_with_whitespace(self):
        """Test URL with leading/trailing whitespace is handled."""
        url = '  https://youtube.com/watch?v=abc123  '
        self.assertTrue(is_youtube_url(url))

    def test_http_url(self):
        """Test HTTP (non-HTTPS) URL is accepted."""
        url = 'http://youtube.com/watch?v=abc123'
        self.assertTrue(is_youtube_url(url))


class TestCheckFfmpegAvailable(unittest.TestCase):
    """Tests for check_ffmpeg_available function."""

    def setUp(self):
        """Clear cache before each test."""
        check_ffmpeg_available.cache_clear()

    def tearDown(self):
        """Clear cache after each test."""
        check_ffmpeg_available.cache_clear()

    @patch('cesar.youtube_handler.shutil.which')
    def test_ffmpeg_available(self, mock_which):
        """Test returns (True, '') when both ffmpeg and ffprobe found."""
        mock_which.side_effect = lambda x: f'/usr/bin/{x}'

        available, error = check_ffmpeg_available()

        self.assertTrue(available)
        self.assertEqual(error, '')

    @patch('cesar.youtube_handler.shutil.which')
    def test_ffmpeg_missing(self, mock_which):
        """Test returns (False, error_msg) when ffmpeg not found."""
        mock_which.return_value = None

        available, error = check_ffmpeg_available()

        self.assertFalse(available)
        self.assertIn('FFmpeg not found', error)
        self.assertIn('pacman', error)  # Check install instructions

    @patch('cesar.youtube_handler.shutil.which')
    def test_ffprobe_missing(self, mock_which):
        """Test returns (False, error_msg) when ffprobe not found."""
        def which_side_effect(cmd):
            return '/usr/bin/ffmpeg' if cmd == 'ffmpeg' else None

        mock_which.side_effect = which_side_effect

        available, error = check_ffmpeg_available()

        self.assertFalse(available)
        self.assertIn('FFprobe not found', error)

    @patch('cesar.youtube_handler.shutil.which')
    def test_result_is_cached(self, mock_which):
        """Test check result is cached after first call."""
        mock_which.side_effect = lambda x: f'/usr/bin/{x}'

        # First call
        check_ffmpeg_available()
        # Second call
        check_ffmpeg_available()

        # shutil.which should only be called twice (once for ffmpeg, once for ffprobe)
        # on the first check_ffmpeg_available call due to caching
        self.assertEqual(mock_which.call_count, 2)


class TestRequireFfmpeg(unittest.TestCase):
    """Tests for require_ffmpeg function."""

    def setUp(self):
        """Clear cache before each test."""
        check_ffmpeg_available.cache_clear()

    def tearDown(self):
        """Clear cache after each test."""
        check_ffmpeg_available.cache_clear()

    @patch('cesar.youtube_handler.shutil.which')
    def test_require_ffmpeg_available(self, mock_which):
        """Test require_ffmpeg does nothing when ffmpeg available."""
        mock_which.side_effect = lambda x: f'/usr/bin/{x}'

        # Should not raise
        require_ffmpeg()

    @patch('cesar.youtube_handler.shutil.which')
    def test_require_ffmpeg_missing_raises(self, mock_which):
        """Test require_ffmpeg raises FFmpegNotFoundError when missing."""
        mock_which.return_value = None

        with self.assertRaises(FFmpegNotFoundError) as ctx:
            require_ffmpeg()

        self.assertIn('FFmpeg not found', str(ctx.exception))


class TestDownloadYouTubeAudio(unittest.TestCase):
    """Tests for download_youtube_audio function."""

    def setUp(self):
        """Clear cache before each test."""
        check_ffmpeg_available.cache_clear()

    def tearDown(self):
        """Clear cache after each test."""
        check_ffmpeg_available.cache_clear()

    @patch('cesar.youtube_handler.require_ffmpeg')
    def test_invalid_url_raises_error(self, mock_require):
        """Test invalid URL raises YouTubeURLError."""
        with self.assertRaises(YouTubeURLError) as ctx:
            download_youtube_audio('https://vimeo.com/123456')

        self.assertIn('Invalid YouTube URL', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    def test_ffmpeg_missing_raises_error(self, mock_require):
        """Test FFmpeg missing raises FFmpegNotFoundError."""
        mock_require.side_effect = FFmpegNotFoundError("FFmpeg not found")

        with self.assertRaises(FFmpegNotFoundError):
            download_youtube_audio('https://youtube.com/watch?v=test')

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_download_success(self, mock_ydl_class, mock_require):
        """Test successful download returns path to audio file."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {'title': 'Test Video'}

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create a fake output file
            test_file = temp_path / 'test.m4a'

            # Patch uuid to return predictable value
            with patch('cesar.youtube_handler.uuid.uuid4', return_value='test'):
                # Create the expected output file
                (temp_path / 'test.m4a').touch()

                result = download_youtube_audio(
                    'https://youtube.com/watch?v=abc123',
                    output_dir=temp_path
                )

            self.assertEqual(result, temp_path / 'test.m4a')
            mock_ydl.extract_info.assert_called_once()

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_download_error_403_raises_rate_limit(self, mock_ydl_class, mock_require):
        """Test 403 error raises YouTubeRateLimitError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError("HTTP Error 403: Forbidden")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeRateLimitError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=test',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('rate limiting', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_download_error_429_raises_rate_limit(self, mock_ydl_class, mock_require):
        """Test 429 error raises YouTubeRateLimitError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError("HTTP Error 429: Too Many Requests")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeRateLimitError):
                download_youtube_audio(
                    'https://youtube.com/watch?v=test',
                    output_dir=Path(temp_dir)
                )

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_download_error_unavailable(self, mock_ydl_class, mock_require):
        """Test unavailable video raises YouTubeUnavailableError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError("Video unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeUnavailableError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=test',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('unavailable', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_download_error_private(self, mock_ydl_class, mock_require):
        """Test private video raises YouTubeUnavailableError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError("Video is private")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeUnavailableError):
                download_youtube_audio(
                    'https://youtube.com/watch?v=test',
                    output_dir=Path(temp_dir)
                )

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_download_extractor_error(self, mock_ydl_class, mock_require):
        """Test ExtractorError raises YouTubeURLError."""
        from yt_dlp.utils import ExtractorError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = ExtractorError("Unable to extract video")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeURLError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=test',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('Could not process', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_download_postprocessing_error(self, mock_ydl_class, mock_require):
        """Test PostProcessingError raises YouTubeDownloadError."""
        from yt_dlp.utils import PostProcessingError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = PostProcessingError("FFmpeg failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeDownloadError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=test',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('Audio conversion failed', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    @patch('cesar.youtube_handler._cleanup_partial_files')
    def test_cleanup_called_on_failure(self, mock_cleanup, mock_ydl_class, mock_require):
        """Test partial files are cleaned up on download failure."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError("Network error")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeDownloadError):
                download_youtube_audio(
                    'https://youtube.com/watch?v=test',
                    output_dir=Path(temp_dir)
                )

        # Verify cleanup was called
        mock_cleanup.assert_called_once()

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_finds_alternative_extensions(self, mock_ydl_class, mock_require):
        """Test download finds file with alternative extension."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {'title': 'Test Video'}

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch('cesar.youtube_handler.uuid.uuid4', return_value='test'):
                # Create an .opus file instead of .m4a
                (temp_path / 'test.opus').touch()

                result = download_youtube_audio(
                    'https://youtube.com/watch?v=abc123',
                    output_dir=temp_path
                )

            self.assertEqual(result, temp_path / 'test.opus')


class TestCleanupYouTubeTempDir(unittest.TestCase):
    """Tests for cleanup_youtube_temp_dir function."""

    def test_cleanup_nonexistent_dir(self):
        """Test cleanup returns 0 when directory doesn't exist."""
        with patch('cesar.youtube_handler.tempfile.gettempdir', return_value='/nonexistent'):
            count = cleanup_youtube_temp_dir()
            self.assertEqual(count, 0)

    def test_cleanup_empty_dir(self):
        """Test cleanup returns 0 when directory is empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cesar_dir = temp_path / 'cesar-youtube'
            cesar_dir.mkdir()

            with patch('cesar.youtube_handler.tempfile.gettempdir', return_value=temp_dir):
                count = cleanup_youtube_temp_dir()

            self.assertEqual(count, 0)

    def test_cleanup_with_files(self):
        """Test cleanup removes files and returns count."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cesar_dir = temp_path / 'cesar-youtube'
            cesar_dir.mkdir()

            # Create some files
            (cesar_dir / 'file1.m4a').touch()
            (cesar_dir / 'file2.m4a').touch()
            (cesar_dir / 'file3.part').touch()

            with patch('cesar.youtube_handler.tempfile.gettempdir', return_value=temp_dir):
                count = cleanup_youtube_temp_dir()

            self.assertEqual(count, 3)
            # Verify files are deleted
            self.assertFalse((cesar_dir / 'file1.m4a').exists())
            self.assertFalse((cesar_dir / 'file2.m4a').exists())
            self.assertFalse((cesar_dir / 'file3.part').exists())

    def test_cleanup_preserves_subdirectories(self):
        """Test cleanup only removes files, not subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cesar_dir = temp_path / 'cesar-youtube'
            cesar_dir.mkdir()

            # Create a file and a subdirectory
            (cesar_dir / 'file1.m4a').touch()
            (cesar_dir / 'subdir').mkdir()
            (cesar_dir / 'subdir' / 'nested.m4a').touch()

            with patch('cesar.youtube_handler.tempfile.gettempdir', return_value=temp_dir):
                count = cleanup_youtube_temp_dir()

            # Only the top-level file should be counted
            self.assertEqual(count, 1)
            # Subdirectory should still exist
            self.assertTrue((cesar_dir / 'subdir').exists())


if __name__ == "__main__":
    unittest.main()
