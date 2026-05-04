#!/usr/bin/env python3
"""
Tests for transcript formatters (standard and agent-review modes)
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from cesar.transcript_formatter import (
    format_timestamp,
    MarkdownTranscriptFormatter,
    AgentReviewMarkdownFormatter,
)
from cesar.transcriber import TranscriptionSegment
from cesar.association import ScreenshotAssociation


class TestFormatTimestamp(unittest.TestCase):
    """Test timestamp formatting utility"""

    def test_format_timestamp_standard(self):
        """Test standard timestamp formatting"""
        result = format_timestamp(83.5)  # 1:23.5
        self.assertEqual(result, "01:23.5")

    def test_format_timestamp_zero(self):
        """Test zero timestamp"""
        result = format_timestamp(0.0)
        self.assertEqual(result, "00:00.0")

    def test_format_timestamp_long(self):
        """Test long duration timestamp"""
        result = format_timestamp(3661.5)  # 1:01:01.5
        self.assertEqual(result, "61:01.5")

    def test_format_timestamp_deciseconds(self):
        """Test decisecond precision"""
        result = format_timestamp(5.12)
        self.assertEqual(result, "00:05.1")  # Rounds to 1 decisecond


class TestMarkdownTranscriptFormatter(unittest.TestCase):
    """Test standard MarkdownTranscriptFormatter"""

    def setUp(self):
        """Set up test environment"""
        self.formatter = MarkdownTranscriptFormatter(
            speaker_count=2,
            duration=120.0,
        )

    def test_format_empty_segments(self):
        """Test formatting empty segment list"""
        result = self.formatter.format([])
        self.assertIn("# Transcript", result)
        self.assertIn("Speakers:** 2 detected", result)

    def test_format_segments_with_speaker_labels(self):
        """Test formatting segments with speaker labels"""
        segments = [
            MagicMock(
                start=0.0,
                end=5.0,
                speaker="SPEAKER_00",
                text="Hello everyone",
            ),
            MagicMock(
                start=5.0,
                end=10.0,
                speaker="SPEAKER_01",
                text="Nice to meet you",
            ),
        ]

        result = self.formatter.format(segments)

        self.assertIn("### Speaker 1", result)
        self.assertIn("### Speaker 2", result)
        self.assertIn("Hello everyone", result)
        self.assertIn("Nice to meet you", result)

    def test_format_skips_short_segments(self):
        """Test that very short segments are filtered"""
        segments = [
            MagicMock(
                start=0.0,
                end=0.3,  # Below 0.5s minimum
                speaker="SPEAKER_00",
                text="Hi",
            ),
            MagicMock(
                start=0.5,
                end=5.0,
                speaker="SPEAKER_00",
                text="Valid segment",
            ),
        ]

        result = self.formatter.format(segments)

        self.assertIn("Valid segment", result)
        self.assertNotIn("Hi\n", result)  # Short segment should be filtered

    def test_format_speaker_changes(self):
        """Test speaker header changes"""
        segments = [
            MagicMock(
                start=0.0,
                end=5.0,
                speaker="SPEAKER_00",
                text="First speaker",
            ),
            MagicMock(
                start=5.0,
                end=10.0,
                speaker="SPEAKER_00",
                text="Same speaker continues",
            ),
            MagicMock(
                start=10.0,
                end=15.0,
                speaker="SPEAKER_01",
                text="New speaker",
            ),
        ]

        result = self.formatter.format(segments)

        # First speaker header should appear
        self.assertEqual(result.count("### Speaker 1"), 1)
        # Second speaker header should appear
        self.assertEqual(result.count("### Speaker 2"), 1)


class TestAgentReviewMarkdownFormatter(unittest.TestCase):
    """Test AgentReviewMarkdownFormatter"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.images_dir = Path(self.temp_dir) / "images"
        self.images_dir.mkdir()
        self.formatter = AgentReviewMarkdownFormatter(
            source_path=Path(self.temp_dir) / "video.mp4",
            duration=120.0,
            output_name="review",
            images_dir=self.images_dir,
        )

    def test_format_includes_frontmatter(self):
        """Test that output includes YAML frontmatter"""
        result = self.formatter.format(segments=[], screenshots=[])

        self.assertIn("---", result)
        self.assertIn("mode: agent-review", result)
        self.assertIn("source:", result)
        self.assertIn("duration:", result)
        self.assertIn("images_dir:", result)

    def test_format_frontmatter_values(self):
        """Test frontmatter contains correct values"""
        result = self.formatter.format(segments=[], screenshots=[])

        self.assertIn("video.mp4", result)
        self.assertIn("120.0", result)
        self.assertIn("images/", result)

    def test_format_empty_transcript(self):
        """Test formatting with no segments"""
        result = self.formatter.format(segments=[], screenshots=[])

        self.assertIn("# Agent Review", result)
        self.assertIn("No transcript segments available", result)

    def test_format_with_segments(self):
        """Test formatting with transcript segments"""
        segments = [
            TranscriptionSegment(
                start=0.0,
                end=5.0,
                text="Hello world",
                speaker="SPEAKER_00",
                segment_id="seg_001",
            ),
            TranscriptionSegment(
                start=5.0,
                end=10.0,
                text="This is a test",
                speaker="SPEAKER_01",
                segment_id="seg_002",
            ),
        ]

        result = self.formatter.format(segments, screenshots=[])

        self.assertIn("## Transcript", result)
        self.assertIn("### Speaker 1", result)
        self.assertIn("### Speaker 2", result)
        self.assertIn("Hello world", result)
        self.assertIn("This is a test", result)
        self.assertIn("00:00.0 - 00:05.0", result)
        self.assertIn("00:05.0 - 00:10.0", result)

    def test_format_with_screenshots(self):
        """Test formatting with screenshot associations"""
        segments = [
            TranscriptionSegment(
                start=0.0,
                end=10.0,
                text="Speaking about something",
                speaker="SPEAKER_00",
                segment_id="seg_001",
            ),
        ]

        screenshots = [
            ScreenshotAssociation(
                timestamp=5.0,
                filename="review_00-00-05.png",
                trigger_type="time",
                segments=segments,
            ),
        ]

        result = self.formatter.format(segments, screenshots)

        self.assertIn("![", result)
        self.assertIn("review_00-00-05.png", result)
        self.assertIn("00:05.0", result)
        self.assertIn("Time-based", result)

    def test_format_screenshot_with_cue(self):
        """Test formatting screenshot triggered by speech cue"""
        segments = [
            TranscriptionSegment(
                start=0.0,
                end=10.0,
                text="Notice this issue here",
                speaker="SPEAKER_00",
                segment_id="seg_001",
            ),
        ]

        screenshots = [
            ScreenshotAssociation(
                timestamp=5.0,
                filename="review_00-00-05.png",
                trigger_type="speech_cue",
                segments=segments,
                cue_word="notice",
            ),
        ]

        result = self.formatter.format(segments, screenshots)

        self.assertIn("Speech cue", result)
        self.assertIn("notice", result)

    def test_format_screenshot_scene_change(self):
        """Test formatting screenshot from scene change"""
        segments = [
            TranscriptionSegment(
                start=0.0,
                end=10.0,
                text="Content",
                speaker="SPEAKER_00",
                segment_id="seg_001",
            ),
        ]

        screenshots = [
            ScreenshotAssociation(
                timestamp=5.0,
                filename="review_00-00-05.png",
                trigger_type="scene_change",
                segments=segments,
            ),
        ]

        result = self.formatter.format(segments, screenshots)

        self.assertIn("Scene change", result)

    def test_format_skips_short_segments(self):
        """Test that very short segments are filtered"""
        segments = [
            TranscriptionSegment(
                start=0.0,
                end=0.05,  # Below 0.1s minimum
                text="",
                segment_id="seg_001",
            ),
            TranscriptionSegment(
                start=0.1,
                end=5.0,
                text="Valid content",
                segment_id="seg_002",
            ),
        ]

        result = self.formatter.format(segments, screenshots=[])

        self.assertIn("Valid content", result)
        # Should only have one transcript entry
        self.assertNotIn("seg_001", result)

    def test_format_metadata_header(self):
        """Test metadata header contains key info"""
        result = self.formatter.format(segments=[], screenshots=[])

        self.assertIn("# Agent Review", result)
        self.assertIn("Duration:", result)
        self.assertIn("Speakers:", result)
        self.assertIn("Date:", result)

    def test_format_multiple_screenshots_same_segment(self):
        """Test multiple screenshots for same segment"""
        segments = [
            TranscriptionSegment(
                start=0.0,
                end=30.0,
                text="Long segment with multiple screenshots",
                speaker="SPEAKER_00",
                segment_id="seg_001",
            ),
        ]

        screenshots = [
            ScreenshotAssociation(
                timestamp=5.0,
                filename="review_00-00-05.png",
                trigger_type="time",
                segments=segments,
            ),
            ScreenshotAssociation(
                timestamp=15.0,
                filename="review_00-00-15.png",
                trigger_type="scene_change",
                segments=segments,
            ),
        ]

        result = self.formatter.format(segments, screenshots)

        self.assertIn("review_00-00-05.png", result)
        self.assertIn("review_00-00-15.png", result)

    def test_format_unknown_speaker(self):
        """Test handling of unknown speaker"""
        segments = [
            TranscriptionSegment(
                start=0.0,
                end=5.0,
                text="Content",
                speaker=None,
                segment_id="seg_001",
            ),
        ]

        result = self.formatter.format(segments, screenshots=[])

        # Should not crash, should use "Unknown" as default
        self.assertIn("Content", result)


if __name__ == '__main__':
    unittest.main()
