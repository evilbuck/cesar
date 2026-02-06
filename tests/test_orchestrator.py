"""
Unit tests for TranscriptionOrchestrator with WhisperXPipeline.

Tests the new WhisperXPipeline-based orchestrator with proper fallback
behavior when diarization fails (WX-09 requirement).
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import json

from cesar.orchestrator import TranscriptionOrchestrator, OrchestrationResult
from cesar.transcriber import AudioTranscriber, TranscriptionSegment
from cesar.diarization import DiarizationError, AuthenticationError
from cesar.whisperx_wrapper import WhisperXPipeline, WhisperXSegment
from cesar.transcript_formatter import MarkdownTranscriptFormatter


class TestOrchestrationResult(unittest.TestCase):
    """Test OrchestrationResult dataclass properties."""

    def test_total_processing_time_with_diarization(self):
        """Test total_processing_time calculation with diarization."""
        result = OrchestrationResult(
            output_path=Path("output.md"),
            speakers_detected=2,
            audio_duration=100.0,
            transcription_time=10.0,
            diarization_time=5.0,
            formatting_time=1.0,
            diarization_succeeded=True
        )
        self.assertEqual(result.total_processing_time, 16.0)

    def test_total_processing_time_without_diarization(self):
        """Test total_processing_time calculation without diarization."""
        result = OrchestrationResult(
            output_path=Path("output.txt"),
            speakers_detected=0,
            audio_duration=100.0,
            transcription_time=10.0,
            diarization_time=None,
            formatting_time=1.0,
            diarization_succeeded=False
        )
        self.assertEqual(result.total_processing_time, 11.0)

    def test_speed_ratio(self):
        """Test speed_ratio calculation."""
        result = OrchestrationResult(
            output_path=Path("output.md"),
            speakers_detected=2,
            audio_duration=100.0,
            transcription_time=10.0,
            diarization_time=5.0,
            formatting_time=1.0,
            diarization_succeeded=True
        )
        # 100 seconds audio / 16 seconds processing = 6.25x
        self.assertAlmostEqual(result.speed_ratio, 6.25, places=2)

    def test_speed_ratio_zero_time(self):
        """Test speed_ratio with zero processing time."""
        result = OrchestrationResult(
            output_path=Path("output.md"),
            speakers_detected=0,
            audio_duration=100.0,
            transcription_time=0.0,
            diarization_time=None,
            formatting_time=0.0,
            diarization_succeeded=False
        )
        self.assertEqual(result.speed_ratio, 0.0)


class TestTranscriptionOrchestrator(unittest.TestCase):
    """Test TranscriptionOrchestrator class with WhisperXPipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.audio_path = Path(self.temp_dir) / "audio.mp3"
        self.output_path = Path(self.temp_dir) / "output.txt"

        # Create mock pipeline
        self.pipeline = MagicMock(spec=WhisperXPipeline)
        self.pipeline.transcribe_and_diarize.return_value = (
            [
                WhisperXSegment(start=0.0, end=5.0, speaker="SPEAKER_00", text="First segment"),
                WhisperXSegment(start=5.0, end=10.0, speaker="SPEAKER_01", text="Second segment"),
            ],
            2,  # speaker_count
            10.0  # audio_duration
        )

        # Create mock transcriber for fallback tests
        self.transcriber = MagicMock(spec=AudioTranscriber)
        self.transcriber.transcribe_to_segments.return_value = (
            [
                TranscriptionSegment(0.0, 5.0, "First segment"),
                TranscriptionSegment(5.0, 10.0, "Second segment"),
            ],
            {
                'language': 'en',
                'language_probability': 0.99,
                'audio_duration': 10.0,
                'processing_time': 2.0,
                'speed_ratio': 5.0,
                'segment_count': 2
            }
        )

        # Create mock formatter
        self.formatter = MagicMock(spec=MarkdownTranscriptFormatter)
        self.formatter.format.return_value = "# Transcript\n\n### Speaker 1\nFirst segment"

    def test_orchestrate_success_with_diarization(self):
        """Test successful orchestration with WhisperXPipeline diarization."""
        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True
        )

        # Verify pipeline called
        self.pipeline.transcribe_and_diarize.assert_called_once()

        # Verify formatter called
        self.formatter.format.assert_called_once()

        # Verify result
        self.assertTrue(result.diarization_succeeded)
        self.assertEqual(result.speakers_detected, 2)
        self.assertEqual(result.audio_duration, 10.0)
        self.assertIsNotNone(result.diarization_time)
        self.assertTrue(str(result.output_path).endswith('.md'))

    def test_orchestrate_diarization_disabled(self):
        """Test orchestration with diarization disabled uses transcriber."""
        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=False
        )

        # Verify pipeline NOT called (diarization disabled)
        self.pipeline.transcribe_and_diarize.assert_not_called()

        # Verify transcriber called for plain transcription
        self.transcriber.transcribe_to_segments.assert_called_once()

        # Verify result
        self.assertFalse(result.diarization_succeeded)
        self.assertEqual(result.speakers_detected, 0)
        self.assertIsNone(result.diarization_time)
        self.assertTrue(str(result.output_path).endswith('.txt'))

        # Verify plain transcript was saved
        with open(result.output_path, 'r') as f:
            content = f.read()
            self.assertIn("Speaker detection unavailable", content)
            self.assertIn("First segment", content)

    def test_orchestrate_diarization_fails_with_fallback(self):
        """Test graceful fallback when diarization fails (WX-09).

        IMPORTANT: This test MUST pass (not expectedFailure) per WX-09 requirement.
        When diarization fails and a transcriber is available, the orchestrator
        should fall back to plain transcription.
        """
        # Make pipeline raise DiarizationError
        self.pipeline.transcribe_and_diarize.side_effect = DiarizationError("Model failed")

        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,  # Fallback transcriber provided
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True
        )

        # Verify pipeline was attempted
        self.pipeline.transcribe_and_diarize.assert_called_once()

        # Verify transcriber was called as fallback
        self.transcriber.transcribe_to_segments.assert_called_once()

        # Verify result indicates fallback
        self.assertFalse(result.diarization_succeeded)
        self.assertEqual(result.speakers_detected, 0)
        self.assertIsNone(result.diarization_time)
        self.assertTrue(str(result.output_path).endswith('.txt'))

        # Verify plain transcript was saved
        with open(result.output_path, 'r') as f:
            content = f.read()
            self.assertIn("Speaker detection unavailable", content)
            self.assertIn("First segment", content)

    def test_orchestrate_diarization_fails_no_fallback(self):
        """Test DiarizationError re-raised when no fallback transcriber."""
        # Make pipeline raise DiarizationError
        self.pipeline.transcribe_and_diarize.side_effect = DiarizationError("Model failed")

        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=None,  # No fallback
            formatter=self.formatter
        )

        with self.assertRaises(DiarizationError) as ctx:
            orchestrator.orchestrate(
                audio_path=self.audio_path,
                output_path=self.output_path,
                enable_diarization=True
            )

        self.assertIn("Model failed", str(ctx.exception))
        self.assertIn("no fallback", str(ctx.exception).lower())

    def test_orchestrate_authentication_error_propagates(self):
        """Test that AuthenticationError propagates (not caught for fallback)."""
        # Make pipeline raise AuthenticationError
        self.pipeline.transcribe_and_diarize.side_effect = AuthenticationError(
            "HuggingFace authentication failed"
        )

        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,  # Fallback available but should not be used
            formatter=self.formatter
        )

        with self.assertRaises(AuthenticationError) as ctx:
            orchestrator.orchestrate(
                audio_path=self.audio_path,
                output_path=self.output_path,
                enable_diarization=True
            )

        self.assertIn("authentication", str(ctx.exception).lower())

        # Transcriber should NOT have been called (auth error should propagate)
        self.transcriber.transcribe_to_segments.assert_not_called()

    def test_orchestrate_progress_callback(self):
        """Test progress callback receives correct steps and percentages."""
        progress_calls = []

        def progress_callback(step, percentage):
            progress_calls.append((step, percentage))

        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True,
            progress_callback=progress_callback
        )

        # Should see start, pipeline complete, formatting, and complete steps
        step_names = [call[0] for call in progress_calls]
        self.assertTrue(len(progress_calls) > 0)

        # Verify progress goes from 0 to 100
        percentages = [call[1] for call in progress_calls]
        self.assertEqual(percentages[0], 0.0)  # First call
        self.assertEqual(percentages[-1], 100.0)  # Last call

    def test_orchestrate_no_pipeline_no_transcriber_raises(self):
        """Test ValueError when neither pipeline nor transcriber provided."""
        orchestrator = TranscriptionOrchestrator(
            pipeline=None,
            transcriber=None,
            formatter=self.formatter
        )

        with self.assertRaises(ValueError) as ctx:
            orchestrator.orchestrate(
                audio_path=self.audio_path,
                output_path=self.output_path,
                enable_diarization=True
            )

        self.assertIn("pipeline", str(ctx.exception).lower())
        self.assertIn("transcriber", str(ctx.exception).lower())

    def test_orchestrate_keep_intermediate_files(self):
        """Test intermediate files are saved when keep_intermediate=True."""
        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True,
            keep_intermediate=True
        )

        # Verify intermediate diarization file exists
        diarization_path = self.output_path.parent / f"{self.output_path.stem}_diarization.json"
        self.assertTrue(diarization_path.exists())
        with open(diarization_path, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['speaker_count'], 2)
            self.assertEqual(len(data['segments']), 2)

    def test_orchestrate_file_extension_override(self):
        """Test file extension is changed based on diarization success."""
        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        # Pass output_path with .txt extension
        output_txt = Path(self.temp_dir) / "output.txt"

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=output_txt,
            enable_diarization=True
        )

        # Should be changed to .md
        self.assertTrue(str(result.output_path).endswith('.md'))
        self.assertTrue(result.output_path.exists())

    def test_orchestrate_formatting_error_fallback(self):
        """Test fallback to plain text when formatting fails."""
        # Mock formatter to raise error
        self.formatter.format.side_effect = Exception("Formatting failed")

        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True
        )

        # Should fall back to plain .txt
        self.assertFalse(result.diarization_succeeded)
        self.assertTrue(str(result.output_path).endswith('.txt'))
        self.assertTrue(result.output_path.exists())

    def test_orchestrate_creates_formatter_if_not_provided(self):
        """Test that formatter is created automatically if not provided."""
        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,
            formatter=None  # No formatter provided
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True
        )

        # Should still succeed and create .md output
        self.assertTrue(result.diarization_succeeded)
        self.assertTrue(str(result.output_path).endswith('.md'))
        self.assertTrue(result.output_path.exists())

    def test_orchestrate_passes_min_max_speakers_to_pipeline(self):
        """Test that min/max speakers are passed to pipeline."""
        orchestrator = TranscriptionOrchestrator(
            pipeline=self.pipeline,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True,
            min_speakers=2,
            max_speakers=4
        )

        # Verify pipeline called with correct speaker limits
        call_args = self.pipeline.transcribe_and_diarize.call_args
        self.assertEqual(call_args.kwargs['min_speakers'], 2)
        self.assertEqual(call_args.kwargs['max_speakers'], 4)

    def test_orchestrate_only_transcriber_no_pipeline(self):
        """Test orchestration works with only transcriber (no pipeline)."""
        orchestrator = TranscriptionOrchestrator(
            pipeline=None,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=False  # Must be False when no pipeline
        )

        # Verify transcriber called
        self.transcriber.transcribe_to_segments.assert_called_once()

        # Should save plain transcript
        self.assertFalse(result.diarization_succeeded)
        self.assertTrue(str(result.output_path).endswith('.txt'))


if __name__ == '__main__':
    unittest.main()
