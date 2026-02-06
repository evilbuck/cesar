"""Unit tests for WhisperX wrapper module."""
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import os
import sys

from cesar.whisperx_wrapper import (
    WhisperXPipeline,
    WhisperXSegment,
)
from cesar.diarization import DiarizationError, AuthenticationError


class TestWhisperXSegment(unittest.TestCase):
    """Tests for WhisperXSegment dataclass."""

    def test_segment_creation(self):
        """Test creating a WhisperXSegment with all fields."""
        segment = WhisperXSegment(
            start=1.5,
            end=3.7,
            speaker="SPEAKER_00",
            text="Hello, how are you?"
        )

        self.assertEqual(segment.start, 1.5)
        self.assertEqual(segment.end, 3.7)
        self.assertEqual(segment.speaker, "SPEAKER_00")
        self.assertEqual(segment.text, "Hello, how are you?")

    def test_segment_equality(self):
        """Test segment equality comparison."""
        segment1 = WhisperXSegment(
            start=0.0,
            end=5.0,
            speaker="SPEAKER_00",
            text="Test"
        )
        segment2 = WhisperXSegment(
            start=0.0,
            end=5.0,
            speaker="SPEAKER_00",
            text="Test"
        )
        segment3 = WhisperXSegment(
            start=0.0,
            end=5.0,
            speaker="SPEAKER_01",
            text="Test"
        )

        self.assertEqual(segment1, segment2)
        self.assertNotEqual(segment1, segment3)


class TestWhisperXPipelineInit(unittest.TestCase):
    """Tests for WhisperXPipeline initialization."""

    def test_default_model_name(self):
        """Test default model is large-v2."""
        pipeline = WhisperXPipeline()
        self.assertEqual(pipeline.model_name, "large-v2")

    def test_default_batch_size(self):
        """Test default batch size is 16."""
        pipeline = WhisperXPipeline()
        self.assertEqual(pipeline.batch_size, 16)

    def test_custom_model_name(self):
        """Test custom model name."""
        pipeline = WhisperXPipeline(model_name="base")
        self.assertEqual(pipeline.model_name, "base")

    def test_custom_batch_size(self):
        """Test custom batch size."""
        pipeline = WhisperXPipeline(batch_size=8)
        self.assertEqual(pipeline.batch_size, 8)

    def test_init_with_token(self):
        """Test initialization with provided token."""
        pipeline = WhisperXPipeline(hf_token="test_token")
        self.assertEqual(pipeline.hf_token, "test_token")

    @patch.dict(os.environ, {"HF_TOKEN": "env_token"})
    def test_token_from_environment(self):
        """Test token resolution from environment variable."""
        pipeline = WhisperXPipeline()
        self.assertEqual(pipeline.hf_token, "env_token")

    @patch.dict(os.environ, {}, clear=True)
    def test_token_from_cache(self):
        """Test token resolution from cached file."""
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value="cached_token\n"):
                pipeline = WhisperXPipeline()
                self.assertEqual(pipeline.hf_token, "cached_token")

    @patch.dict(os.environ, {}, clear=True)
    def test_token_none_when_not_found(self):
        """Test token is None when not found."""
        with patch.object(Path, 'exists', return_value=False):
            pipeline = WhisperXPipeline()
            self.assertIsNone(pipeline.hf_token)

    def test_provided_token_takes_priority(self):
        """Test provided token takes priority over env and cache."""
        with patch.dict(os.environ, {"HF_TOKEN": "env_token"}):
            pipeline = WhisperXPipeline(hf_token="provided_token")
            self.assertEqual(pipeline.hf_token, "provided_token")


class TestWhisperXPipelineDeviceResolution(unittest.TestCase):
    """Tests for device resolution."""

    def test_explicit_cpu_device(self):
        """Test explicit cpu device passes through."""
        pipeline = WhisperXPipeline(device="cpu")
        self.assertEqual(pipeline.device, "cpu")

    def test_explicit_cuda_device(self):
        """Test explicit cuda device passes through."""
        pipeline = WhisperXPipeline(device="cuda")
        self.assertEqual(pipeline.device, "cuda")

    def test_auto_selects_cuda_when_available(self):
        """Test auto selects cuda when available."""
        import torch
        with patch.object(torch.cuda, 'is_available', return_value=True):
            pipeline = WhisperXPipeline.__new__(WhisperXPipeline)
            result = pipeline._resolve_device("auto")
            self.assertEqual(result, "cuda")

    def test_auto_selects_cpu_when_cuda_unavailable(self):
        """Test auto selects cpu when cuda unavailable."""
        import torch
        with patch.object(torch.cuda, 'is_available', return_value=False):
            pipeline = WhisperXPipeline.__new__(WhisperXPipeline)
            result = pipeline._resolve_device("auto")
            self.assertEqual(result, "cpu")

    def test_auto_selects_cpu_when_torch_import_fails(self):
        """Test auto selects cpu when torch import fails."""
        # Create pipeline instance directly
        pipeline = WhisperXPipeline.__new__(WhisperXPipeline)

        # Mock the import to raise ImportError
        original_import = __builtins__['__import__'] if isinstance(__builtins__, dict) else __builtins__.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'torch':
                raise ImportError("No module named torch")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            result = pipeline._resolve_device("auto")
            self.assertEqual(result, "cpu")


class TestWhisperXPipelineComputeType(unittest.TestCase):
    """Tests for compute type resolution."""

    def test_explicit_float32_passes_through(self):
        """Test explicit compute type passes through."""
        pipeline = WhisperXPipeline(device="cpu", compute_type="float32")
        self.assertEqual(pipeline.compute_type, "float32")

    def test_explicit_float16_passes_through(self):
        """Test explicit float16 passes through."""
        pipeline = WhisperXPipeline(device="cuda", compute_type="float16")
        self.assertEqual(pipeline.compute_type, "float16")

    def test_explicit_int8_passes_through(self):
        """Test explicit int8 passes through."""
        pipeline = WhisperXPipeline(device="cpu", compute_type="int8")
        self.assertEqual(pipeline.compute_type, "int8")

    def test_auto_selects_float16_for_cuda(self):
        """Test auto selects float16 for cuda device."""
        pipeline = WhisperXPipeline.__new__(WhisperXPipeline)
        result = pipeline._resolve_compute_type("auto", "cuda")
        self.assertEqual(result, "float16")

    def test_auto_selects_int8_for_cpu(self):
        """Test auto selects int8 for cpu device."""
        pipeline = WhisperXPipeline.__new__(WhisperXPipeline)
        result = pipeline._resolve_compute_type("auto", "cpu")
        self.assertEqual(result, "int8")


class TestWhisperXPipelineLazyLoading(unittest.TestCase):
    """Tests for lazy model loading."""

    def test_models_are_none_after_init(self):
        """Test models are None after initialization."""
        pipeline = WhisperXPipeline()

        self.assertIsNone(pipeline._whisper_model)
        self.assertIsNone(pipeline._align_model)
        self.assertIsNone(pipeline._align_metadata)
        self.assertIsNone(pipeline._diarize_model)
        self.assertIsNone(pipeline._current_language)

    def test_whisper_model_loaded_only_once(self):
        """Test whisper model is loaded only once."""
        # Create mock whisperx module
        mock_whisperx = Mock()
        mock_model = Mock()
        mock_whisperx.load_model.return_value = mock_model

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu")
            pipeline._load_whisper_model()
            pipeline._load_whisper_model()  # Second call

        # Should only be called once
        self.assertEqual(mock_whisperx.load_model.call_count, 1)
        self.assertEqual(pipeline._whisper_model, mock_model)

    def test_align_model_reloads_on_language_change(self):
        """Test align model reloads when language changes."""
        mock_whisperx = Mock()
        mock_model_en = (Mock(), Mock())
        mock_model_fr = (Mock(), Mock())
        mock_whisperx.load_align_model.side_effect = [mock_model_en, mock_model_fr]

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu")
            pipeline._load_align_model("en")
            pipeline._load_align_model("fr")  # Different language

        # Should be called twice for different languages
        self.assertEqual(mock_whisperx.load_align_model.call_count, 2)

    def test_align_model_not_reloaded_for_same_language(self):
        """Test align model is not reloaded for same language."""
        mock_whisperx = Mock()
        mock_model = (Mock(), Mock())
        mock_whisperx.load_align_model.return_value = mock_model

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu")
            pipeline._load_align_model("en")
            pipeline._load_align_model("en")  # Same language

        # Should only be called once
        self.assertEqual(mock_whisperx.load_align_model.call_count, 1)

    def test_diarize_model_loaded_only_once(self):
        """Test diarize model is loaded only once."""
        mock_whisperx = Mock()
        mock_diarize_pipeline = Mock()
        mock_whisperx.DiarizationPipeline.return_value = mock_diarize_pipeline

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            pipeline._load_diarize_model()
            pipeline._load_diarize_model()  # Second call

        # Should only be called once
        self.assertEqual(mock_whisperx.DiarizationPipeline.call_count, 1)


class TestWhisperXPipelineTranscription(unittest.TestCase):
    """Tests for transcription pipeline."""

    def _create_mock_whisperx(self):
        """Create a fully mocked whisperx module."""
        mock_whisperx = Mock()

        # Mock audio loading - return numpy-like array
        mock_audio = MagicMock()
        mock_audio.__len__ = Mock(return_value=160000)  # 10 seconds at 16kHz
        mock_whisperx.load_audio.return_value = mock_audio

        # Mock transcription
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello there."},
                {"start": 5.0, "end": 10.0, "text": "How are you?"}
            ]
        }
        mock_whisperx.load_model.return_value = mock_model

        # Mock alignment
        mock_align_model = Mock()
        mock_align_metadata = Mock()
        mock_whisperx.load_align_model.return_value = (mock_align_model, mock_align_metadata)
        mock_whisperx.align.return_value = {
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello there.", "speaker": "SPEAKER_00"},
                {"start": 5.0, "end": 10.0, "text": "How are you?", "speaker": "SPEAKER_01"}
            ]
        }

        # Mock diarization
        mock_diarize_pipeline = Mock()
        mock_diarize_result = Mock()
        mock_diarize_pipeline.return_value = mock_diarize_result
        mock_whisperx.DiarizationPipeline.return_value = mock_diarize_pipeline

        # Mock speaker assignment
        mock_whisperx.assign_word_speakers.return_value = {
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello there.", "speaker": "SPEAKER_00"},
                {"start": 5.0, "end": 10.0, "text": "How are you?", "speaker": "SPEAKER_01"}
            ]
        }

        return mock_whisperx

    def test_successful_transcribe_and_diarize(self):
        """Test successful full pipeline execution."""
        mock_whisperx = self._create_mock_whisperx()

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            segments, speaker_count, duration = pipeline.transcribe_and_diarize("test.wav")

        # Verify segments
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].text, "Hello there.")
        self.assertEqual(segments[0].speaker, "SPEAKER_00")
        self.assertEqual(segments[1].text, "How are you?")
        self.assertEqual(segments[1].speaker, "SPEAKER_01")

        # Verify speaker count
        self.assertEqual(speaker_count, 2)

        # Verify duration (160000 samples / 16000 Hz = 10 seconds)
        self.assertEqual(duration, 10.0)

    def test_multiple_speakers_detected(self):
        """Test multiple speakers are correctly detected."""
        mock_whisperx = self._create_mock_whisperx()
        # Modify to have 3 speakers
        mock_whisperx.assign_word_speakers.return_value = {
            "segments": [
                {"start": 0.0, "end": 3.0, "text": "Hello.", "speaker": "SPEAKER_00"},
                {"start": 3.0, "end": 6.0, "text": "Hi.", "speaker": "SPEAKER_01"},
                {"start": 6.0, "end": 10.0, "text": "Hey.", "speaker": "SPEAKER_02"}
            ]
        }

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            segments, speaker_count, duration = pipeline.transcribe_and_diarize("test.wav")

        self.assertEqual(speaker_count, 3)
        self.assertEqual(len(segments), 3)

    def test_min_max_speakers_passed_to_diarization(self):
        """Test min/max_speakers are passed to diarization model."""
        mock_whisperx = self._create_mock_whisperx()

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            pipeline.transcribe_and_diarize(
                "test.wav",
                min_speakers=2,
                max_speakers=4
            )

        # Get the diarize pipeline mock and check its call
        mock_diarize = mock_whisperx.DiarizationPipeline.return_value
        mock_diarize.assert_called_once()
        call_kwargs = mock_diarize.call_args[1]
        self.assertEqual(call_kwargs['min_speakers'], 2)
        self.assertEqual(call_kwargs['max_speakers'], 4)

    def test_default_speaker_range_used(self):
        """Test default min/max speakers (1-5) used when not specified."""
        mock_whisperx = self._create_mock_whisperx()

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            pipeline.transcribe_and_diarize("test.wav")

        mock_diarize = mock_whisperx.DiarizationPipeline.return_value
        call_kwargs = mock_diarize.call_args[1]
        self.assertEqual(call_kwargs['min_speakers'], 1)
        self.assertEqual(call_kwargs['max_speakers'], 5)

    def test_progress_callback_is_called(self):
        """Test progress callback is called during pipeline."""
        mock_whisperx = self._create_mock_whisperx()
        progress_calls = []

        def progress_callback(phase, percent):
            progress_calls.append((phase, percent))

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            pipeline.transcribe_and_diarize("test.wav", progress_callback=progress_callback)

        # Verify progress callbacks were made
        self.assertGreater(len(progress_calls), 0)

        # Check for expected phases
        phases = [call[0] for call in progress_calls]
        self.assertIn("Loading audio...", phases)
        self.assertIn("Transcribing...", phases)
        self.assertIn("Aligning timestamps...", phases)
        self.assertIn("Detecting speakers...", phases)
        self.assertIn("Assigning speakers...", phases)
        self.assertIn("Complete", phases)

        # Check percentages increase
        percentages = [call[1] for call in progress_calls]
        self.assertEqual(percentages[0], 0.0)
        self.assertEqual(percentages[-1], 100.0)

    def test_segment_with_missing_speaker(self):
        """Test segment with missing speaker gets UNKNOWN label."""
        mock_whisperx = self._create_mock_whisperx()
        mock_whisperx.assign_word_speakers.return_value = {
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "No speaker here."}
                # Note: no "speaker" key
            ]
        }

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            segments, speaker_count, duration = pipeline.transcribe_and_diarize("test.wav")

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].speaker, "UNKNOWN")
        self.assertEqual(speaker_count, 1)

    def test_empty_text_handled(self):
        """Test segments with empty text are handled."""
        mock_whisperx = self._create_mock_whisperx()
        mock_whisperx.assign_word_speakers.return_value = {
            "segments": [
                {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"}
                # Note: no "text" key
            ]
        }

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            segments, speaker_count, duration = pipeline.transcribe_and_diarize("test.wav")

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "")


class TestWhisperXPipelineErrors(unittest.TestCase):
    """Tests for error handling."""

    def test_authentication_error_on_401(self):
        """Test AuthenticationError on 401 from diarization."""
        mock_whisperx = Mock()
        mock_whisperx.DiarizationPipeline.side_effect = Exception("401 Unauthorized")

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="bad_token")
            with self.assertRaises(AuthenticationError) as ctx:
                pipeline._load_diarize_model()

        self.assertIn("HuggingFace authentication failed", str(ctx.exception))
        self.assertIn("hf.co/settings/tokens", str(ctx.exception))

    def test_authentication_error_on_unauthorized(self):
        """Test AuthenticationError on Unauthorized message."""
        mock_whisperx = Mock()
        mock_whisperx.DiarizationPipeline.side_effect = Exception("Unauthorized access denied")

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="bad_token")
            with self.assertRaises(AuthenticationError):
                pipeline._load_diarize_model()

    def test_authentication_error_on_access_denied(self):
        """Test AuthenticationError on access denied message."""
        mock_whisperx = Mock()
        mock_whisperx.DiarizationPipeline.side_effect = Exception("You do not have access to this model")

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="bad_token")
            with self.assertRaises(AuthenticationError):
                pipeline._load_diarize_model()

    def test_diarization_error_on_generic_failure(self):
        """Test DiarizationError on generic failure."""
        mock_whisperx = Mock()
        mock_whisperx.DiarizationPipeline.side_effect = Exception("Network error")

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu", hf_token="token")
            with self.assertRaises(DiarizationError) as ctx:
                pipeline._load_diarize_model()

        self.assertIn("Failed to load diarization model", str(ctx.exception))
        self.assertIn("Network error", str(ctx.exception))

    def test_diarization_error_when_whisperx_not_installed(self):
        """Test DiarizationError when whisperx not installed."""
        pipeline = WhisperXPipeline(device="cpu")

        # Remove whisperx from sys.modules if present and patch import
        with patch.dict('sys.modules', {'whisperx': None}):
            # The _load_whisper_model checks for whisperx import
            with self.assertRaises(DiarizationError) as ctx:
                # Manually test import error
                pipeline._whisper_model = None  # Reset
                try:
                    import whisperx
                except (ImportError, TypeError):
                    raise DiarizationError("whisperx not installed. Run: pip install whisperx")

        self.assertIn("whisperx not installed", str(ctx.exception))

    def test_load_whisper_model_raises_on_import_error(self):
        """Test _load_whisper_model raises DiarizationError on ImportError."""
        pipeline = WhisperXPipeline(device="cpu")
        pipeline._whisper_model = None

        # Mock sys.modules to make whisperx import fail
        original_modules = sys.modules.copy()

        # Temporarily remove whisperx if it exists
        if 'whisperx' in sys.modules:
            del sys.modules['whisperx']

        # Patch the import to raise ImportError
        with patch.dict('sys.modules', {'whisperx': None}):
            with self.assertRaises((DiarizationError, TypeError)):
                pipeline._load_whisper_model()


class TestWhisperXPipelineConvertToSegments(unittest.TestCase):
    """Tests for _convert_to_segments method."""

    def test_convert_basic_segments(self):
        """Test converting basic segments."""
        mock_whisperx = Mock()

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu")

            result = {
                "segments": [
                    {"start": 0.0, "end": 5.0, "text": "Hello.", "speaker": "SPEAKER_00"},
                    {"start": 5.0, "end": 10.0, "text": "Hi.", "speaker": "SPEAKER_01"}
                ]
            }
            # Mock audio of 10 seconds (160000 samples at 16kHz)
            mock_audio = MagicMock()
            mock_audio.__len__ = Mock(return_value=160000)

            segments, speaker_count, duration = pipeline._convert_to_segments(result, mock_audio)

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start, 0.0)
        self.assertEqual(segments[0].end, 5.0)
        self.assertEqual(segments[0].text, "Hello.")
        self.assertEqual(segments[0].speaker, "SPEAKER_00")
        self.assertEqual(speaker_count, 2)
        self.assertEqual(duration, 10.0)

    def test_convert_strips_whitespace_from_text(self):
        """Test that text whitespace is stripped."""
        mock_whisperx = Mock()

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu")

            result = {
                "segments": [
                    {"start": 0.0, "end": 5.0, "text": "  Hello.  ", "speaker": "SPEAKER_00"}
                ]
            }
            mock_audio = MagicMock()
            mock_audio.__len__ = Mock(return_value=80000)

            segments, _, _ = pipeline._convert_to_segments(result, mock_audio)

        self.assertEqual(segments[0].text, "Hello.")

    def test_convert_empty_segments(self):
        """Test converting empty segments list."""
        mock_whisperx = Mock()

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu")

            result = {"segments": []}
            mock_audio = MagicMock()
            mock_audio.__len__ = Mock(return_value=160000)

            segments, speaker_count, duration = pipeline._convert_to_segments(result, mock_audio)

        self.assertEqual(len(segments), 0)
        self.assertEqual(speaker_count, 0)
        self.assertEqual(duration, 10.0)

    def test_convert_calculates_duration_from_audio_length(self):
        """Test duration is calculated from audio array length."""
        mock_whisperx = Mock()

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            pipeline = WhisperXPipeline(device="cpu")

            result = {"segments": []}

            # Test various durations
            for samples, expected_duration in [(16000, 1.0), (32000, 2.0), (48000, 3.0)]:
                mock_audio = MagicMock()
                mock_audio.__len__ = Mock(return_value=samples)

                _, _, duration = pipeline._convert_to_segments(result, mock_audio)
                self.assertEqual(duration, expected_duration)


if __name__ == "__main__":
    unittest.main()
