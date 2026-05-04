#!/usr/bin/env python3
"""
Tests for VideoProcessor (FFmpeg frame extraction and video metadata)
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cesar.video_processor import VideoProcessor, VideoMetadata


class TestVideoProcessor(unittest.TestCase):
    """Test VideoProcessor functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = VideoProcessor()

    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)

    def test_supported_formats(self):
        """Test that supported video formats are defined"""
        self.assertIn('.mp4', VideoProcessor.SUPPORTED_FORMATS)
        self.assertIn('.mkv', VideoProcessor.SUPPORTED_FORMATS)
        self.assertIn('.mov', VideoProcessor.SUPPORTED_FORMATS)
        self.assertIn('.avi', VideoProcessor.SUPPORTED_FORMATS)
        self.assertIn('.webm', VideoProcessor.SUPPORTED_FORMATS)

    def test_supported_image_formats(self):
        """Test that supported image formats are defined"""
        self.assertIn('.png', VideoProcessor.SUPPORTED_IMAGE_FORMATS)
        self.assertIn('.jpg', VideoProcessor.SUPPORTED_IMAGE_FORMATS)
        self.assertIn('.jpeg', VideoProcessor.SUPPORTED_IMAGE_FORMATS)

    def test_validate_video_file_not_found(self):
        """Test validation fails for non-existent file"""
        non_existent = Path(self.temp_dir) / "nonexistent.mp4"
        with self.assertRaises(FileNotFoundError):
            self.processor.validate_video_file(non_existent)

    def test_validate_video_file_unsupported_format(self):
        """Test validation fails for unsupported format"""
        # Create a fake file with wrong extension
        fake_video = Path(self.temp_dir) / "video.mp3"
        fake_video.touch()
        with self.assertRaises(ValueError) as ctx:
            self.processor.validate_video_file(fake_video)
        self.assertIn("Unsupported video format", str(ctx.exception))

    def test_validate_video_file_directory(self):
        """Test validation fails for directory instead of file"""
        test_dir = Path(self.temp_dir) / "subdir"
        test_dir.mkdir()
        with self.assertRaises(ValueError) as ctx:
            self.processor.validate_video_file(test_dir)
        self.assertIn("Path is not a file", str(ctx.exception))

    @patch('cesar.video_processor.subprocess.run')
    def test_validate_video_file_ffprobe_check(self, mock_run):
        """Test validation calls ffprobe to verify video stream"""
        # Create a fake video file
        fake_video = Path(self.temp_dir) / "video.mp4"
        fake_video.touch()

        # Track calls to distinguish ffmpeg -version from ffprobe
        call_count = [0]

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd and cmd[0] == 'ffmpeg' and '-version' in cmd:
                call_count[0] += 1
                return MagicMock(returncode=0, stdout="ffmpeg version 6.0", stderr="")
            else:
                call_count[0] += 1
                return MagicMock(returncode=0, stdout="video", stderr="")

        mock_run.side_effect = mock_run_side_effect

        # Should not raise when ffprobe succeeds
        result = self.processor.validate_video_file(fake_video)
        self.assertEqual(result, fake_video)

        # Verify both ffmpeg version check and ffprobe were called
        self.assertGreaterEqual(mock_run.call_count, 1)

    def test_ffmpeg_not_available(self):
        """Test behavior when FFmpeg is not available"""
        processor = VideoProcessor()
        # Reset cached values
        processor._ffmpeg_available = None
        processor._ffmpeg_version = None

        with patch.object(processor, '_check_ffmpeg', return_value=False):
            self.assertFalse(processor.ffmpeg_available)
            self.assertIsNone(processor.ffmpeg_version)

    @patch('cesar.video_processor.subprocess.run')
    def test_ffmpeg_available_true(self, mock_run):
        """Test FFmpeg availability detection when FFmpeg is installed"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ffmpeg version 6.0\n...",
            stderr=""
        )

        processor = VideoProcessor()
        processor._ffmpeg_available = None  # Reset cache
        processor._ffmpeg_version = None

        self.assertTrue(processor.ffmpeg_available)
        self.assertIsNotNone(processor.ffmpeg_version)

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_frame_no_ffmpeg(self, mock_run):
        """Test frame extraction fails when FFmpeg is not available"""
        processor = VideoProcessor()
        processor._ffmpeg_available = False

        video_path = Path(self.temp_dir) / "video.mp4"
        video_path.touch()
        output_path = Path(self.temp_dir) / "frame.png"

        with self.assertRaises(RuntimeError) as ctx:
            processor.extract_frame(video_path, 10.0, output_path)
        self.assertIn("FFmpeg is not available", str(ctx.exception))

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_frame_unsupported_format(self, mock_run):
        """Test frame extraction fails for unsupported image format"""
        processor = VideoProcessor()
        processor._ffmpeg_available = True

        video_path = Path(self.temp_dir) / "video.mp4"
        video_path.touch()
        output_path = Path(self.temp_dir) / "frame.tiff"

        with self.assertRaises(ValueError) as ctx:
            processor.extract_frame(video_path, 10.0, output_path, image_format='tiff')
        self.assertIn("Unsupported image format", str(ctx.exception))

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_frame_success(self, mock_run):
        """Test successful frame extraction"""
        processor = VideoProcessor()
        processor._ffmpeg_available = True

        video_path = Path(self.temp_dir) / "video.mp4"
        video_path.touch()
        output_path = Path(self.temp_dir) / "frame.png"

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd and cmd[0] == 'ffmpeg' and '-version' in cmd:
                return MagicMock(returncode=0, stdout="ffmpeg version 6.0", stderr="")
            elif cmd and cmd[0] == 'ffprobe':
                return MagicMock(returncode=0, stdout="video", stderr="")
            else:
                return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        result = processor.extract_frame(video_path, 10.5, output_path)
        self.assertEqual(result, output_path)

        # Verify FFmpeg command was called with -ss flag
        ffmpeg_calls = [c for c in mock_run.call_args_list
                       if c[0] and c[0][0][0] == 'ffmpeg' and '-ss' in c[0][0]]
        self.assertGreaterEqual(len(ffmpeg_calls), 1)

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_frames_batch(self, mock_run):
        """Test batch frame extraction calls subprocess for each timestamp"""
        processor = VideoProcessor()
        processor._ffmpeg_available = True

        video_path = Path(self.temp_dir) / "video.mp4"
        video_path.touch()
        output_dir = Path(self.temp_dir) / "frames"
        output_dir.mkdir()

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if cmd and cmd[0] == 'ffmpeg' and '-version' in cmd:
                return MagicMock(returncode=0, stdout="ffmpeg version 6.0", stderr="")
            elif cmd and cmd[0] == 'ffprobe':
                return MagicMock(returncode=0, stdout="video", stderr="")
            else:
                # Return MagicMock that has exists() returning True
                m = MagicMock(returncode=0, stdout="", stderr="")
                m.exists.return_value = True
                return m

        mock_run.side_effect = mock_run_side_effect

        timestamps = [10.0, 20.0, 30.0]
        result = processor.extract_frames_batch(
            video_path, timestamps, output_dir, "frame"
        )

        self.assertEqual(len(result), 3)
        # Check files have correct naming pattern
        for path in result:
            self.assertTrue(path.name.startswith("frame_"))
            self.assertTrue(path.name.endswith(".png"))

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_frames_batch_partial_failure(self, mock_run):
        """Test batch extraction handles partial failures gracefully"""
        processor = VideoProcessor()
        processor._ffmpeg_available = True

        video_path = Path(self.temp_dir) / "video.mp4"
        video_path.touch()
        output_dir = Path(self.temp_dir) / "frames"
        output_dir.mkdir()

        call_count = [0]

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            call_count[0] += 1

            # First ffmpeg version check
            if cmd and cmd[0] == 'ffmpeg' and '-version' in cmd:
                return MagicMock(returncode=0, stdout="ffmpeg version 6.0", stderr="")
            # ffprobe check
            elif cmd and cmd[0] == 'ffprobe':
                return MagicMock(returncode=0, stdout="video", stderr="")
            # Frame extraction calls (skip first, fail second)
            elif call_count[0] > 3:  # Skip the version check and ffprobe
                if (call_count[0] - 3) % 2 == 0:  # Fail every other frame
                    raise subprocess.CalledProcessError(1, "ffmpeg", stderr="error")

            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = mock_run_side_effect

        timestamps = [10.0, 20.0, 30.0]
        result = processor.extract_frames_batch(
            video_path, timestamps, output_dir, "frame"
        )

        # Should still get some successful frames
        self.assertGreater(len(result), 0)

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_frames_batch_all_fail(self, mock_run):
        """Test batch extraction raises error when all frames fail"""
        processor = VideoProcessor()
        processor._ffmpeg_available = True

        video_path = Path(self.temp_dir) / "video.mp4"
        video_path.touch()
        output_dir = Path(self.temp_dir) / "frames"
        output_dir.mkdir()

        call_count = [0]

        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            call_count[0] += 1

            # First ffmpeg version check - must succeed
            if cmd and cmd[0] == 'ffmpeg' and '-version' in cmd:
                return MagicMock(returncode=0, stdout="ffmpeg version 6.0", stderr="")
            # ffprobe check - must succeed
            elif cmd and cmd[0] == 'ffprobe':
                return MagicMock(returncode=0, stdout="video", stderr="")
            # All frame extraction calls fail
            else:
                raise subprocess.CalledProcessError(1, "ffmpeg", stderr="error")

        mock_run.side_effect = mock_run_side_effect

        timestamps = [10.0, 20.0]
        with self.assertRaises(RuntimeError) as ctx:
            processor.extract_frames_batch(
                video_path, timestamps, output_dir, "frame"
            )
        self.assertIn("Failed to extract any frames", str(ctx.exception))

    def test_parse_fps_fraction(self):
        """Test FPS parsing from fraction format"""
        result = self.processor._parse_fps("30000/1001")
        self.assertAlmostEqual(result, 29.97, places=2)

    def test_parse_fps_integer(self):
        """Test FPS parsing from integer format"""
        result = self.processor._parse_fps("30")
        self.assertEqual(result, 30.0)

    def test_parse_fps_invalid(self):
        """Test FPS parsing with invalid input"""
        result = self.processor._parse_fps("invalid")
        self.assertEqual(result, 0.0)

    def test_parse_fps_zero_denominator(self):
        """Test FPS parsing with zero denominator"""
        result = self.processor._parse_fps("30/0")
        self.assertEqual(result, 0.0)


class TestVideoMetadata(unittest.TestCase):
    """Test VideoMetadata dataclass"""

    def test_video_metadata_creation(self):
        """Test VideoMetadata can be created with all fields"""
        metadata = VideoMetadata(
            duration=120.5,
            width=1920,
            height=1080,
            fps=30.0,
            codec="h264",
            file_size=1048576
        )
        self.assertEqual(metadata.duration, 120.5)
        self.assertEqual(metadata.width, 1920)
        self.assertEqual(metadata.height, 1080)
        self.assertEqual(metadata.fps, 30.0)
        self.assertEqual(metadata.codec, "h264")
        self.assertEqual(metadata.file_size, 1048576)


class TestExtractAudio(unittest.TestCase):
    """Test audio extraction from video files"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = VideoProcessor()

    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)

    def test_extract_audio_no_ffmpeg(self):
        """Test extract_audio raises when FFmpeg is unavailable"""
        self.processor._ffmpeg_available = False
        video = Path(self.temp_dir) / "video.mp4"
        video.touch()
        output = Path(self.temp_dir) / "audio.mp3"

        with self.assertRaises(RuntimeError) as ctx:
            self.processor.extract_audio(video, output)
        self.assertIn("FFmpeg is not available", str(ctx.exception))

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_audio_success(self, mock_run):
        """Test successful audio extraction"""
        mock_run.return_value = MagicMock(returncode=0)
        self.processor._ffmpeg_available = True

        video = Path(self.temp_dir) / "video.mp4"
        video.touch()
        output = Path(self.temp_dir) / "output" / "audio.mp3"

        result = self.processor.extract_audio(video, output)

        self.assertEqual(result, output)
        self.assertEqual(mock_run.call_count, 2)  # validate (ffprobe) + extract (ffmpeg)
        # Verify FFmpeg extraction args (second call)
        cmd = mock_run.call_args_list[1][0][0]
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-vn", cmd)
        self.assertIn("-ab", cmd)

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_audio_creates_output_dir(self, mock_run):
        """Test that extract_audio creates output directory if needed"""
        mock_run.return_value = MagicMock(returncode=0)
        self.processor._ffmpeg_available = True

        video = Path(self.temp_dir) / "video.mp4"
        video.touch()
        output = Path(self.temp_dir) / "nested" / "dir" / "audio.mp3"

        self.processor.extract_audio(video, output)

        # Output directory should have been created
        self.assertTrue(output.parent.exists())

    @patch('cesar.video_processor.subprocess.run')
    def test_extract_audio_ffmpeg_failure(self, mock_run):
        """Test audio extraction handles FFmpeg errors"""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="No audio stream found"
        )
        self.processor._ffmpeg_available = True

        video = Path(self.temp_dir) / "video.mp4"
        video.touch()
        output = Path(self.temp_dir) / "audio.mp3"

        with self.assertRaises(RuntimeError) as ctx:
            self.processor.extract_audio(video, output)
        self.assertIn("Failed to extract audio", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
