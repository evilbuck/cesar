#!/usr/bin/env python3
"""
Tests for transcription functionality
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from cesar.device_detection import DeviceCapabilities


class TestTranscription(unittest.TestCase):
    """Test transcription functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = Path(self.temp_dir) / "test_audio.mp3"
        self.output_file = Path(self.temp_dir) / "output.txt"

        # Create a dummy input file
        self.input_file.touch()

    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    @patch('cesar.transcriber.subprocess.run')
    def test_transcribe_audio_success(self, mock_subprocess, mock_caps):
        """Test successful audio transcription"""
        # Mock device capabilities
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=4, optimal_threads=4
        )

        # Mock ffprobe for duration check
        mock_subprocess.return_value = MagicMock(stdout="10.0\n", returncode=0)

        # Mock segment objects
        mock_segment1 = MagicMock()
        mock_segment1.text = "Hello world"
        mock_segment1.end = 5.0
        mock_segment2 = MagicMock()
        mock_segment2.text = "This is a test"
        mock_segment2.end = 10.0

        # Mock transcription info
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95
        mock_info.duration = 10.0

        # Configure the mock model
        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([mock_segment1, mock_segment2]), mock_info)

        # Patch faster_whisper module for the import inside _load_model
        mock_whisper_module = MagicMock()
        mock_whisper_module.WhisperModel.return_value = mock_model

        with patch.dict('sys.modules', {'faster_whisper': mock_whisper_module}):
            from cesar.transcriber import AudioTranscriber

            # Create transcriber and run transcription
            transcriber = AudioTranscriber()
            result = transcriber.transcribe_file(
                str(self.input_file),
                str(self.output_file)
            )

            # Verify the model was called
            mock_model.transcribe.assert_called_once()

            # Verify result contains expected fields
            self.assertEqual(result['language'], 'en')
            self.assertEqual(result['language_probability'], 0.95)
            self.assertEqual(result['segment_count'], 2)
            self.assertEqual(result['output_path'], str(self.output_file))

            # Verify output file was created with correct content
            self.assertTrue(self.output_file.exists())
            with open(self.output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("Hello world", content)
                self.assertIn("This is a test", content)

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    @patch('cesar.transcriber.subprocess.run')
    def test_transcribe_audio_empty_segments(self, mock_subprocess, mock_caps):
        """Test transcription with no segments"""
        # Mock device capabilities
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=4, optimal_threads=4
        )

        # Mock ffprobe for duration check
        mock_subprocess.return_value = MagicMock(stdout="5.0\n", returncode=0)

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95

        # Empty segments
        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([]), mock_info)

        # Patch faster_whisper module for the import inside _load_model
        mock_whisper_module = MagicMock()
        mock_whisper_module.WhisperModel.return_value = mock_model

        with patch.dict('sys.modules', {'faster_whisper': mock_whisper_module}):
            from cesar.transcriber import AudioTranscriber

            # Create transcriber and run transcription
            transcriber = AudioTranscriber()
            result = transcriber.transcribe_file(
                str(self.input_file),
                str(self.output_file)
            )

            # Verify output file was created but is empty
            self.assertTrue(self.output_file.exists())
            self.assertEqual(result['segment_count'], 0)
            with open(self.output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertEqual(content, "")


class TestAudioTranscriberInit(unittest.TestCase):
    """Test AudioTranscriber initialization"""

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    def test_transcriber_default_settings(self, mock_caps):
        """Test transcriber initializes with default settings"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False,
            has_mps=False,
            cpu_cores=4,
            optimal_threads=4
        )

        from cesar.transcriber import AudioTranscriber
        transcriber = AudioTranscriber()

        self.assertEqual(transcriber.model_size, 'base')
        self.assertEqual(transcriber.device, 'cpu')
        self.assertIsNone(transcriber.model)  # Model not loaded until needed

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    def test_transcriber_custom_model(self, mock_caps):
        """Test transcriber with custom model size"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False,
            has_mps=False,
            cpu_cores=4,
            optimal_threads=4
        )

        from cesar.transcriber import AudioTranscriber
        transcriber = AudioTranscriber(model_size='small')

        self.assertEqual(transcriber.model_size, 'small')


if __name__ == "__main__":
    unittest.main()
