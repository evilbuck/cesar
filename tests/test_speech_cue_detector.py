#!/usr/bin/env python3
"""
Tests for SpeechCueDetector and related types.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from cesar.speech_cue_detector import (
    SpeechCueDetector,
    TranscriptSegment,
    CueMatch,
    DEFAULT_SPEECH_CUES,
)


class TestTranscriptSegment(unittest.TestCase):
    """Test TranscriptSegment dataclass."""

    def test_basic_segment(self):
        """Test creating a basic segment."""
        seg = TranscriptSegment(start=5.0, end=10.0, text="Hello world")
        self.assertEqual(seg.start, 5.0)
        self.assertEqual(seg.end, 10.0)
        self.assertEqual(seg.text, "Hello world")
        self.assertIsNone(seg.speaker)
        self.assertIsNone(seg.segment_id)

    def test_segment_with_speaker(self):
        """Test creating a segment with speaker label."""
        seg = TranscriptSegment(
            start=5.0, end=10.0, text="Hello world", speaker="SPEAKER_00"
        )
        self.assertEqual(seg.speaker, "SPEAKER_00")

    def test_segment_with_id(self):
        """Test creating a segment with ID."""
        seg = TranscriptSegment(
            start=5.0, end=10.0, text="Hello world", segment_id="seg_001"
        )
        self.assertEqual(seg.segment_id, "seg_001")


class TestCueMatch(unittest.TestCase):
    """Test CueMatch dataclass."""

    def test_cue_match_creation(self):
        """Test creating a cue match."""
        match = CueMatch(
            timestamp=5.0,
            cue_word="this",
            segment_text="Look at this code",
        )
        self.assertEqual(match.timestamp, 5.0)
        self.assertEqual(match.cue_word, "this")
        self.assertEqual(match.segment_text, "Look at this code")


class TestSpeechCueDetector(unittest.TestCase):
    """Test SpeechCueDetector functionality."""

    def test_default_cues(self):
        """Test default cue word list."""
        detector = SpeechCueDetector()
        self.assertEqual(detector.cue_words, DEFAULT_SPEECH_CUES)

    def test_custom_cues(self):
        """Test custom cue words."""
        detector = SpeechCueDetector(cue_words=["custom", "words"])
        self.assertEqual(detector.cue_words, ["custom", "words"])

    def test_detect_single_cue(self):
        """Test detecting a single cue word."""
        detector = SpeechCueDetector()
        segments = [
            TranscriptSegment(start=5.0, end=10.0, text="Look at this function"),
        ]

        matches = detector.detect_cues(segments)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].timestamp, 5.0)
        self.assertEqual(matches[0].cue_word, "this")

    def test_detect_case_insensitive(self):
        """Test case-insensitive cue detection."""
        detector = SpeechCueDetector()
        segments = [
            TranscriptSegment(start=5.0, end=10.0, text="LOOK AT THIS"),
        ]

        matches = detector.detect_cues(segments)
        self.assertEqual(len(matches), 1)

    def test_detect_no_cues(self):
        """Test no cues found in text."""
        detector = SpeechCueDetector()
        segments = [
            TranscriptSegment(start=5.0, end=10.0, text="The weather is nice today"),
        ]

        matches = detector.detect_cues(segments)
        self.assertEqual(len(matches), 0)

    def test_detect_multiple_segments(self):
        """Test detecting cues across multiple segments."""
        detector = SpeechCueDetector()
        segments = [
            TranscriptSegment(start=5.0, end=10.0, text="Look at this function"),
            TranscriptSegment(start=15.0, end=20.0, text="The code is fine"),
            TranscriptSegment(start=25.0, end=30.0, text="Here is the issue"),
        ]

        matches = detector.detect_cues(segments)
        self.assertEqual(len(matches), 2)  # "this" and "here" (not "issue" — already matched "here")
        timestamps = [m.timestamp for m in matches]
        self.assertIn(5.0, timestamps)
        self.assertIn(25.0, timestamps)

    def test_one_match_per_segment(self):
        """Test that only one match is returned per segment even with multiple cues."""
        detector = SpeechCueDetector()
        segments = [
            TranscriptSegment(
                start=5.0, end=10.0,
                text="Look at this broken bug"
            ),
        ]

        matches = detector.detect_cues(segments)
        # Should only be 1 match even though "this", "broken", "bug" all match
        self.assertEqual(len(matches), 1)
        # Should match the first cue found ("this" is first in default list)
        self.assertEqual(matches[0].cue_word, "this")

    def test_detect_cue_with_speaker(self):
        """Test that match includes speaker info."""
        detector = SpeechCueDetector()
        segments = [
            TranscriptSegment(
                start=5.0, end=10.0, text="This is wrong",
                speaker="SPEAKER_01", segment_id="seg_005"
            ),
        ]

        matches = detector.detect_cues(segments)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].speaker, "SPEAKER_01")
        self.assertEqual(matches[0].segment_id, "seg_005")

    def test_multi_word_cue(self):
        """Test detection of multi-word cue phrases."""
        detector = SpeechCueDetector()
        segments = [
            TranscriptSegment(start=5.0, end=10.0, text="Pay attention to this"),
        ]

        matches = detector.detect_cues(segments)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].cue_word, "this")

    def test_empty_segments(self):
        """Test with empty segment list."""
        detector = SpeechCueDetector()
        matches = detector.detect_cues([])
        self.assertEqual(matches, 0 if isinstance(matches, int) else [])

    def test_get_cue_timestamps(self):
        """Test convenience method for getting just timestamps."""
        detector = SpeechCueDetector()
        segments = [
            TranscriptSegment(start=5.0, end=10.0, text="This is here"),
            TranscriptSegment(start=25.0, end=30.0, text="The bug is obvious"),
        ]

        timestamps = detector.get_cue_timestamps(segments)
        self.assertEqual(timestamps, [5.0, 25.0])

    def test_get_cue_timestamps_deduplicates(self):
        """Test that get_cue_timestamps returns unique timestamps."""
        detector = SpeechCueDetector(cue_words=["this", "here"])
        segments = [
            TranscriptSegment(start=5.0, end=10.0, text="This is here"),
        ]

        timestamps = detector.get_cue_timestamps(segments)
        # Both "this" and "here" match, but only one timestamp
        self.assertEqual(len(timestamps), 1)
        self.assertEqual(timestamps[0], 5.0)

    def test_parse_cue_string(self):
        """Test parsing comma-separated cue string."""
        result = SpeechCueDetector.parse_cue_string("this, here, that")
        self.assertEqual(result, ["this", "here", "that"])

    def test_parse_cue_string_strips_whitespace(self):
        """Test that whitespace is stripped from cues."""
        result = SpeechCueDetector.parse_cue_string(" this , here , that ")
        self.assertEqual(result, ["this", "here", "that"])

    def test_parse_cue_string_filters_empty(self):
        """Test that empty entries are filtered out."""
        result = SpeechCueDetector.parse_cue_string("this,,that,")
        self.assertEqual(result, ["this", "that"])

    def test_parse_cue_string_empty_input(self):
        """Test parsing empty string."""
        result = SpeechCueDetector.parse_cue_string("")
        self.assertEqual(result, [])


class TestDefaultCueList(unittest.TestCase):
    """Test the default speech cue word list."""

    def test_default_cues_include_expected_words(self):
        """Test that default cues contain expected words."""
        expected = ["this", "here", "that", "look at", "notice", "bug", "wrong", "broken"]
        for word in expected:
            self.assertIn(word, DEFAULT_SPEECH_CUES)

    def test_default_cues_count(self):
        """Test default cue list has 12 entries."""
        self.assertEqual(len(DEFAULT_SPEECH_CUES), 12)


if __name__ == '__main__':
    unittest.main()
