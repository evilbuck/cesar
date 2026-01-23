#!/usr/bin/env python3
"""
Tests for Whisper model initialization and loading
"""
import unittest
from unittest.mock import patch, MagicMock

from cesar.transcriber import AudioTranscriber
from cesar.device_detection import OptimalConfiguration, DeviceDetector, DeviceCapabilities


class TestModelInitialization(unittest.TestCase):
    """Test Whisper model initialization"""

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    def test_model_not_loaded_at_init(self, mock_caps):
        """Test that model is not loaded at initialization"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False,
            has_mps=False,
            cpu_cores=4,
            optimal_threads=4
        )

        transcriber = AudioTranscriber(model_size="base")

        # Model should not be loaded yet
        self.assertIsNone(transcriber.model)
        self.assertEqual(transcriber.model_size, "base")

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    def test_model_loads_on_transcribe(self, mock_caps):
        """Test that model loads when transcription is called"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False,
            has_mps=False,
            cpu_cores=4,
            optimal_threads=4
        )

        transcriber = AudioTranscriber(model_size="base")

        # Patch faster_whisper module when it's imported inside _load_model
        with patch.dict('sys.modules', {'faster_whisper': MagicMock()}):
            import sys
            mock_whisper_module = sys.modules['faster_whisper']
            mock_model = MagicMock()
            mock_whisper_module.WhisperModel.return_value = mock_model

            transcriber._load_model()

            # Verify model was created
            mock_whisper_module.WhisperModel.assert_called_once()
            self.assertIsNotNone(transcriber.model)

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    def test_load_model_handles_import_error(self, mock_caps):
        """Test handling of missing faster-whisper dependency"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False,
            has_mps=False,
            cpu_cores=4,
            optimal_threads=4
        )

        transcriber = AudioTranscriber(model_size="base")

        # Patch the import to fail
        with patch.dict('sys.modules', {'faster_whisper': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'faster_whisper'")):
                with self.assertRaises(ImportError) as context:
                    transcriber._load_model()

                self.assertIn("faster-whisper is not installed", str(context.exception))


class TestDeviceDetection(unittest.TestCase):
    """Test device detection functionality"""

    @patch('cesar.device_detection.DeviceDetector._check_cuda')
    @patch('cesar.device_detection.DeviceDetector._check_mps')
    @patch('os.cpu_count')
    def test_device_detection_cpu_only(self, mock_cpu_count, mock_mps, mock_cuda):
        """Test device detection with CPU only"""
        mock_cpu_count.return_value = 4
        mock_cuda.return_value = False
        mock_mps.return_value = False

        detector = DeviceDetector()
        caps = detector.get_capabilities()

        self.assertFalse(caps.has_cuda)
        self.assertFalse(caps.has_mps)
        self.assertEqual(caps.cpu_cores, 4)

    def test_optimal_device_selection_cpu(self):
        """Test optimal device selection returns CPU when no GPU"""
        mock_detector = MagicMock()
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=False,
            has_mps=False,
            cpu_cores=4,
            optimal_threads=4
        )

        config = OptimalConfiguration(detector=mock_detector)
        device = config.get_optimal_device()

        self.assertEqual(device, "cpu")

    def test_optimal_device_selection_cuda(self):
        """Test optimal device selection returns CUDA when available"""
        mock_detector = MagicMock()
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=True,
            has_mps=False,
            cpu_cores=4,
            optimal_threads=4
        )

        config = OptimalConfiguration(detector=mock_detector)
        device = config.get_optimal_device()

        self.assertEqual(device, "cuda")

    def test_optimal_device_with_override(self):
        """Test device selection with user override"""
        mock_detector = MagicMock()
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=True,
            has_mps=False,
            cpu_cores=4,
            optimal_threads=4
        )

        config = OptimalConfiguration(detector=mock_detector)
        device = config.get_optimal_device(override="cpu")

        # User override should be respected
        self.assertEqual(device, "cpu")


if __name__ == "__main__":
    unittest.main()
