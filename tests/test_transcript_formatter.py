"""
Tests for transcript formatting with speaker labels.
"""
import unittest
from datetime import datetime
from cesar.whisperx_wrapper import WhisperXSegment
from cesar.transcript_formatter import MarkdownTranscriptFormatter, format_timestamp


class TestMarkdownTranscriptFormatter(unittest.TestCase):
    """Test MarkdownTranscriptFormatter class."""

    def test_format_single_segment(self):
        """Should format single segment with speaker header and timestamp."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=15.3,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(
                start=0.0,
                end=15.3,
                speaker="SPEAKER_00",
                text="This is the first segment."
            )
        ]

        result = formatter.format(segments)

        # Should include speaker header
        self.assertIn("### Speaker 1", result)
        # Should include timestamp
        self.assertIn("[00:00.0 - 00:15.3]", result)
        # Should include text
        self.assertIn("This is the first segment.", result)

    def test_format_multiple_segments_same_speaker(self):
        """Should show multiple timestamps for consecutive same-speaker segments."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=30.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=10.0, speaker="SPEAKER_00", text="First part."),
            WhisperXSegment(start=10.5, end=20.0, speaker="SPEAKER_00", text="Second part."),
        ]

        result = formatter.format(segments)

        # Should have single speaker header
        self.assertEqual(result.count("### Speaker 1"), 1)
        # Should have two timestamps
        self.assertIn("[00:00.0 - 00:10.0]", result)
        self.assertIn("[00:10.5 - 00:20.0]", result)
        # Should have both texts
        self.assertIn("First part.", result)
        self.assertIn("Second part.", result)

    def test_format_multiple_speakers(self):
        """Should create separate sections for different speakers."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=3,
            duration=45.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=10.0, speaker="SPEAKER_00", text="Speaker one."),
            WhisperXSegment(start=10.0, end=20.0, speaker="SPEAKER_01", text="Speaker two."),
            WhisperXSegment(start=20.0, end=30.0, speaker="SPEAKER_02", text="Speaker three."),
        ]

        result = formatter.format(segments)

        # Should have three speaker headers
        self.assertIn("### Speaker 1", result)
        self.assertIn("### Speaker 2", result)
        self.assertIn("### Speaker 3", result)
        # All texts should be present
        self.assertIn("Speaker one.", result)
        self.assertIn("Speaker two.", result)
        self.assertIn("Speaker three.", result)

    def test_format_overlapping_speech(self):
        """Should show 'Multiple speakers' for overlapping speech."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=15.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(
                start=0.0,
                end=5.0,
                speaker="Multiple speakers",
                text="Overlapping speech content."
            )
        ]

        result = formatter.format(segments)

        # Should have "Multiple speakers" header
        self.assertIn("### Multiple speakers", result)
        # Should include timestamp and text
        self.assertIn("[00:00.0 - 00:05.0]", result)
        self.assertIn("Overlapping speech content.", result)

    def test_filters_short_segments(self):
        """Should filter out segments below minimum duration."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=15.0,
            min_segment_duration=1.0
        )

        segments = [
            WhisperXSegment(start=0.0, end=0.5, speaker="SPEAKER_00", text="Too short."),
            WhisperXSegment(start=1.0, end=5.0, speaker="SPEAKER_00", text="Long enough."),
        ]

        result = formatter.format(segments)

        # Should not include the short segment
        self.assertNotIn("Too short.", result)
        # Should include the long segment
        self.assertIn("Long enough.", result)

    def test_metadata_header_speakers_detected(self):
        """Should include correct speaker count in metadata."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=3,
            duration=60.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=10.0, speaker="SPEAKER_00", text="Text.")
        ]

        result = formatter.format(segments)

        # Should show 3 speakers detected
        self.assertIn("**Speakers:** 3 detected", result)

    def test_metadata_header_duration(self):
        """Should format duration correctly in metadata."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=754.0,  # 12 minutes 34 seconds
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=10.0, speaker="SPEAKER_00", text="Text.")
        ]

        result = formatter.format(segments)

        # Should format as MM:SS
        self.assertIn("**Duration:** 12:34", result)

    def test_metadata_header_creation_date(self):
        """Should include creation date in metadata."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=60.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=10.0, speaker="SPEAKER_00", text="Text.")
        ]

        result = formatter.format(segments)

        # Should have creation date (today)
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertIn(f"**Created:** {today}", result)

    def test_metadata_header_structure(self):
        """Should have proper metadata header structure."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=60.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=10.0, speaker="SPEAKER_00", text="Text.")
        ]

        result = formatter.format(segments)

        # Should start with title
        self.assertTrue(result.startswith("# Transcript\n"))
        # Should have separator between metadata and content
        self.assertIn("\n---\n", result)

    def test_speaker_label_conversion(self):
        """Should convert SPEAKER_00 to Speaker 1, etc."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=30.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=10.0, speaker="SPEAKER_00", text="Zero."),
            WhisperXSegment(start=10.0, end=20.0, speaker="SPEAKER_01", text="One."),
        ]

        result = formatter.format(segments)

        # Should convert to human-friendly labels
        self.assertIn("### Speaker 1", result)
        self.assertIn("### Speaker 2", result)
        # Should not show raw SPEAKER_XX labels
        self.assertNotIn("SPEAKER_00", result)
        self.assertNotIn("SPEAKER_01", result)

    def test_unknown_speaker_handling(self):
        """Should handle UNKNOWN speaker label."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=1,
            duration=10.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=5.0, speaker="UNKNOWN", text="Unknown speaker."),
        ]

        result = formatter.format(segments)

        # Should show "Unknown speaker" header
        self.assertIn("### Unknown speaker", result)
        self.assertIn("Unknown speaker.", result)

    def test_empty_segments_list(self):
        """Should handle empty segments list gracefully."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=0,
            duration=0.0,
            min_segment_duration=0.5
        )

        result = formatter.format([])

        # Should still have header structure
        self.assertIn("# Transcript", result)
        # But no speaker sections
        self.assertNotIn("###", result.split("---")[1])

    def test_default_min_segment_duration(self):
        """Should use default minimum segment duration of 0.5s."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=10.0
        )

        # Should have default
        self.assertEqual(formatter.min_segment_duration, 0.5)

    def test_timestamp_format_integration(self):
        """Should use format_timestamp for consistent formatting."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=1,
            duration=100.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=65.7, end=89.4, speaker="SPEAKER_00", text="Text."),
        ]

        result = formatter.format(segments)

        # Should use MM:SS.d format
        expected_timestamp = f"[{format_timestamp(65.7)} - {format_timestamp(89.4)}]"
        self.assertIn(expected_timestamp, result)

    def test_preserves_text_content(self):
        """Should preserve exact text content including punctuation."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=1,
            duration=10.0,
            min_segment_duration=0.5
        )

        text = "This is a test! With punctuation, special chars: @#$% and numbers 123."
        segments = [
            WhisperXSegment(start=0.0, end=5.0, speaker="SPEAKER_00", text=text),
        ]

        result = formatter.format(segments)

        # Text should be preserved exactly
        self.assertIn(text, result)

    def test_alternating_speakers(self):
        """Should handle alternating speakers correctly."""
        formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=40.0,
            min_segment_duration=0.5
        )

        segments = [
            WhisperXSegment(start=0.0, end=10.0, speaker="SPEAKER_00", text="First."),
            WhisperXSegment(start=10.0, end=20.0, speaker="SPEAKER_01", text="Second."),
            WhisperXSegment(start=20.0, end=30.0, speaker="SPEAKER_00", text="First again."),
            WhisperXSegment(start=30.0, end=40.0, speaker="SPEAKER_01", text="Second again."),
        ]

        result = formatter.format(segments)

        # Should have two occurrences of each speaker header
        self.assertEqual(result.count("### Speaker 1"), 2)
        self.assertEqual(result.count("### Speaker 2"), 2)
        # All texts present
        self.assertIn("First.", result)
        self.assertIn("Second.", result)
        self.assertIn("First again.", result)
        self.assertIn("Second again.", result)


if __name__ == "__main__":
    unittest.main()
