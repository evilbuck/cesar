"""Tests for diarization exception classes and data types.

The actual diarization implementation has been replaced by WhisperX pipeline.
This module now only tests the remaining exception classes and dataclasses
for backward compatibility.
"""
import unittest

from cesar.diarization import (
    DiarizationError,
    AuthenticationError,
    SpeakerSegment,
    DiarizationResult,
)


class TestDiarizationExceptions(unittest.TestCase):
    """Tests for diarization exception classes."""

    def test_diarization_error_is_exception(self):
        """Test DiarizationError is an exception."""
        with self.assertRaises(DiarizationError):
            raise DiarizationError("test error")

    def test_authentication_error_is_diarization_error(self):
        """Test AuthenticationError is a subclass of DiarizationError."""
        self.assertTrue(issubclass(AuthenticationError, DiarizationError))

    def test_authentication_error_can_be_caught_as_diarization_error(self):
        """Test AuthenticationError can be caught as DiarizationError."""
        with self.assertRaises(DiarizationError):
            raise AuthenticationError("auth failed")

    def test_exception_message_preserved(self):
        """Test exception message is preserved."""
        try:
            raise DiarizationError("specific message")
        except DiarizationError as e:
            self.assertEqual(str(e), "specific message")

    def test_authentication_error_message_preserved(self):
        """Test AuthenticationError message is preserved."""
        try:
            raise AuthenticationError("auth specific message")
        except AuthenticationError as e:
            self.assertEqual(str(e), "auth specific message")


class TestSpeakerSegment(unittest.TestCase):
    """Tests for SpeakerSegment dataclass."""

    def test_segment_creation(self):
        """Test creating a SpeakerSegment."""
        segment = SpeakerSegment(start=1.5, end=3.7, speaker="SPEAKER_00")

        self.assertEqual(segment.start, 1.5)
        self.assertEqual(segment.end, 3.7)
        self.assertEqual(segment.speaker, "SPEAKER_00")

    def test_segment_equality(self):
        """Test SpeakerSegment equality."""
        seg1 = SpeakerSegment(start=0.0, end=5.0, speaker="SPEAKER_00")
        seg2 = SpeakerSegment(start=0.0, end=5.0, speaker="SPEAKER_00")
        seg3 = SpeakerSegment(start=0.0, end=5.0, speaker="SPEAKER_01")

        self.assertEqual(seg1, seg2)
        self.assertNotEqual(seg1, seg3)


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

    def test_result_with_single_speaker(self):
        """Test DiarizationResult with single speaker."""
        segments = [
            SpeakerSegment(start=0.0, end=30.0, speaker="SPEAKER_00"),
        ]
        result = DiarizationResult(
            segments=segments,
            speaker_count=1,
            audio_duration=30.0
        )

        self.assertEqual(result.speaker_count, 1)
        self.assertEqual(len(result.segments), 1)


if __name__ == '__main__':
    unittest.main()
