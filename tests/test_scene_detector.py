#!/usr/bin/env python3
"""
Tests for FFmpegSceneDetector, time-based sampling, and timestamp deduplication.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cesar.ffmpeg_scene_detector import (
    FFmpegSceneDetector,
    generate_time_based_timestamps,
    deduplicate_timestamps,
    SceneDetectionError,
)


class TestFFmpegSceneDetector(unittest.TestCase):
    """Test FFmpegSceneDetector functionality."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.video_path = Path(self.temp_dir) / "test.mp4"
        self.video_path.touch()
        self.detector = FFmpegSceneDetector(threshold=0.3)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_default_threshold(self):
        """Test default threshold is 0.3."""
        detector = FFmpegSceneDetector()
        self.assertEqual(detector.threshold, 0.3)

    def test_custom_threshold(self):
        """Test custom threshold."""
        detector = FFmpegSceneDetector(threshold=0.5)
        self.assertEqual(detector.threshold, 0.5)

    def test_detect_scenes_file_not_found(self):
        """Test detect_scenes raises FileNotFoundError for missing file."""
        with self.assertRaises(FileNotFoundError):
            self.detector.detect_scenes(Path("/nonexistent/video.mp4"))

    @patch('cesar.ffmpeg_scene_detector.subprocess.run')
    def test_detect_with_scdet_success(self, mock_run):
        """Test successful scene detection with scdet filter."""
        # Mock scdet available
        self.detector._scdet_available = True

        # Mock FFmpeg output with scene changes
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr=(
                "[Parsed_scdet_0 @ 0x...] lavfi.scdit.score=0.45 pts_time:5.123000\n"
                "[Parsed_scdet_0 @ 0x...] lavfi.scdit.score=0.67 pts_time:12.456000\n"
                "[Parsed_scdet_0 @ 0x...] lavfi.scdit.score=0.38 pts_time:25.789000\n"
            ),
            stdout=""
        )

        result = self.detector.detect_scenes(self.video_path)
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result[0], 5.123, places=3)
        self.assertAlmostEqual(result[1], 12.456, places=3)
        self.assertAlmostEqual(result[2], 25.789, places=3)

    @patch('cesar.ffmpeg_scene_detector.subprocess.run')
    def test_detect_with_scdet_no_scenes(self, mock_run):
        """Test scene detection with no scene changes found."""
        self.detector._scdet_available = True

        mock_run.return_value = MagicMock(
            returncode=0,
            stderr="",
            stdout=""
        )

        result = self.detector.detect_scenes(self.video_path)
        self.assertEqual(result, [])

    @patch('cesar.ffmpeg_scene_detector.subprocess.run')
    def test_detect_with_scdet_fallback(self, mock_run):
        """Test fallback from scdet to select filter."""
        self.detector._scdet_available = True

        # scdet fails, select succeeds
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            cmd = args[0] if args else kwargs.get('args', [])
            if 'scdet' in str(cmd):
                raise subprocess.CalledProcessError(1, 'ffmpeg', stderr='scdet error')
            elif 'select' in str(cmd):
                return MagicMock(
                    returncode=0,
                    stderr="pts_time:10.500\npts_time:20.300\n",
                    stdout=""
                )
            return MagicMock(returncode=0, stderr="", stdout="")

        mock_run.side_effect = side_effect

        result = self.detector.detect_scenes(self.video_path)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0], 10.5, places=3)

    @patch('cesar.ffmpeg_scene_detector.subprocess.run')
    def test_detect_with_select_filter(self, mock_run):
        """Test detection using select filter (scdet unavailable)."""
        self.detector._scdet_available = False

        mock_run.return_value = MagicMock(
            returncode=0,
            stderr="pts_time:8.250000\npts_time:16.750000\n",
            stdout=""
        )

        result = self.detector.detect_scenes(self.video_path)
        self.assertEqual(len(result), 2)

    @patch('cesar.ffmpeg_scene_detector.subprocess.run')
    def test_detect_graceful_failure(self, mock_run):
        """Test graceful empty result on complete failure."""
        self.detector._scdet_available = False

        mock_run.side_effect = subprocess.CalledProcessError(
            1, 'ffmpeg', stderr='error'
        )

        result = self.detector.detect_scenes(self.video_path)
        self.assertEqual(result, [])

    @patch('cesar.ffmpeg_scene_detector.subprocess.run')
    def test_scdet_available_check(self, mock_run):
        """Test scdet availability detection."""
        # scdet in filters list
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=" ... scdet ... select ... ",
        )
        detector = FFmpegSceneDetector()
        detector._scdet_available = None
        self.assertTrue(detector.scdet_available)

    @patch('cesar.ffmpeg_scene_detector.subprocess.run')
    def test_scdet_not_available(self, mock_run):
        """Test scdet not in filters list."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=" ... select ... scale ... ",
        )
        detector = FFmpegSceneDetector()
        detector._scdet_available = None
        self.assertFalse(detector.scdet_available)

    def test_parse_scene_timestamps(self):
        """Test parsing of scdet output."""
        output = (
            "[Parsed_scdet_0] lavfi.scdit.score=0.45 pts_time:5.123000\n"
            "[Parsed_scdet_0] lavfi.scdit.score=0.67 pts_time:12.456000\n"
        )
        result = self.detector._parse_scene_timestamps(output)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0], 5.123, places=3)

    def test_parse_scene_timestamps_deduplicates(self):
        """Test that duplicate timestamps are removed."""
        output = "pts_time:5.000 pts_time:5.000 pts_time:10.000"
        result = self.detector._parse_scene_timestamps(output)
        self.assertEqual(len(result), 2)

    def test_parse_showinfo_timestamps(self):
        """Test parsing of showinfo output."""
        output = (
            "[Parsed_showinfo_1] n:0 pts:162000 pts_time:5.062500\n"
            "[Parsed_showinfo_1] n:1 pts:405000 pts_time:12.656250\n"
        )
        result = self.detector._parse_showinfo_timestamps(output)
        self.assertEqual(len(result), 2)


class TestTimeBasedTimestamps(unittest.TestCase):
    """Test time-based timestamp generation."""

    def test_basic_interval(self):
        """Test timestamps at 30s intervals for 120s video."""
        result = generate_time_based_timestamps(120.0, interval=30.0)
        self.assertEqual(result, [30.0, 60.0, 90.0])

    def test_start_at_first_interval(self):
        """Test that timestamps start at the first interval, not 0."""
        result = generate_time_based_timestamps(60.0, interval=30.0)
        self.assertNotIn(0.0, result)
        self.assertEqual(result, [30.0])

    def test_short_video(self):
        """Test video shorter than interval returns empty."""
        result = generate_time_based_timestamps(15.0, interval=30.0)
        self.assertEqual(result, [])

    def test_custom_interval(self):
        """Test custom interval."""
        result = generate_time_based_timestamps(60.0, interval=15.0)
        self.assertEqual(result, [15.0, 30.0, 45.0])

    def test_zero_duration(self):
        """Test zero duration returns empty."""
        result = generate_time_based_timestamps(0.0, interval=30.0)
        self.assertEqual(result, [])

    def test_negative_duration(self):
        """Test negative duration returns empty."""
        result = generate_time_based_timestamps(-10.0, interval=30.0)
        self.assertEqual(result, [])

    def test_zero_interval(self):
        """Test zero interval returns empty."""
        result = generate_time_based_timestamps(60.0, interval=0.0)
        self.assertEqual(result, [])

    def test_start_offset(self):
        """Test start offset parameter."""
        result = generate_time_based_timestamps(120.0, interval=30.0, start=10.0)
        self.assertEqual(result, [40.0, 70.0, 100.0])

    def test_exact_boundary(self):
        """Test video duration exactly at interval boundary."""
        result = generate_time_based_timestamps(60.0, interval=30.0)
        # t=60 == duration, should not be included (t < duration)
        self.assertNotIn(60.0, result)


class TestDeduplicateTimestamps(unittest.TestCase):
    """Test timestamp deduplication."""

    def test_empty_input(self):
        """Test empty input returns empty."""
        result = deduplicate_timestamps([])
        self.assertEqual(result, [])

    def test_no_lists(self):
        """Test no arguments returns empty."""
        result = deduplicate_timestamps()
        self.assertEqual(result, [])

    def test_single_list(self):
        """Test single list passes through."""
        result = deduplicate_timestamps([1.0, 5.0, 10.0])
        self.assertEqual(result, [1.0, 5.0, 10.0])

    def test_merge_multiple_lists(self):
        """Test merging multiple lists."""
        result = deduplicate_timestamps(
            [5.0, 20.0],
            [10.0, 25.0],
            [15.0, 30.0],
        )
        self.assertEqual(result, [5.0, 10.0, 15.0, 20.0, 25.0, 30.0])

    def test_dedup_close_timestamps(self):
        """Test that timestamps within tolerance are deduplicated."""
        result = deduplicate_timestamps(
            [5.0, 5.3, 5.8, 10.0],
            tolerance=1.0
        )
        # 5.3 and 5.8 are within 1.0 of 5.0, so they get removed
        self.assertEqual(result, [5.0, 10.0])

    def test_dedup_across_sources(self):
        """Test dedup of close timestamps from different sources."""
        result = deduplicate_timestamps(
            [5.0, 20.0],
            [5.5, 19.7],  # 5.5 close to 5.0, 19.7 close to 20.0
            tolerance=1.0
        )
        self.assertEqual(result, [5.0, 19.7])

    def test_custom_tolerance(self):
        """Test custom tolerance."""
        result = deduplicate_timestamps(
            [5.0, 5.3, 5.8, 10.0],
            tolerance=0.2
        )
        # Only 5.3 is within 0.2 of 5.0
        self.assertEqual(result, [5.0, 5.3, 5.8, 10.0])

    def test_preserves_order(self):
        """Test that result is sorted."""
        result = deduplicate_timestamps(
            [30.0, 10.0, 20.0],
        )
        self.assertEqual(result, [10.0, 20.0, 30.0])


if __name__ == '__main__':
    unittest.main()
