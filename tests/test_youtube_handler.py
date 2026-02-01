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
    YouTubeAgeRestrictedError,
    YouTubeDownloadError,
    YouTubeNetworkError,
    YouTubeRateLimitError,
    YouTubeURLError,
    YouTubeUnavailableError,
    check_ffmpeg_available,
    cleanup_youtube_temp_dir,
    download_youtube_audio,
    extract_video_id,
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

            self.assertIn('limiting', str(ctx.exception))

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


class TestExtractVideoId(unittest.TestCase):
    """Tests for extract_video_id function."""

    def test_extract_from_watch_url(self):
        """Test extraction from standard watch URL."""
        url = 'https://youtube.com/watch?v=dQw4w9WgXcQ'
        self.assertEqual(extract_video_id(url), 'dQw4w9WgXcQ')

    def test_extract_from_youtu_be(self):
        """Test extraction from shortened youtu.be URL."""
        url = 'https://youtu.be/dQw4w9WgXcQ'
        self.assertEqual(extract_video_id(url), 'dQw4w9WgXcQ')

    def test_extract_from_shorts(self):
        """Test extraction from YouTube Shorts URL."""
        url = 'https://youtube.com/shorts/abc123XYZ00'
        self.assertEqual(extract_video_id(url), 'abc123XYZ00')

    def test_extract_from_embed(self):
        """Test extraction from embed URL."""
        url = 'https://youtube.com/embed/dQw4w9WgXcQ'
        self.assertEqual(extract_video_id(url), 'dQw4w9WgXcQ')

    def test_extract_with_extra_params(self):
        """Test extraction with additional URL parameters."""
        url = 'https://youtube.com/watch?v=dQw4w9WgXcQ&list=PLxyz'
        self.assertEqual(extract_video_id(url), 'dQw4w9WgXcQ')

    def test_extract_from_invalid_url(self):
        """Test extraction from non-YouTube URL returns 'unknown'."""
        url = 'https://example.com/video'
        self.assertEqual(extract_video_id(url), 'unknown')

    def test_extract_from_empty_string(self):
        """Test extraction from empty string returns 'unknown'."""
        self.assertEqual(extract_video_id(''), 'unknown')

    def test_extract_from_none(self):
        """Test extraction from None returns 'unknown'."""
        self.assertEqual(extract_video_id(None), 'unknown')


class TestExceptionAttributes(unittest.TestCase):
    """Tests for exception class attributes."""

    def test_youtube_download_error_attributes(self):
        """Test YouTubeDownloadError has correct attributes."""
        self.assertEqual(YouTubeDownloadError.error_type, 'youtube_error')
        self.assertEqual(YouTubeDownloadError.http_status, 400)

    def test_youtube_url_error_attributes(self):
        """Test YouTubeURLError has correct attributes."""
        self.assertEqual(YouTubeURLError.error_type, 'invalid_youtube_url')
        self.assertEqual(YouTubeURLError.http_status, 400)

    def test_youtube_unavailable_error_attributes(self):
        """Test YouTubeUnavailableError has correct attributes."""
        self.assertEqual(YouTubeUnavailableError.error_type, 'video_unavailable')
        self.assertEqual(YouTubeUnavailableError.http_status, 404)

    def test_youtube_rate_limit_error_attributes(self):
        """Test YouTubeRateLimitError has correct attributes."""
        self.assertEqual(YouTubeRateLimitError.error_type, 'rate_limited')
        self.assertEqual(YouTubeRateLimitError.http_status, 429)

    def test_youtube_age_restricted_error_attributes(self):
        """Test YouTubeAgeRestrictedError has correct attributes."""
        self.assertEqual(YouTubeAgeRestrictedError.error_type, 'age_restricted')
        self.assertEqual(YouTubeAgeRestrictedError.http_status, 403)

    def test_youtube_network_error_attributes(self):
        """Test YouTubeNetworkError has correct attributes."""
        self.assertEqual(YouTubeNetworkError.error_type, 'network_error')
        self.assertEqual(YouTubeNetworkError.http_status, 502)

    def test_ffmpeg_not_found_error_attributes(self):
        """Test FFmpegNotFoundError has correct attributes."""
        self.assertEqual(FFmpegNotFoundError.error_type, 'ffmpeg_not_found')
        self.assertEqual(FFmpegNotFoundError.http_status, 503)


class TestDownloadErrorDetection(unittest.TestCase):
    """Tests for error detection patterns in download_youtube_audio."""

    def setUp(self):
        """Clear FFmpeg cache before each test."""
        check_ffmpeg_available.cache_clear()

    def tearDown(self):
        """Clear FFmpeg cache after each test."""
        check_ffmpeg_available.cache_clear()

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_detects_age_restricted(self, mock_ydl_class, mock_require):
        """Test age-restricted video raises YouTubeAgeRestrictedError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError(
            "Sign in to confirm your age"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeAgeRestrictedError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=test123test',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('Age-restricted', str(ctx.exception))
            self.assertIn('test123test', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_detects_private_video(self, mock_ydl_class, mock_require):
        """Test private video raises YouTubeUnavailableError with specific message."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError(
            "This is a private video"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeUnavailableError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=pvt123pvt00',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('Private', str(ctx.exception))
            self.assertIn('pvt123pvt00', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_detects_geo_restricted(self, mock_ydl_class, mock_require):
        """Test geo-restricted video raises YouTubeUnavailableError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError(
            "Video not available in your country"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeUnavailableError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=geo123geo00',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('Geo-restricted', str(ctx.exception))
            self.assertIn('geo123geo00', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_detects_network_timeout(self, mock_ydl_class, mock_require):
        """Test network timeout raises YouTubeNetworkError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError(
            "Connection timed out"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeNetworkError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=net123net00',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('timeout', str(ctx.exception))
            self.assertIn('net123net00', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_detects_connection_reset(self, mock_ydl_class, mock_require):
        """Test connection reset raises YouTubeNetworkError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError(
            "Connection reset by peer"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeNetworkError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=rst123rst00',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('interrupted', str(ctx.exception))
            self.assertIn('rst123rst00', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_detects_rate_limit_403(self, mock_ydl_class, mock_require):
        """Test 403 error raises YouTubeRateLimitError."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError(
            "HTTP Error 403: Forbidden"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeRateLimitError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=lim123lim00',
                    output_dir=Path(temp_dir)
                )

            self.assertIn('limiting', str(ctx.exception))
            self.assertIn('lim123lim00', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    @patch('cesar.youtube_handler.yt_dlp.YoutubeDL')
    def test_error_message_includes_video_id(self, mock_ydl_class, mock_require):
        """Test that error messages include video ID."""
        from yt_dlp.utils import DownloadError

        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError("Video unavailable")

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YouTubeUnavailableError) as ctx:
                download_youtube_audio(
                    'https://youtube.com/watch?v=abc123XYZ99',
                    output_dir=Path(temp_dir)
                )

            # Verify video ID appears in message
            self.assertIn('abc123XYZ99', str(ctx.exception))
            # Verify format matches expected pattern
            self.assertIn('video:', str(ctx.exception))

    @patch('cesar.youtube_handler.require_ffmpeg')
    def test_invalid_url_includes_video_id(self, mock_require):
        """Test invalid URL error includes video ID extraction."""
        with self.assertRaises(YouTubeURLError) as ctx:
            download_youtube_audio('https://example.com/video')

        self.assertIn('unknown', str(ctx.exception))
        self.assertIn('video:', str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
