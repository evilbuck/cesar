#!/usr/bin/env python3
"""
Tests for CLI argument parsing and commands
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from click.testing import CliRunner

from cesar.cli import cli, transcribe


class TestCLI(unittest.TestCase):
    """Test CLI commands and argument parsing"""

    def setUp(self):
        """Set up test environment"""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        # Create a test audio file
        self.test_audio = Path(self.temp_dir) / "test.mp3"
        self.test_audio.touch()
        self.output_file = Path(self.temp_dir) / "output.txt"

    def tearDown(self):
        """Clean up test files"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_cli_help(self):
        """Test CLI help command"""
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('cesar', result.output.lower())

    def test_cli_version(self):
        """Test CLI version command"""
        result = self.runner.invoke(cli, ['--version'])
        self.assertEqual(result.exit_code, 0)
        # Should show version number
        self.assertIn('cesar', result.output.lower())

    def test_transcribe_help(self):
        """Test transcribe subcommand help"""
        result = self.runner.invoke(cli, ['transcribe', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('INPUT', result.output)
        self.assertIn('YouTube', result.output)  # Should mention YouTube support
        self.assertIn('--output', result.output)
        self.assertIn('--model', result.output)

    def test_transcribe_missing_input(self):
        """Test transcribe with missing input file"""
        result = self.runner.invoke(cli, ['transcribe', '-o', 'output.txt'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('missing argument', result.output.lower())

    def test_transcribe_missing_output(self):
        """Test transcribe with missing output option"""
        result = self.runner.invoke(cli, ['transcribe', str(self.test_audio)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('--output', result.output.lower())

    def test_transcribe_nonexistent_input(self):
        """Test transcribe with non-existent input file"""
        result = self.runner.invoke(cli, ['transcribe', 'nonexistent.mp3', '-o', 'output.txt'])
        self.assertNotEqual(result.exit_code, 0)

    def test_model_choices(self):
        """Test valid model choices are accepted"""
        # Just test that the help shows valid choices
        result = self.runner.invoke(cli, ['transcribe', '--help'])
        self.assertEqual(result.exit_code, 0)
        for model in ['tiny', 'base', 'small', 'medium', 'large']:
            self.assertIn(model, result.output.lower())

    def test_device_choices(self):
        """Test valid device choices are shown"""
        result = self.runner.invoke(cli, ['transcribe', '--help'])
        self.assertEqual(result.exit_code, 0)
        for device in ['auto', 'cpu', 'cuda', 'mps']:
            self.assertIn(device, result.output.lower())

    @patch('cesar.cli.download_youtube_audio')
    @patch('cesar.cli.is_youtube_url')
    @patch('cesar.cli.AudioTranscriber')
    def test_transcribe_youtube_url(self, mock_transcriber, mock_is_youtube, mock_download):
        """Test transcribing a YouTube URL."""
        mock_is_youtube.return_value = True
        # Create a real temp file for the mock to return
        with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as f:
            f.write(b'fake audio')
            temp_path = Path(f.name)
        mock_download.return_value = temp_path

        # Mock the transcriber to avoid real transcription
        mock_instance = MagicMock()
        mock_instance.get_audio_duration.return_value = 60.0
        mock_instance.transcribe_file.return_value = {
            'language': 'en',
            'language_probability': 0.99,
            'audio_duration': 60.0,
            'processing_time': 5.0,
            'speed_ratio': 12.0,
            'segment_count': 10,
            'output_path': str(self.output_file),
        }
        mock_transcriber.return_value = mock_instance

        runner = CliRunner()
        result = runner.invoke(cli, [
            'transcribe',
            'https://www.youtube.com/watch?v=test123',
            '-o', str(self.output_file),
            '-q',  # Quiet to simplify output checking
        ])

        # Verify download was called
        mock_download.assert_called_once()
        # Should succeed
        self.assertEqual(result.exit_code, 0)
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @patch('cesar.cli.is_youtube_url')
    @patch('cesar.cli.download_youtube_audio')
    def test_transcribe_youtube_ffmpeg_missing(self, mock_download, mock_is_youtube):
        """Test YouTube URL with FFmpeg missing."""
        from cesar.youtube_handler import FFmpegNotFoundError
        mock_is_youtube.return_value = True
        mock_download.side_effect = FFmpegNotFoundError("FFmpeg not found")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'transcribe',
            'https://www.youtube.com/watch?v=test123',
            '-o', str(self.output_file),
        ])

        self.assertNotEqual(result.exit_code, 0)
        # Check error appears in output or stderr
        output_text = result.output + (result.stderr or '')
        self.assertIn('FFmpeg', output_text)

    @patch('cesar.cli.is_youtube_url')
    @patch('cesar.cli.download_youtube_audio')
    def test_transcribe_youtube_download_error(self, mock_download, mock_is_youtube):
        """Test YouTube URL with download error."""
        from cesar.youtube_handler import YouTubeUnavailableError
        mock_is_youtube.return_value = True
        mock_download.side_effect = YouTubeUnavailableError("Video unavailable")

        runner = CliRunner()
        result = runner.invoke(cli, [
            'transcribe',
            'https://www.youtube.com/watch?v=test123',
            '-o', str(self.output_file),
        ])

        self.assertNotEqual(result.exit_code, 0)

    def test_transcribe_non_youtube_url_rejected(self):
        """Test that non-YouTube URLs are rejected in CLI."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            'transcribe',
            'https://example.com/audio.mp3',
            '-o', str(self.output_file),
        ])

        # Should fail - CLI only supports files and YouTube URLs
        self.assertNotEqual(result.exit_code, 0)


class TestYouTubeErrorFormatting(unittest.TestCase):
    """Tests for CLI YouTube error message formatting."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.output_file = Path(self.temp_dir) / "output.txt"

    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir)

    @patch('cesar.cli.download_youtube_audio')
    @patch('cesar.cli.is_youtube_url', return_value=True)
    def test_youtube_error_displays_message(self, mock_is_yt, mock_download):
        """Test YouTube errors are displayed with user-friendly format."""
        from cesar.youtube_handler import YouTubeUnavailableError
        mock_download.side_effect = YouTubeUnavailableError(
            "Private video (video: xyz789). This video is private."
        )

        result = self.runner.invoke(
            transcribe,
            ['https://youtube.com/watch?v=xyz789', '-o', str(self.output_file)]
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('YouTube Error:', result.output)
        self.assertIn('Private video', result.output)

    @patch('cesar.cli.download_youtube_audio')
    @patch('cesar.cli.is_youtube_url', return_value=True)
    def test_verbose_shows_cause(self, mock_is_yt, mock_download):
        """Test verbose mode shows underlying cause."""
        from cesar.youtube_handler import YouTubeNetworkError
        inner_error = Exception("HTTP Error 500: Internal Server Error")
        outer_error = YouTubeNetworkError("Network error (video: abc123).")
        outer_error.__cause__ = inner_error
        mock_download.side_effect = outer_error

        result = self.runner.invoke(
            transcribe,
            ['https://youtube.com/watch?v=abc123', '-o', str(self.output_file), '-v']
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Cause:', result.output)
        self.assertIn('HTTP Error 500', result.output)

    @patch('cesar.cli.download_youtube_audio')
    @patch('cesar.cli.is_youtube_url', return_value=True)
    def test_verbose_without_cause_no_crash(self, mock_is_yt, mock_download):
        """Test verbose mode handles errors without __cause__."""
        from cesar.youtube_handler import YouTubeRateLimitError
        mock_download.side_effect = YouTubeRateLimitError("Rate limited (video: abc123).")

        result = self.runner.invoke(
            transcribe,
            ['https://youtube.com/watch?v=abc123', '-o', str(self.output_file), '-v']
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('YouTube Error:', result.output)
        # Should not crash, and should not show "Cause:" line
        self.assertNotIn('Cause:', result.output)

    @patch('cesar.cli.download_youtube_audio')
    @patch('cesar.cli.is_youtube_url', return_value=True)
    def test_non_verbose_hides_cause(self, mock_is_yt, mock_download):
        """Test non-verbose mode does not show underlying cause."""
        from cesar.youtube_handler import YouTubeNetworkError
        inner_error = Exception("HTTP Error 500: Internal Server Error")
        outer_error = YouTubeNetworkError("Network error (video: abc123).")
        outer_error.__cause__ = inner_error
        mock_download.side_effect = outer_error

        result = self.runner.invoke(
            transcribe,
            ['https://youtube.com/watch?v=abc123', '-o', str(self.output_file)]
        )

        self.assertEqual(result.exit_code, 1)
        self.assertIn('YouTube Error:', result.output)
        self.assertNotIn('Cause:', result.output)


if __name__ == "__main__":
    unittest.main()
