#!/usr/bin/env python3
"""
Tests for audio processing and worker configuration
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from cesar.transcriber import AudioTranscriber
from cesar.device_detection import OptimalConfiguration, DeviceDetector, DeviceCapabilities


class TestAudioDuration(unittest.TestCase):
    """Test audio duration detection functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    @patch('cesar.transcriber.subprocess.run')
    def test_get_audio_duration_success(self, mock_run, mock_caps):
        """Test successful audio duration detection"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=4, optimal_threads=4
        )

        # Mock ffprobe output
        mock_run.return_value = MagicMock(stdout="1800.5\n", returncode=0)

        transcriber = AudioTranscriber()
        duration = transcriber.get_audio_duration("test.mp3")

        self.assertEqual(duration, 1800.5)
        mock_run.assert_called_once()

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    @patch('cesar.transcriber.subprocess.run')
    def test_get_audio_duration_failure(self, mock_run, mock_caps):
        """Test audio duration detection failure"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=4, optimal_threads=4
        )

        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffprobe')

        transcriber = AudioTranscriber()
        with self.assertRaises(RuntimeError):
            transcriber.get_audio_duration("nonexistent.mp3")


class TestWorkerConfiguration(unittest.TestCase):
    """Test worker and thread configuration"""

    def test_get_optimal_thread_count_user_specified(self):
        """Test thread count with user specification"""
        mock_detector = MagicMock()
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=8, optimal_threads=6
        )

        config = OptimalConfiguration(detector=mock_detector)
        self.assertEqual(config.get_optimal_threads(override=4), 4)
        self.assertEqual(config.get_optimal_threads(override=1), 1)

    def test_get_optimal_thread_count_auto(self):
        """Test automatic thread count detection"""
        mock_detector = MagicMock()

        # Test with 8 cores
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=8, optimal_threads=8
        )
        config = OptimalConfiguration(detector=mock_detector)
        self.assertEqual(config.get_optimal_threads(None), 8)

        # Test with 16 cores - should cap at 8
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=16, optimal_threads=8
        )
        config = OptimalConfiguration(detector=mock_detector)
        self.assertEqual(config.get_optimal_threads(None), 8)

        # Test with 2 cores
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=2, optimal_threads=2
        )
        config = OptimalConfiguration(detector=mock_detector)
        self.assertEqual(config.get_optimal_threads(None), 2)


class TestBatchSizeConfiguration(unittest.TestCase):
    """Test batch size configuration"""

    def test_batch_size_cpu(self):
        """Test batch size for CPU device"""
        mock_detector = MagicMock()
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=4, optimal_threads=4, gpu_memory=None
        )

        config = OptimalConfiguration(detector=mock_detector)

        # CPU batch sizes should be small
        self.assertEqual(config.get_optimal_batch_size("cpu", "tiny"), 4)
        self.assertEqual(config.get_optimal_batch_size("cpu", "base"), 2)
        self.assertEqual(config.get_optimal_batch_size("cpu", "large"), 1)

    def test_batch_size_cuda(self):
        """Test batch size for CUDA device with GPU memory"""
        mock_detector = MagicMock()
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=True, has_mps=False, cpu_cores=4, optimal_threads=4, gpu_memory=8000  # 8GB
        )

        config = OptimalConfiguration(detector=mock_detector)

        # CUDA with good GPU memory should have larger batch sizes
        batch_base = config.get_optimal_batch_size("cuda", "base")
        batch_tiny = config.get_optimal_batch_size("cuda", "tiny")

        # Larger model = smaller batch
        self.assertGreaterEqual(batch_tiny, batch_base)

    def test_batch_size_mps(self):
        """Test batch size for Apple MPS device"""
        mock_detector = MagicMock()
        mock_detector.get_capabilities.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=True, cpu_cores=8, optimal_threads=8
        )

        config = OptimalConfiguration(detector=mock_detector)

        # MPS has conservative batch sizes
        self.assertEqual(config.get_optimal_batch_size("mps", "tiny"), 16)
        self.assertEqual(config.get_optimal_batch_size("mps", "base"), 8)
        self.assertEqual(config.get_optimal_batch_size("mps", "large"), 1)


class TestTranscriberWorkerConfig(unittest.TestCase):
    """Test AudioTranscriber worker configuration"""

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    def test_transcriber_uses_optimal_workers(self, mock_caps):
        """Test that transcriber uses optimal worker configuration"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=8, optimal_threads=6
        )

        transcriber = AudioTranscriber()

        # Should use optimal thread count
        self.assertEqual(transcriber.num_workers, 6)

    @patch('cesar.device_detection.DeviceDetector.get_capabilities')
    def test_transcriber_custom_workers(self, mock_caps):
        """Test transcriber with custom worker count"""
        mock_caps.return_value = DeviceCapabilities(
            has_cuda=False, has_mps=False, cpu_cores=8, optimal_threads=6
        )

        transcriber = AudioTranscriber(num_workers=4)

        # Should use specified worker count
        self.assertEqual(transcriber.num_workers, 4)


if __name__ == "__main__":
    unittest.main()
