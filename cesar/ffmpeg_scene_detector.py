"""
FFmpeg-based scene change detection for video files.

Detects scene transitions using FFmpeg's select filter with scene detection.
Returns timestamps where significant visual changes occur between frames.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SceneDetectionError(Exception):
    """Base exception for scene detection errors."""
    pass


class FFmpegSceneDetector:
    """Detects scene changes in video files using FFmpeg.

    Uses FFmpeg's select filter with the 'scdet' (scene detection) mode
    to find timestamps where the visual content changes significantly.

    Falls back to the 'select' filter with scene comparison if scdet
    is not available in the installed FFmpeg version.
    """

    # Default threshold for scene detection (0.0 = everything, 1.0 = nothing)
    DEFAULT_THRESHOLD = 0.3

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        """Initialize the scene detector.

        Args:
            threshold: Scene detection sensitivity (0.0-1.0).
                Lower values detect more scene changes.
                Default: 0.3
        """
        self.threshold = threshold
        self._scdet_available: Optional[bool] = None

    @property
    def scdet_available(self) -> bool:
        """Check if FFmpeg supports the scdet filter.

        Returns:
            True if scdet filter is available.
        """
        if self._scdet_available is None:
            self._scdet_available = self._check_scdet_support()
        return self._scdet_available

    def _check_scdet_support(self) -> bool:
        """Check if FFmpeg supports the scdet filter.

        Returns:
            True if scdet filter is available.
        """
        try:
            result = subprocess.run(
                ['ffmpeg', '-filters'],
                capture_output=True,
                text=True,
                check=True
            )
            # Look for 'scdet' in the filters list
            return 'scdet' in result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def detect_scenes(
        self,
        video_path: Path,
        threshold: Optional[float] = None
    ) -> list[float]:
        """Detect scene change timestamps in a video file.

        Args:
            video_path: Path to the video file.
            threshold: Override the default threshold for this detection.
                If None, uses the instance default.

        Returns:
            List of timestamps (in seconds) where scene changes were detected.
            Returns empty list if no changes detected or on graceful failure.

        Raises:
            FileNotFoundError: If the video file doesn't exist.
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        effective_threshold = threshold if threshold is not None else self.threshold

        # Try scdet filter first, fall back to select filter
        if self.scdet_available:
            return self._detect_with_scdet(video_path, effective_threshold)
        else:
            logger.warning(
                "FFmpeg scdet filter not available. "
                "Falling back to select filter for scene detection."
            )
            return self._detect_with_select(video_path, effective_threshold)

    def _detect_with_scdet(
        self,
        video_path: Path,
        threshold: float
    ) -> list[float]:
        """Detect scene changes using the scdet filter.

        Args:
            video_path: Path to the video file.
            threshold: Detection threshold.

        Returns:
            List of scene change timestamps.
        """
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-filter:v', f"scdet=s={threshold}",
            '-f', 'null',
            '-'
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return self._parse_scene_timestamps(result.stderr)

        except subprocess.CalledProcessError as e:
            logger.warning(
                f"Scene detection with scdet failed: {e.stderr}"
            )
            # Fall back to select filter
            return self._detect_with_select(video_path, threshold)

    def _detect_with_select(
        self,
        video_path: Path,
        threshold: float
    ) -> list[float]:
        """Detect scene changes using the select filter.

        This is a fallback when scdet is not available.

        Args:
            video_path: Path to the video file.
            threshold: Detection threshold.

        Returns:
            List of scene change timestamps.
        """
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-filter:v', f"select='gt(scene,{threshold})',showinfo",
            '-f', 'null',
            '-'
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )
            # FFmpeg may return non-zero but still output useful info
            return self._parse_showinfo_timestamps(result.stderr)

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(
                f"Scene detection with select filter failed: {e}"
            )
            return []

    def _parse_scene_timestamps(self, ffmpeg_output: str) -> list[float]:
        """Parse scene change timestamps from FFmpeg scdet output.

        The scdet filter outputs lines like:
            [Parsed_scdet_0 ...] lavfi.scdit.score=X pts_time:Y.YYY

        Args:
            ffmpeg_output: FFmpeg stderr output.

        Returns:
            Sorted list of unique timestamps.
        """
        timestamps = []

        # Match scdet output: pts_time:NUMBER
        pattern = r'pts_time:(\d+\.?\d*)'
        for match in re.finditer(pattern, ffmpeg_output):
            try:
                ts = float(match.group(1))
                timestamps.append(ts)
            except ValueError:
                continue

        return sorted(set(timestamps))

    def _parse_showinfo_timestamps(self, ffmpeg_output: str) -> list[float]:
        """Parse scene change timestamps from FFmpeg showinfo output.

        The select+showinfo filter outputs lines like:
            [Parsed_showinfo_1 ...] n:0 pts:Y pts_time:X.XXX ...

        Args:
            ffmpeg_output: FFmpeg stderr output.

        Returns:
            Sorted list of unique timestamps.
        """
        timestamps = []

        # Match showinfo output: pts_time:NUMBER
        pattern = r'pts_time:(\d+\.?\d*)'
        for match in re.finditer(pattern, ffmpeg_output):
            try:
                ts = float(match.group(1))
                timestamps.append(ts)
            except ValueError:
                continue

        return sorted(set(timestamps))


def generate_time_based_timestamps(
    duration: float,
    interval: float = 30.0,
    start: float = 0.0
) -> list[float]:
    """Generate evenly-spaced timestamps for time-based screenshot capture.

    Args:
        duration: Total video duration in seconds.
        interval: Time between screenshots in seconds. Default: 30.0.
        start: Start offset in seconds. Default: 0.0.

    Returns:
        List of timestamps from start to duration (exclusive).
    """
    if duration <= 0 or interval <= 0:
        return []

    timestamps = []
    t = start + interval  # Skip t=0, start at first interval

    while t < duration:
        timestamps.append(round(t, 3))
        t += interval

    return timestamps


def deduplicate_timestamps(
    *timestamp_lists: list[float],
    tolerance: float = 1.0
) -> list[float]:
    """Merge and deduplicate timestamps from multiple sources.

    Timestamps within `tolerance` seconds of each other are considered
    duplicates and only the first one is kept.

    Args:
        *timestamp_lists: Variable number of timestamp lists to merge.
        tolerance: Minimum gap between timestamps (seconds). Default: 1.0.

    Returns:
        Sorted, deduplicated list of timestamps.
    """
    # Flatten all lists
    all_timestamps = []
    for lst in timestamp_lists:
        all_timestamps.extend(lst)

    if not all_timestamps:
        return []

    # Sort by timestamp
    all_timestamps.sort()

    # Deduplicate with tolerance
    deduped = [all_timestamps[0]]
    for ts in all_timestamps[1:]:
        if ts - deduped[-1] >= tolerance:
            deduped.append(ts)

    return deduped
