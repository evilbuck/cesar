#!/usr/bin/env python3
"""
Tests for input validation functions in AudioTranscriber
"""
import unittest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from cesar.device_detection import DeviceCapabilities


class TestValidation(unittest.TestCase):
    """Test input validation functions"""

    def setUp(self):
        """Set up test files"""
        self.temp_dir = tempfile.mkdtemp()

        # Create test audio files
        self.valid_audio_file = Path(self.temp_dir) / "test.mp3"
        self.valid_audio_file.touch()

        self.unsupported_file = Path(self.temp_dir) / "test.txt"
        self.unsupported_file.touch()

        # Mock device detection to avoid importing torch
        self.mock_caps_patcher = patch('cesar.device_detection.DeviceDetector.get_capabilities')
        self.mock_caps = self.mock_caps_patcher.start()
        self.mock_caps.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=4, optimal_threads=4
        )

        # Import and create transcriber after mocking
        from cesar.transcriber import AudioTranscriber
        self.transcriber = AudioTranscriber()

    def tearDown(self):
        """Clean up test files"""
        self.mock_caps_patcher.stop()
        shutil.rmtree(self.temp_dir)

    def test_validate_input_file_exists(self):
        """Test validation of existing audio file"""
        result = self.transcriber.validate_input_file(str(self.valid_audio_file))
        self.assertEqual(result, self.valid_audio_file)

    def test_validate_input_file_not_found(self):
        """Test validation of non-existent file"""
        with self.assertRaises(FileNotFoundError):
            self.transcriber.validate_input_file("nonexistent.mp3")

    def test_validate_input_file_unsupported_format(self):
        """Test validation of unsupported file format"""
        with self.assertRaises(ValueError):
            self.transcriber.validate_input_file(str(self.unsupported_file))

    def test_validate_input_file_directory(self):
        """Test validation when path is a directory"""
        with self.assertRaises(ValueError):
            self.transcriber.validate_input_file(self.temp_dir)

    def test_validate_output_path_valid(self):
        """Test validation of valid output path"""
        output_path = Path(self.temp_dir) / "output.txt"
        result = self.transcriber.validate_output_path(str(output_path))
        self.assertEqual(result, output_path)

    def test_validate_output_path_creates_directory(self):
        """Test that output validation creates parent directories"""
        output_path = Path(self.temp_dir) / "subdir" / "output.txt"
        result = self.transcriber.validate_output_path(str(output_path))
        self.assertEqual(result, output_path)
        self.assertTrue(output_path.parent.exists())

    def test_supported_audio_formats(self):
        """Test that all expected audio formats are supported"""
        from cesar.transcriber import AudioTranscriber
        expected_formats = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma'}
        self.assertEqual(AudioTranscriber.SUPPORTED_FORMATS, expected_formats)


if __name__ == "__main__":
    unittest.main()
