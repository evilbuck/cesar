"""
Unit tests for TranscriptionOrchestrator.
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import tempfile
import json

from cesar.orchestrator import TranscriptionOrchestrator, OrchestrationResult
from cesar.transcriber import AudioTranscriber
from cesar.diarization import SpeakerDiarizer, DiarizationError, DiarizationResult, SpeakerSegment
from cesar.timestamp_aligner import TranscriptionSegment, AlignedSegment
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
    """Test TranscriptionOrchestrator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.audio_path = Path(self.temp_dir) / "audio.mp3"
        self.output_path = Path(self.temp_dir) / "output.txt"

        # Create mock transcriber
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

        # Create mock diarizer
        self.diarizer = MagicMock(spec=SpeakerDiarizer)
        self.diarizer.diarize.return_value = DiarizationResult(
            segments=[
                SpeakerSegment(0.0, 5.0, "SPEAKER_00"),
                SpeakerSegment(5.0, 10.0, "SPEAKER_01"),
            ],
            speaker_count=2,
            audio_duration=10.0
        )

        # Create mock formatter
        self.formatter = MagicMock(spec=MarkdownTranscriptFormatter)
        self.formatter.format.return_value = "# Transcript\n\n### Speaker 1\nFirst segment"

    def test_orchestrate_success_with_diarization(self):
        """Test successful orchestration with diarization."""
        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True
        )

        # Verify transcriber called
        self.transcriber.transcribe_to_segments.assert_called_once_with(
            str(self.audio_path),
            progress_callback=unittest.mock.ANY
        )

        # Verify diarizer called
        self.diarizer.diarize.assert_called_once_with(
            str(self.audio_path),
            min_speakers=None,
            max_speakers=None,
            progress_callback=unittest.mock.ANY
        )

        # Verify formatter called
        self.formatter.format.assert_called_once()

        # Verify result
        self.assertTrue(result.diarization_succeeded)
        self.assertEqual(result.speakers_detected, 2)
        self.assertEqual(result.audio_duration, 10.0)
        self.assertIsNotNone(result.diarization_time)
        self.assertTrue(str(result.output_path).endswith('.md'))

    def test_orchestrate_diarization_disabled(self):
        """Test orchestration with diarization disabled."""
        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=False
        )

        # Verify diarizer NOT called
        self.diarizer.diarize.assert_not_called()

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

    def test_orchestrate_diarization_fails_gracefully(self):
        """Test graceful fallback when diarization fails."""
        self.diarizer.diarize.side_effect = DiarizationError("Model failed")

        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True
        )

        # Verify result indicates failure
        self.assertFalse(result.diarization_succeeded)
        self.assertEqual(result.speakers_detected, 0)
        self.assertIsNone(result.diarization_time)
        self.assertTrue(str(result.output_path).endswith('.txt'))

        # Verify plain transcript was saved
        with open(result.output_path, 'r') as f:
            content = f.read()
            self.assertIn("Speaker detection unavailable", content)

    def test_orchestrate_transcription_fails_propagates(self):
        """Test that transcription errors propagate."""
        self.transcriber.transcribe_to_segments.side_effect = Exception("Transcription failed")

        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer
        )

        with self.assertRaises(Exception) as context:
            orchestrator.orchestrate(
                audio_path=self.audio_path,
                output_path=self.output_path
            )

        self.assertIn("Transcription failed", str(context.exception))

    def test_orchestrate_progress_callback(self):
        """Test progress callback receives correct steps and percentages."""
        progress_calls = []

        def progress_callback(step, percentage):
            progress_calls.append((step, percentage))

        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
            formatter=self.formatter
        )

        orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True,
            progress_callback=progress_callback
        )

        # Should see transcribing, detecting speakers, and formatting steps
        step_names = [call[0] for call in progress_calls]
        self.assertIn("Transcribing...", step_names)
        self.assertIn("Detecting speakers...", step_names)
        self.assertIn("Formatting...", step_names)

        # Verify progress goes from 0 to 100
        percentages = [call[1] for call in progress_calls]
        self.assertEqual(percentages[0], 0.0)  # First call
        self.assertEqual(percentages[-1], 100.0)  # Last call

    def test_orchestrate_keep_intermediate_files(self):
        """Test intermediate files are saved when keep_intermediate=True."""
        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True,
            keep_intermediate=True
        )

        # Verify intermediate transcription file exists
        transcription_path = self.output_path.parent / f"{self.output_path.stem}_transcription.txt"
        self.assertTrue(transcription_path.exists())
        with open(transcription_path, 'r') as f:
            content = f.read()
            self.assertIn("First segment", content)

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
            transcriber=self.transcriber,
            diarizer=self.diarizer,
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

    def test_orchestrate_single_speaker_uses_formatter(self):
        """Test single speaker still uses formatter (not special-cased)."""
        # Mock single speaker diarization
        self.diarizer.diarize.return_value = DiarizationResult(
            segments=[SpeakerSegment(0.0, 10.0, "SPEAKER_00")],
            speaker_count=1,
            audio_duration=10.0
        )

        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True
        )

        # Formatter should still be called
        self.formatter.format.assert_called_once()
        self.assertTrue(result.diarization_succeeded)
        self.assertEqual(result.speakers_detected, 1)

    def test_orchestrate_formatting_error_fallback(self):
        """Test fallback to plain text when formatting fails."""
        # Mock formatter to raise error
        self.formatter.format.side_effect = Exception("Formatting failed")

        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
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

    def test_orchestrate_no_diarizer_provided(self):
        """Test orchestration when diarizer is None."""
        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=None,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True  # Enable but no diarizer provided
        )

        # Should save plain transcript
        self.assertFalse(result.diarization_succeeded)
        self.assertTrue(str(result.output_path).endswith('.txt'))

    @patch('cesar.orchestrator.align_timestamps')
    def test_orchestrate_calls_align_timestamps(self, mock_align):
        """Test that align_timestamps is called correctly."""
        mock_align.return_value = [
            AlignedSegment(0.0, 5.0, "SPEAKER_00", "First segment"),
            AlignedSegment(5.0, 10.0, "SPEAKER_01", "Second segment"),
        ]

        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
            formatter=self.formatter
        )

        result = orchestrator.orchestrate(
            audio_path=self.audio_path,
            output_path=self.output_path,
            enable_diarization=True
        )

        # Verify align_timestamps was called
        mock_align.assert_called_once()
        call_args = mock_align.call_args[0]
        self.assertEqual(len(call_args[0]), 2)  # Two transcription segments
        self.assertIsInstance(call_args[1], DiarizationResult)

    def test_orchestrate_creates_formatter_if_not_provided(self):
        """Test that formatter is created automatically if not provided."""
        orchestrator = TranscriptionOrchestrator(
            transcriber=self.transcriber,
            diarizer=self.diarizer,
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


if __name__ == '__main__':
    unittest.main()
