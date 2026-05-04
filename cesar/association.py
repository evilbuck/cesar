"""
Screenshot-to-transcript segment association.

Maps screenshot timestamps to overlapping transcript segments for
agent-review mode output generation.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from cesar.transcriber import TranscriptionSegment

logger = logging.getLogger(__name__)


@dataclass
class ScreenshotAssociation:
    """Association between a screenshot and transcript segments.

    Attributes:
        timestamp: Screenshot capture time in seconds.
        filename: Screenshot filename (e.g., "recording_00-01-23.png").
        trigger_type: How this screenshot was triggered
            ("time", "speech_cue", "scene_change").
        segments: List of transcript segments overlapping this timestamp.
        cue_word: The speech cue that triggered this screenshot
            (if trigger_type is "speech_cue").
    """
    timestamp: float
    filename: str
    trigger_type: str  # "time", "speech_cue", "scene_change"
    segments: list[TranscriptionSegment]
    cue_word: Optional[str] = None


def associate_screenshots(
    screenshot_timestamps: list[tuple[float, str]],
    segments: list[TranscriptionSegment],
    trigger_type: str = "time",
    tolerance: float = 2.0,
) -> list[ScreenshotAssociation]:
    """Associate screenshots with overlapping transcript segments.

    For each screenshot timestamp, finds all transcript segments whose
    time range overlaps with the timestamp (within tolerance).

    Args:
        screenshot_timestamps: List of (timestamp, filename) tuples.
        segments: Transcript segments with start/end times.
        trigger_type: Type of trigger for all screenshots in this batch.
        tolerance: Seconds before/after timestamp to consider overlapping.
            Default: 2.0 (matches segments within ±2s of screenshot).

    Returns:
        List of ScreenshotAssociation objects.
    """
    associations = []

    for timestamp, filename in screenshot_timestamps:
        overlapping = []
        for seg in segments:
            # Check if segment overlaps with [timestamp - tolerance, timestamp + tolerance]
            if seg.start <= timestamp + tolerance and seg.end >= timestamp - tolerance:
                overlapping.append(seg)

        associations.append(ScreenshotAssociation(
            timestamp=timestamp,
            filename=filename,
            trigger_type=trigger_type,
            segments=overlapping,
        ))

    return associations


def format_timestamp_for_filename(seconds: float) -> str:
    """Format a timestamp in seconds to HH-MM-SS for screenshot naming.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted string like "00-01-23".
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}-{minutes:02d}-{secs:02d}"
