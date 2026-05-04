#!/usr/bin/env python3
"""
Tests for SidecarGenerator (JSON sidecar for agent-review mode)
"""

import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

from cesar.sidecar_generator import (
    SidecarGenerator,
    ReviewMetadata,
    SegmentData,
    ScreenshotData,
    ReviewSidecar,
)
from cesar.transcriber import TranscriptionSegment
from cesar.association import ScreenshotAssociation


class TestReviewMetadata(unittest.TestCase):
    """Test ReviewMetadata dataclass"""

    def test_default_values(self):
        """Test default values are set correctly"""
        metadata = ReviewMetadata()
        self.assertEqual(metadata.mode, "agent-review")
        self.assertEqual(metadata.source, "")
        self.assertEqual(metadata.output_name, "")
        self.assertEqual(metadata.duration, 0.0)
        self.assertEqual(metadata.screenshots_interval, 30)
        self.assertTrue(metadata.speech_cues_enabled)
        self.assertTrue(metadata.scene_detection_enabled)

    def test_custom_values(self):
        """Test custom values can be set"""
        metadata = ReviewMetadata(
            source="/path/to/video.mp4",
            output_name="review",
            duration=120.5,
            screenshots_interval=60,
            speech_cues_enabled=False,
            scene_detection_enabled=False,
        )
        self.assertEqual(metadata.source, "/path/to/video.mp4")
        self.assertEqual(metadata.output_name, "review")
        self.assertEqual(metadata.duration, 120.5)
        self.assertEqual(metadata.screenshots_interval, 60)
        self.assertFalse(metadata.speech_cues_enabled)
        self.assertFalse(metadata.scene_detection_enabled)


class TestSegmentData(unittest.TestCase):
    """Test SegmentData dataclass"""

    def test_segment_data_creation(self):
        """Test SegmentData can be created with required fields"""
        segment = SegmentData(
            id="seg_001",
            start=0.0,
            end=5.5,
            text="Hello world",
        )
        self.assertEqual(segment.id, "seg_001")
        self.assertEqual(segment.start, 0.0)
        self.assertEqual(segment.end, 5.5)
        self.assertEqual(segment.text, "Hello world")
        self.assertIsNone(segment.speaker)

    def test_segment_data_with_speaker(self):
        """Test SegmentData with speaker"""
        segment = SegmentData(
            id="seg_002",
            start=5.5,
            end=10.0,
            text="Nice to meet you",
            speaker="SPEAKER_00",
        )
        self.assertEqual(segment.speaker, "SPEAKER_00")


class TestScreenshotData(unittest.TestCase):
    """Test ScreenshotData dataclass"""

    def test_screenshot_data_creation(self):
        """Test ScreenshotData can be created"""
        screenshot = ScreenshotData(
            filename="review_00-01-30.png",
            timestamp=90.0,
            trigger_type="time",
            associated_segment_ids=["seg_003", "seg_004"],
        )
        self.assertEqual(screenshot.filename, "review_00-01-30.png")
        self.assertEqual(screenshot.timestamp, 90.0)
        self.assertEqual(screenshot.trigger_type, "time")
        self.assertEqual(screenshot.associated_segment_ids, ["seg_003", "seg_004"])
        self.assertIsNone(screenshot.cue_word)

    def test_screenshot_data_with_cue(self):
        """Test ScreenshotData with speech cue"""
        screenshot = ScreenshotData(
            filename="review_00-02-15.png",
            timestamp=135.0,
            trigger_type="speech_cue",
            associated_segment_ids=["seg_005"],
            cue_word="notice",
        )
        self.assertEqual(screenshot.trigger_type, "speech_cue")
        self.assertEqual(screenshot.cue_word, "notice")


class TestReviewSidecar(unittest.TestCase):
    """Test ReviewSidecar dataclass"""

    def test_review_sidecar_creation(self):
        """Test ReviewSidecar can be created with all fields"""
        metadata = ReviewMetadata(source="/path/to/video.mp4", duration=120.0)
        segments = [
            SegmentData(id="seg_001", start=0.0, end=5.0, text="Hello"),
        ]
        screenshots = [
            ScreenshotData(
                filename="review_00-01-00.png",
                timestamp=60.0,
                trigger_type="time",
                associated_segment_ids=["seg_001"],
            ),
        ]

        sidecar = ReviewSidecar(
            metadata=metadata,
            transcript=segments,
            screenshots=screenshots,
        )

        self.assertEqual(sidecar.metadata.source, "/path/to/video.mp4")
        self.assertEqual(len(sidecar.transcript), 1)
        self.assertEqual(len(sidecar.screenshots), 1)


class TestSidecarGenerator(unittest.TestCase):
    """Test SidecarGenerator functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_path = Path(self.temp_dir) / "review"
        self.source_path = Path(self.temp_dir) / "video.mp4"
        self.duration = 120.5

    def test_generator_initialization(self):
        """Test generator can be initialized"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        self.assertEqual(generator.output_path, self.output_path)
        self.assertEqual(generator.source_path, self.source_path)
        self.assertEqual(generator.duration, self.duration)
        expected_sidecar_path = self.output_path.with_suffix('.sidecar.json')
        self.assertEqual(generator.sidecar_path, expected_sidecar_path)

    def test_configure(self):
        """Test configuration options"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        generator.configure(
            screenshots_interval=60,
            speech_cues_enabled=False,
            scene_detection_enabled=False,
        )

        self.assertEqual(generator._screenshots_interval, 60)
        self.assertFalse(generator._speech_cues_enabled)
        self.assertFalse(generator._scene_detection_enabled)

    def test_build_metadata(self):
        """Test metadata building"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        metadata = generator._build_metadata()

        self.assertEqual(metadata.mode, "agent-review")
        self.assertEqual(metadata.source, str(self.source_path))
        self.assertEqual(metadata.output_name, "review")
        self.assertEqual(metadata.duration, self.duration)
        self.assertIsNotNone(metadata.created_at)
        # Should be valid ISO format
        datetime.fromisoformat(metadata.created_at)

    def test_serialize_segments_empty(self):
        """Test serializing empty segment list"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        result = generator._serialize_segments([])
        self.assertEqual(result, [])

    def test_serialize_segments(self):
        """Test serializing transcript segments"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        segments = [
            TranscriptionSegment(
                start=0.0,
                end=5.5,
                text="Hello world",
                speaker="SPEAKER_00",
                segment_id="seg_001",
            ),
            TranscriptionSegment(
                start=5.5,
                end=10.0,
                text="Nice to meet you",
                speaker="SPEAKER_01",
                segment_id="seg_002",
            ),
        ]

        result = generator._serialize_segments(segments)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "seg_001")
        self.assertEqual(result[0].start, 0.0)
        self.assertEqual(result[0].end, 5.5)
        self.assertEqual(result[0].text, "Hello world")
        self.assertEqual(result[0].speaker, "SPEAKER_00")
        self.assertEqual(result[1].speaker, "SPEAKER_01")

    def test_serialize_segments_skips_short(self):
        """Test that very short segments are skipped"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        segments = [
            TranscriptionSegment(
                start=0.0,
                end=0.05,  # Less than 0.1s
                text="",
                segment_id="seg_001",
            ),
            TranscriptionSegment(
                start=0.1,
                end=5.0,
                text="Valid segment",
                segment_id="seg_002",
            ),
        ]

        result = generator._serialize_segments(segments)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "seg_002")

    def test_serialize_screenshots_empty(self):
        """Test serializing empty screenshot list"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        result = generator._serialize_screenshots([])
        self.assertEqual(result, [])

    def test_serialize_screenshots(self):
        """Test serializing screenshot associations"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        associations = [
            ScreenshotAssociation(
                timestamp=60.0,
                filename="review_00-01-00.png",
                trigger_type="time",
                segments=[
                    TranscriptionSegment(
                        start=55.0, end=65.0, text="Speaking",
                        segment_id="seg_003",
                    ),
                ],
            ),
            ScreenshotAssociation(
                timestamp=90.0,
                filename="review_00-01-30.png",
                trigger_type="speech_cue",
                segments=[
                    TranscriptionSegment(
                        start=85.0, end=95.0, text="Notice this",
                        segment_id="seg_005",
                    ),
                ],
                cue_word="notice",
            ),
        ]

        result = generator._serialize_screenshots(associations)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].filename, "review_00-01-00.png")
        self.assertEqual(result[0].trigger_type, "time")
        self.assertEqual(result[0].associated_segment_ids, ["seg_003"])
        self.assertIsNone(result[0].cue_word)

        self.assertEqual(result[1].trigger_type, "speech_cue")
        self.assertEqual(result[1].cue_word, "notice")

    def test_to_dict(self):
        """Test generating sidecar as dictionary"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        segments = [
            TranscriptionSegment(
                start=0.0,
                end=5.0,
                text="Hello",
                segment_id="seg_001",
            ),
        ]

        associations = [
            ScreenshotAssociation(
                timestamp=60.0,
                filename="review_00-01-00.png",
                trigger_type="time",
                segments=[],
            ),
        ]

        result = generator.to_dict(segments, associations)

        self.assertIn("metadata", result)
        self.assertIn("transcript", result)
        self.assertIn("screenshots", result)
        self.assertEqual(result["metadata"]["mode"], "agent-review")
        self.assertEqual(len(result["transcript"]), 1)
        self.assertEqual(len(result["screenshots"]), 1)

    def test_generate_writes_file(self):
        """Test that generate() writes a JSON file"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )

        segments = [
            TranscriptionSegment(
                start=0.0,
                end=5.0,
                text="Hello",
                segment_id="seg_001",
            ),
        ]

        associations = [
            ScreenshotAssociation(
                timestamp=60.0,
                filename="review_00-01-00.png",
                trigger_type="time",
                segments=[],
            ),
        ]

        result = generator.generate(segments, associations)

        # Check file was created
        self.assertTrue(result.exists())

        # Check content is valid JSON
        with open(result, 'r') as f:
            data = json.load(f)

        self.assertEqual(data["metadata"]["mode"], "agent-review")
        self.assertEqual(len(data["transcript"]), 1)
        self.assertEqual(len(data["screenshots"]), 1)

    def test_generated_json_structure(self):
        """Test the structure of generated JSON matches schema"""
        generator = SidecarGenerator(
            output_path=self.output_path,
            source_path=self.source_path,
            duration=self.duration,
        )
        generator.configure(
            screenshots_interval=45,
            speech_cues_enabled=True,
            scene_detection_enabled=False,
        )

        segments = [
            TranscriptionSegment(
                start=0.0,
                end=5.0,
                text="Hello world",
                speaker="SPEAKER_00",
                segment_id="seg_001",
            ),
        ]

        associations = [
            ScreenshotAssociation(
                timestamp=90.0,
                filename="review_00-01-30.png",
                trigger_type="scene_change",
                segments=segments,
            ),
        ]

        result = generator.to_dict(segments, associations)

        # Validate metadata structure
        metadata = result["metadata"]
        self.assertEqual(metadata["mode"], "agent-review")
        self.assertEqual(metadata["source"], str(self.source_path))
        self.assertEqual(metadata["duration"], self.duration)
        self.assertIn("created_at", metadata)
        self.assertEqual(metadata["screenshots_interval"], 45)
        self.assertTrue(metadata["speech_cues_enabled"])
        self.assertFalse(metadata["scene_detection_enabled"])

        # Validate transcript structure
        self.assertEqual(len(result["transcript"]), 1)
        seg = result["transcript"][0]
        self.assertIn("id", seg)
        self.assertIn("start", seg)
        self.assertIn("end", seg)
        self.assertIn("text", seg)
        self.assertIn("speaker", seg)

        # Validate screenshots structure
        self.assertEqual(len(result["screenshots"]), 1)
        ss = result["screenshots"][0]
        self.assertIn("filename", ss)
        self.assertIn("timestamp", ss)
        self.assertIn("trigger_type", ss)
        self.assertIn("associated_segment_ids", ss)
        self.assertEqual(ss["trigger_type"], "scene_change")


if __name__ == '__main__':
    unittest.main()
