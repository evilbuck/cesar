"""Tests for screenshot-to-segment association."""

import unittest
from cesar.association import (
    ScreenshotAssociation,
    associate_screenshots,
    format_timestamp_for_filename,
)
from cesar.transcriber import TranscriptionSegment


class TestScreenshotAssociation(unittest.TestCase):
    """Tests for ScreenshotAssociation dataclass."""

    def test_creation(self):
        """Test basic association creation."""
        seg = TranscriptionSegment(start=0.0, end=5.0, text="hello")
        assoc = ScreenshotAssociation(
            timestamp=2.5,
            filename="video_00-00-02.png",
            trigger_type="time",
            segments=[seg],
        )
        self.assertEqual(assoc.timestamp, 2.5)
        self.assertEqual(assoc.filename, "video_00-00-02.png")
        self.assertEqual(assoc.trigger_type, "time")
        self.assertEqual(len(assoc.segments), 1)
        self.assertIsNone(assoc.cue_word)

    def test_with_cue_word(self):
        """Test association with speech cue."""
        seg = TranscriptionSegment(start=10.0, end=15.0, text="look at this")
        assoc = ScreenshotAssociation(
            timestamp=10.0,
            filename="video_00-00-10.png",
            trigger_type="speech_cue",
            segments=[seg],
            cue_word="this",
        )
        self.assertEqual(assoc.cue_word, "this")
        self.assertEqual(assoc.trigger_type, "speech_cue")


class TestAssociateScreenshots(unittest.TestCase):
    """Tests for associate_screenshots function."""

    def _make_segments(self, *ranges):
        """Helper to create segments from (start, end, text) tuples."""
        return [
            TranscriptionSegment(start=s, end=e, text=t)
            for s, e, t in ranges
        ]

    def test_basic_association(self):
        """Single screenshot matches single segment."""
        segments = self._make_segments(
            (0.0, 5.0, "hello world"),
            (5.0, 10.0, "next segment"),
        )
        screenshots = [(2.5, "video_00-00-02.png")]

        result = associate_screenshots(screenshots, segments)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].timestamp, 2.5)
        self.assertEqual(len(result[0].segments), 1)
        self.assertEqual(result[0].segments[0].text, "hello world")

    def test_overlapping_segments(self):
        """Screenshot matches multiple overlapping segments."""
        segments = self._make_segments(
            (0.0, 5.0, "first"),
            (4.0, 8.0, "second"),
            (7.0, 12.0, "third"),
        )
        screenshots = [(5.0, "video_00-00-05.png")]

        result = associate_screenshots(screenshots, segments)

        # With default tolerance 2.0, timestamp 5.0 should match:
        # seg1: [0,5] — overlaps at 5.0 exactly
        # seg2: [4,8] — overlaps
        # seg3: [7,12] — within tolerance (7.0 <= 5.0+2.0)
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(len(result[0].segments), 2)

    def test_no_matching_segments(self):
        """Screenshot with no overlapping segments."""
        segments = self._make_segments(
            (0.0, 5.0, "early"),
            (20.0, 30.0, "late"),
        )
        screenshots = [(10.0, "video_00-00-10.png")]

        result = associate_screenshots(screenshots, segments)

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].segments), 0)

    def test_multiple_screenshots(self):
        """Multiple screenshots each match their own segments."""
        segments = self._make_segments(
            (0.0, 5.0, "first"),
            (10.0, 15.0, "second"),
            (20.0, 25.0, "third"),
        )
        screenshots = [
            (2.5, "video_00-00-02.png"),
            (12.5, "video_00-00-12.png"),
        ]

        result = associate_screenshots(screenshots, segments)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].segments[0].text, "first")
        self.assertEqual(result[1].segments[0].text, "second")

    def test_empty_screenshots(self):
        """No screenshots returns empty list."""
        segments = self._make_segments((0.0, 5.0, "text"))

        result = associate_screenshots([], segments)

        self.assertEqual(result, [])

    def test_empty_segments(self):
        """No segments produces associations with empty segment lists."""
        screenshots = [(5.0, "video_00-00-05.png")]

        result = associate_screenshots(screenshots, [])

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0].segments), 0)

    def test_trigger_type_propagated(self):
        """Trigger type is set on all associations."""
        segments = self._make_segments((0.0, 5.0, "text"))
        screenshots = [(2.5, "video_00-00-02.png")]

        result = associate_screenshots(
            screenshots, segments, trigger_type="scene_change"
        )

        self.assertEqual(result[0].trigger_type, "scene_change")

    def test_custom_tolerance(self):
        """Custom tolerance changes matching behavior."""
        segments = self._make_segments(
            (0.0, 5.0, "close"),
            (15.0, 20.0, "far"),
        )
        screenshots = [(10.0, "video_00-00-10.png")]

        # Default tolerance (2.0): no matches
        result_default = associate_screenshots(
            screenshots, segments, tolerance=2.0
        )
        self.assertEqual(len(result_default[0].segments), 0)

        # Large tolerance (6.0): matches both
        result_large = associate_screenshots(
            screenshots, segments, tolerance=6.0
        )
        self.assertEqual(len(result_large[0].segments), 2)

    def test_segment_with_id_and_speaker(self):
        """Association preserves segment_id and speaker fields."""
        seg = TranscriptionSegment(
            start=0.0, end=5.0, text="hello",
            speaker="SPEAKER_00", segment_id="seg_001"
        )
        screenshots = [(2.5, "video_00-00-02.png")]

        result = associate_screenshots(screenshots, [seg])

        self.assertEqual(result[0].segments[0].segment_id, "seg_001")
        self.assertEqual(result[0].segments[0].speaker, "SPEAKER_00")


class TestFormatTimestampForFilename(unittest.TestCase):
    """Tests for format_timestamp_for_filename."""

    def test_zero(self):
        """Zero seconds."""
        self.assertEqual(format_timestamp_for_filename(0.0), "00-00-00")

    def test_seconds_only(self):
        """Under a minute."""
        self.assertEqual(format_timestamp_for_filename(45.0), "00-00-45")

    def test_minutes_and_seconds(self):
        """Under an hour."""
        self.assertEqual(format_timestamp_for_filename(125.7), "00-02-05")

    def test_hours(self):
        """Over an hour."""
        self.assertEqual(format_timestamp_for_filename(3725.0), "01-02-05")

    def test_large_timestamp(self):
        """Multi-hour recording."""
        self.assertEqual(format_timestamp_for_filename(7384.0), "02-03-04")


if __name__ == "__main__":
    unittest.main()
