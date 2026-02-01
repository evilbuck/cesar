"""Unit tests for diarization module."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import os
import sys

from cesar.diarization import (
    SpeakerDiarizer,
    SpeakerSegment,
    DiarizationResult,
    DiarizationError,
    AuthenticationError,
)


class TestSpeakerDiarizer(unittest.TestCase):
    """Tests for SpeakerDiarizer class."""

    def test_init_with_token(self):
        """Test initialization with provided token."""
        diarizer = SpeakerDiarizer(hf_token="test_token")
        self.assertEqual(diarizer.hf_token, "test_token")

    def test_init_default_model(self):
        """Test default model name."""
        diarizer = SpeakerDiarizer()
        self.assertEqual(diarizer.model_name, "pyannote/speaker-diarization-3.1")

    def test_init_custom_model(self):
        """Test custom model name."""
        diarizer = SpeakerDiarizer(model_name="custom/model")
        self.assertEqual(diarizer.model_name, "custom/model")

    @patch.dict(os.environ, {"HF_TOKEN": "env_token"})
    def test_token_from_environment(self):
        """Test token resolution from environment variable."""
        diarizer = SpeakerDiarizer()
        self.assertEqual(diarizer.hf_token, "env_token")

    @patch.dict(os.environ, {}, clear=True)
    def test_token_from_cache(self):
        """Test token resolution from cached file."""
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value="cached_token\n"):
                diarizer = SpeakerDiarizer()
                self.assertEqual(diarizer.hf_token, "cached_token")

    @patch.dict(os.environ, {}, clear=True)
    def test_token_none_when_not_found(self):
        """Test token is None when not found."""
        with patch.object(Path, 'exists', return_value=False):
            diarizer = SpeakerDiarizer()
            self.assertIsNone(diarizer.hf_token)

    def test_load_pipeline_success(self):
        """Test successful pipeline loading."""
        # Import torch first to avoid import issues
        import torch

        mock_pipeline = Mock()
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        # Mock pyannote.audio module
        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class

        with patch.dict('sys.modules', {'pyannote': Mock(), 'pyannote.audio': mock_pyannote_audio}):
            with patch.object(torch.cuda, "is_available", return_value=False):
                diarizer = SpeakerDiarizer(hf_token="token")
                diarizer._load_pipeline()

        mock_pipeline_class.from_pretrained.assert_called_once_with(
            "pyannote/speaker-diarization-3.1",
            use_auth_token="token"
        )
        self.assertEqual(diarizer.pipeline, mock_pipeline)

    def test_load_pipeline_only_once(self):
        """Test pipeline is only loaded once."""
        import torch

        mock_pipeline = Mock()
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class

        with patch.dict('sys.modules', {'pyannote': Mock(), 'pyannote.audio': mock_pyannote_audio}):
            with patch.object(torch.cuda, "is_available", return_value=False):
                diarizer = SpeakerDiarizer(hf_token="token")
                diarizer._load_pipeline()
                diarizer._load_pipeline()

        # Should only be called once
        self.assertEqual(mock_pipeline_class.from_pretrained.call_count, 1)

    def test_load_pipeline_auth_error(self):
        """Test authentication error handling."""
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.side_effect = Exception("401 Unauthorized")

        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class

        with patch.dict('sys.modules', {'pyannote': Mock(), 'pyannote.audio': mock_pyannote_audio}):
            diarizer = SpeakerDiarizer(hf_token="bad_token")
            with self.assertRaises(AuthenticationError) as ctx:
                diarizer._load_pipeline()

        self.assertIn("HuggingFace authentication failed", str(ctx.exception))
        self.assertIn("hf.co/settings/tokens", str(ctx.exception))

    def test_load_pipeline_generic_error(self):
        """Test generic error handling."""
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.side_effect = Exception("Network error")

        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class

        with patch.dict('sys.modules', {'pyannote': Mock(), 'pyannote.audio': mock_pyannote_audio}):
            diarizer = SpeakerDiarizer(hf_token="token")
            with self.assertRaises(DiarizationError) as ctx:
                diarizer._load_pipeline()

        self.assertIn("Failed to load diarization model", str(ctx.exception))

    def test_gpu_detection(self):
        """Test GPU detection and pipeline movement."""
        import torch

        mock_pipeline = Mock()
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class

        with patch.dict('sys.modules', {'pyannote': Mock(), 'pyannote.audio': mock_pyannote_audio}):
            with patch.object(torch.cuda, "is_available", return_value=True):
                with patch.object(torch, "device") as mock_device:
                    diarizer = SpeakerDiarizer(hf_token="token")
                    diarizer._load_pipeline()

                    mock_pipeline.to.assert_called_once()

    def test_diarize_with_defaults(self):
        """Test diarization with default speaker range."""
        import torch

        # Set up mock pipeline
        mock_pipeline = Mock()
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        # Mock diarization result
        mock_turn = Mock()
        mock_turn.start = 0.0
        mock_turn.end = 5.0
        mock_diarization = Mock()
        mock_diarization.itertracks.return_value = [
            (mock_turn, None, "SPEAKER_00")
        ]
        mock_pipeline.return_value = mock_diarization

        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class

        with patch.dict('sys.modules', {'pyannote': Mock(), 'pyannote.audio': mock_pyannote_audio}):
            with patch.object(torch.cuda, "is_available", return_value=False):
                diarizer = SpeakerDiarizer(hf_token="token")
                result = diarizer.diarize("test.wav")

        # Check pipeline called with default min/max
        mock_pipeline.assert_called_with(
            "test.wav",
            min_speakers=1,
            max_speakers=5,
        )

        # Verify result
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(result.segments[0].start, 0.0)
        self.assertEqual(result.segments[0].end, 5.0)
        self.assertEqual(result.segments[0].speaker, "SPEAKER_00")
        self.assertEqual(result.speaker_count, 1)
        self.assertEqual(result.audio_duration, 5.0)

    def test_diarize_with_custom_speakers(self):
        """Test diarization with custom speaker range."""
        import torch

        mock_pipeline = Mock()
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        mock_turn = Mock()
        mock_turn.start = 0.0
        mock_turn.end = 5.0
        mock_diarization = Mock()
        mock_diarization.itertracks.return_value = [
            (mock_turn, None, "SPEAKER_00")
        ]
        mock_pipeline.return_value = mock_diarization

        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class

        with patch.dict('sys.modules', {'pyannote': Mock(), 'pyannote.audio': mock_pyannote_audio}):
            with patch.object(torch.cuda, "is_available", return_value=False):
                diarizer = SpeakerDiarizer(hf_token="token")
                result = diarizer.diarize("test.wav", min_speakers=2, max_speakers=4)

        mock_pipeline.assert_called_with(
            "test.wav",
            min_speakers=2,
            max_speakers=4,
        )

    def test_diarize_multiple_speakers(self):
        """Test diarization with multiple speakers."""
        import torch

        mock_pipeline = Mock()
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        # Mock multiple speaker segments
        mock_turn1 = Mock()
        mock_turn1.start = 0.0
        mock_turn1.end = 5.0
        mock_turn2 = Mock()
        mock_turn2.start = 5.0
        mock_turn2.end = 10.0
        mock_turn3 = Mock()
        mock_turn3.start = 10.0
        mock_turn3.end = 15.0

        mock_diarization = Mock()
        mock_diarization.itertracks.return_value = [
            (mock_turn1, None, "SPEAKER_00"),
            (mock_turn2, None, "SPEAKER_01"),
            (mock_turn3, None, "SPEAKER_00"),
        ]
        mock_pipeline.return_value = mock_diarization

        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class

        with patch.dict('sys.modules', {'pyannote': Mock(), 'pyannote.audio': mock_pyannote_audio}):
            with patch.object(torch.cuda, "is_available", return_value=False):
                diarizer = SpeakerDiarizer(hf_token="token")
                result = diarizer.diarize("test.wav")

        # Verify result
        self.assertEqual(len(result.segments), 3)
        self.assertEqual(result.speaker_count, 2)
        self.assertEqual(result.audio_duration, 15.0)

    def test_diarize_with_progress_callback(self):
        """Test diarization with progress callback."""
        import torch

        mock_pipeline = Mock()
        mock_pipeline_class = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        mock_turn = Mock()
        mock_turn.start = 0.0
        mock_turn.end = 5.0
        mock_diarization = Mock()
        mock_diarization.itertracks.return_value = [
            (mock_turn, None, "SPEAKER_00")
        ]
        mock_pipeline.return_value = mock_diarization

        # Track progress callback calls
        progress_calls = []
        def progress_callback(msg):
            progress_calls.append(msg)

        # Mock ProgressHook
        mock_progress_hook = MagicMock()
        mock_hook_module = Mock()
        mock_hook_module.ProgressHook = mock_progress_hook

        mock_pipelines = Mock()
        mock_pipelines.utils = Mock()
        mock_pipelines.utils.hook = mock_hook_module

        mock_pyannote_audio = Mock()
        mock_pyannote_audio.Pipeline = mock_pipeline_class
        mock_pyannote_audio.pipelines = mock_pipelines

        with patch.dict('sys.modules', {
            'pyannote': Mock(),
            'pyannote.audio': mock_pyannote_audio,
            'pyannote.audio.pipelines': mock_pipelines,
            'pyannote.audio.pipelines.utils': mock_pipelines.utils,
            'pyannote.audio.pipelines.utils.hook': mock_hook_module,
        }):
            with patch.object(torch.cuda, "is_available", return_value=False):
                diarizer = SpeakerDiarizer(hf_token="token")
                result = diarizer.diarize("test.wav", progress_callback=progress_callback)

        # Verify callback was called
        self.assertGreater(len(progress_calls), 0)
        self.assertIn("Detecting speakers", progress_calls[0])


class TestDiarizationResult(unittest.TestCase):
    """Tests for DiarizationResult dataclass."""

    def test_result_creation(self):
        """Test creating a DiarizationResult."""
        segments = [
            SpeakerSegment(start=0.0, end=5.0, speaker="SPEAKER_00"),
            SpeakerSegment(start=5.0, end=10.0, speaker="SPEAKER_01"),
        ]
        result = DiarizationResult(
            segments=segments,
            speaker_count=2,
            audio_duration=10.0
        )

        self.assertEqual(len(result.segments), 2)
        self.assertEqual(result.speaker_count, 2)
        self.assertEqual(result.audio_duration, 10.0)

    def test_segment_creation(self):
        """Test creating a SpeakerSegment."""
        segment = SpeakerSegment(start=1.5, end=3.7, speaker="SPEAKER_00")

        self.assertEqual(segment.start, 1.5)
        self.assertEqual(segment.end, 3.7)
        self.assertEqual(segment.speaker, "SPEAKER_00")


if __name__ == "__main__":
    unittest.main()
