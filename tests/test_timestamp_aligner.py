"""Unit tests for timestamp alignment module."""
import unittest
import logging
from unittest.mock import patch

from cesar.timestamp_aligner import (
    align_timestamps,
    AlignedSegment,
    TranscriptionSegment,
    format_timestamp,
    should_include_speaker_labels,
    _calculate_intersection,
    _detect_overlapping_speech,
)
from cesar.diarization import DiarizationResult, SpeakerSegment


class TestFormatTimestamp(unittest.TestCase):
    """Tests for timestamp formatting."""

    def test_format_seconds(self):
        """Test formatting seconds."""
        self.assertEqual(format_timestamp(5.2), "00:05.2")

    def test_format_minutes_seconds(self):
        """Test formatting minutes and seconds."""
        self.assertEqual(format_timestamp(65.7), "01:05.7")

    def test_format_zero(self):
        """Test formatting zero."""
        self.assertEqual(format_timestamp(0.0), "00:00.0")

    def test_format_large(self):
        """Test formatting large values."""
        self.assertEqual(format_timestamp(3661.5), "61:01.5")


class TestCalculateIntersection(unittest.TestCase):
    """Tests for intersection calculation."""

    def test_full_overlap(self):
        """Test when segment is fully within speaker range."""
        result = _calculate_intersection(5.0, 10.0, 0.0, 20.0)
        self.assertEqual(result, 5.0)

    def test_partial_overlap_start(self):
        """Test partial overlap at start."""
        result = _calculate_intersection(5.0, 10.0, 7.0, 15.0)
        self.assertEqual(result, 3.0)

    def test_partial_overlap_end(self):
        """Test partial overlap at end."""
        result = _calculate_intersection(5.0, 10.0, 0.0, 7.0)
        self.assertEqual(result, 2.0)

    def test_no_overlap(self):
        """Test no overlap."""
        result = _calculate_intersection(5.0, 10.0, 15.0, 20.0)
        self.assertEqual(result, 0.0)


class TestSingleSpeaker(unittest.TestCase):
    """Tests for single speaker handling."""

    def test_single_speaker_no_split(self):
        """Test that single speaker segments don't get split."""
        transcription = [
            TranscriptionSegment(0.0, 10.0, "Hello world"),
            TranscriptionSegment(10.0, 20.0, "How are you"),
        ]
        diarization = DiarizationResult(
            segments=[SpeakerSegment(0.0, 20.0, "SPEAKER_00")],
            speaker_count=1,
            audio_duration=20.0
        )

        result = align_timestamps(transcription, diarization)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].speaker, "SPEAKER_00")
        self.assertEqual(result[1].speaker, "SPEAKER_00")
        self.assertEqual(result[0].text, "Hello world")

    def test_should_include_labels_single(self):
        """Test that single speaker returns False for labels."""
        diarization = DiarizationResult(
            segments=[SpeakerSegment(0.0, 10.0, "SPEAKER_00")],
            speaker_count=1,
            audio_duration=10.0
        )
        self.assertFalse(should_include_speaker_labels(diarization))

    def test_should_include_labels_multiple(self):
        """Test that multiple speakers returns True for labels."""
        diarization = DiarizationResult(
            segments=[
                SpeakerSegment(0.0, 5.0, "SPEAKER_00"),
                SpeakerSegment(5.0, 10.0, "SPEAKER_01"),
            ],
            speaker_count=2,
            audio_duration=10.0
        )
        self.assertTrue(should_include_speaker_labels(diarization))


class TestMultipleSpeakers(unittest.TestCase):
    """Tests for multiple speaker alignment."""

    def test_segment_fully_in_speaker_range(self):
        """Test segment fully within one speaker's range."""
        transcription = [
            TranscriptionSegment(2.0, 4.0, "Hello world"),
        ]
        diarization = DiarizationResult(
            segments=[
                SpeakerSegment(0.0, 5.0, "SPEAKER_00"),
                SpeakerSegment(5.0, 10.0, "SPEAKER_01"),
            ],
            speaker_count=2,
            audio_duration=10.0
        )

        result = align_timestamps(transcription, diarization)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].speaker, "SPEAKER_00")

    def test_segment_split_at_speaker_change(self):
        """Test segment is split when spanning speaker change."""
        transcription = [
            TranscriptionSegment(3.0, 7.0, "Hello world how are you"),
        ]
        diarization = DiarizationResult(
            segments=[
                SpeakerSegment(0.0, 5.0, "SPEAKER_00"),
                SpeakerSegment(5.0, 10.0, "SPEAKER_01"),
            ],
            speaker_count=2,
            audio_duration=10.0
        )

        result = align_timestamps(transcription, diarization)

        # Should be split into 2 segments
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].speaker, "SPEAKER_00")
        self.assertEqual(result[1].speaker, "SPEAKER_01")
        # Text should be distributed
        self.assertTrue(len(result[0].text) > 0)
        self.assertTrue(len(result[1].text) > 0)


class TestOverlappingSpeech(unittest.TestCase):
    """Tests for overlapping speech handling."""

    def test_detect_overlapping_true(self):
        """Test detection of overlapping speakers."""
        speakers = [
            ("SPEAKER_00", 0.0, 5.0),
            ("SPEAKER_01", 3.0, 8.0),  # Overlaps from 3-5
        ]
        self.assertTrue(_detect_overlapping_speech(speakers))

    def test_detect_overlapping_false(self):
        """Test no overlap detected for sequential speakers."""
        speakers = [
            ("SPEAKER_00", 0.0, 5.0),
            ("SPEAKER_01", 5.5, 10.0),  # Small gap, no overlap
        ]
        self.assertFalse(_detect_overlapping_speech(speakers))

    def test_overlapping_speech_marked(self):
        """Test that overlapping speech is marked as 'Multiple speakers'."""
        transcription = [
            TranscriptionSegment(3.0, 6.0, "Hello world"),
        ]
        diarization = DiarizationResult(
            segments=[
                SpeakerSegment(0.0, 5.0, "SPEAKER_00"),
                SpeakerSegment(3.0, 8.0, "SPEAKER_01"),  # Overlaps 3-5
            ],
            speaker_count=2,
            audio_duration=10.0
        )

        result = align_timestamps(transcription, diarization)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].speaker, "Multiple speakers")


class TestMisalignment(unittest.TestCase):
    """Tests for misalignment handling."""

    def test_no_speaker_found_warning(self):
        """Test warning logged when no speaker found."""
        transcription = [
            TranscriptionSegment(15.0, 20.0, "Late segment"),
        ]
        diarization = DiarizationResult(
            segments=[
                SpeakerSegment(0.0, 10.0, "SPEAKER_00"),
                SpeakerSegment(10.0, 12.0, "SPEAKER_01"),  # Gap from 12-15
            ],
            speaker_count=2,  # Multiple speakers to avoid single-speaker path
            audio_duration=20.0
        )

        with self.assertLogs(level=logging.WARNING) as log:
            result = align_timestamps(transcription, diarization)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].speaker, "UNKNOWN")
        self.assertTrue(any("No speaker found" in msg for msg in log.output))

    def test_low_confidence_warning(self):
        """Test warning for low alignment confidence."""
        transcription = [
            TranscriptionSegment(0.0, 10.0, "Long segment"),  # 10s duration
        ]
        diarization = DiarizationResult(
            segments=[
                SpeakerSegment(8.0, 10.0, "SPEAKER_00"),  # Only 2s overlap = 20%
            ],
            speaker_count=2,  # Mark as multi-speaker to trigger check
            audio_duration=10.0
        )

        with self.assertLogs(level=logging.WARNING) as log:
            result = align_timestamps(transcription, diarization)

        self.assertTrue(any("Low alignment confidence" in msg for msg in log.output))


class TestAlignedSegment(unittest.TestCase):
    """Tests for AlignedSegment dataclass."""

    def test_segment_creation(self):
        """Test creating an aligned segment."""
        segment = AlignedSegment(
            start=1.5,
            end=3.7,
            speaker="SPEAKER_00",
            text="Hello world"
        )

        self.assertEqual(segment.start, 1.5)
        self.assertEqual(segment.end, 3.7)
        self.assertEqual(segment.speaker, "SPEAKER_00")
        self.assertEqual(segment.text, "Hello world")


if __name__ == "__main__":
    unittest.main()
