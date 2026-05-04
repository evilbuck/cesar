"""
Markdown transcript formatter with speaker labels.

Formats aligned transcription segments into clean Markdown output with
speaker headers, timestamps, and metadata.

Accepts any segment with start, end, speaker, text attributes
(WhisperXSegment, AlignedSegment, etc.) via duck typing.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Any, Optional

from cesar.association import ScreenshotAssociation


def format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS.d (decisecond precision).

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like "01:23.4"
    """
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:04.1f}"


class MarkdownTranscriptFormatter:
    """Format aligned segments into Markdown with speaker labels."""

    def __init__(
        self,
        speaker_count: int,
        duration: float,
        min_segment_duration: float = 0.5,
    ):
        """Initialize formatter.

        Args:
            speaker_count: Number of speakers detected in audio
            duration: Total audio duration in seconds
            min_segment_duration: Minimum segment duration to include (default 0.5s)
        """
        self.speaker_count = speaker_count
        self.duration = duration
        self.min_segment_duration = min_segment_duration

    def format(self, segments: List[Any]) -> str:
        """Format segments into Markdown transcript.

        Accepts any segment with start, end, speaker, text attributes
        (WhisperXSegment, AlignedSegment, etc.) via duck typing.

        Args:
            segments: List of segments with speaker labels

        Returns:
            Formatted Markdown string with speaker headers and timestamps
        """
        # Filter segments by minimum duration
        filtered_segments = [
            seg for seg in segments
            if (seg.end - seg.start) >= self.min_segment_duration
        ]

        # Build metadata header
        output = self._build_metadata_header()

        # Add separator
        output += "\n---\n\n"

        # Add formatted segments
        output += self._format_segments(filtered_segments)

        return output

    def _build_metadata_header(self) -> str:
        """Build metadata header with speaker count, duration, and date."""
        # Format duration as MM:SS
        duration_minutes = int(self.duration // 60)
        duration_seconds = int(self.duration % 60)
        duration_str = f"{duration_minutes}:{duration_seconds:02d}"

        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")

        header = "# Transcript\n\n"
        header += f"**Speakers:** {self.speaker_count} detected\n"
        header += f"**Duration:** {duration_str}\n"
        header += f"**Created:** {today}\n"

        return header

    def _format_segments(self, segments: List[Any]) -> str:
        """Format segments with speaker headers and timestamps."""
        if not segments:
            return ""

        output = ""
        current_speaker = None

        for segment in segments:
            # Convert speaker label to human-friendly format
            speaker_label = self._format_speaker_label(segment.speaker)

            # Add speaker header if speaker changed
            if speaker_label != current_speaker:
                if current_speaker is not None:
                    output += "\n"  # Add blank line between different speakers
                output += f"### {speaker_label}\n"
                current_speaker = speaker_label

            # Add timestamp and text
            timestamp_str = f"[{format_timestamp(segment.start)} - {format_timestamp(segment.end)}]"
            output += f"{timestamp_str}\n"
            output += f"{segment.text}\n"

        return output

    def _format_speaker_label(self, speaker: str) -> str:
        """Convert speaker ID to human-friendly label.

        Args:
            speaker: Speaker ID (SPEAKER_00, SPEAKER_01, Multiple speakers, UNKNOWN)

        Returns:
            Human-friendly label (Speaker 1, Speaker 2, Multiple speakers, Unknown speaker)
        """
        if speaker == "Multiple speakers":
            return "Multiple speakers"
        elif speaker == "UNKNOWN":
            return "Unknown speaker"
        elif speaker.startswith("SPEAKER_"):
            # Convert SPEAKER_00 -> Speaker 1, SPEAKER_01 -> Speaker 2, etc.
            try:
                speaker_num = int(speaker.split("_")[1])
                return f"Speaker {speaker_num + 1}"
            except (IndexError, ValueError):
                return speaker
        else:
            return speaker


@dataclass
class ScreenshotReference:
    """Reference to a screenshot for Markdown output.

    Attributes:
        filename: Screenshot filename.
        timestamp: Capture time in seconds.
        trigger_type: How screenshot was triggered.
        segment_ids: IDs of associated transcript segments.
    """
    filename: str
    timestamp: float
    trigger_type: str
    segment_ids: list[str]


class AgentReviewMarkdownFormatter:
    """Format transcript and screenshots into Markdown for agent review.

    Generates Markdown with:
    - YAML frontmatter with metadata
    - Full transcript with speaker labels and timestamps
    - Screenshot references embedded at relevant points
    """

    def __init__(
        self,
        source_path: Path,
        duration: float,
        output_name: str,
        images_dir: Path,
    ):
        """Initialize agent-review formatter.

        Args:
            source_path: Path to the original media file.
            duration: Total media duration in seconds.
            output_name: Base name for output files.
            images_dir: Directory containing screenshots.
        """
        self.source_path = source_path
        self.duration = duration
        self.output_name = output_name
        self.images_dir = images_dir

    def format(
        self,
        segments: List[Any],
        screenshots: list[ScreenshotAssociation],
    ) -> str:
        """Format segments and screenshots into Markdown.

        Args:
            segments: List of transcript segments with start, end, speaker, text.
            screenshots: List of screenshot associations.

        Returns:
            Formatted Markdown string.
        """
        # Build frontmatter
        output = self._build_frontmatter()

        # Add separator
        output += "\n---\n\n"

        # Get unique speakers
        speakers = self._count_speakers(segments)

        # Add metadata section
        output += self._build_metadata_section(speakers)

        # Add transcript with screenshots
        output += "\n---\n\n"
        output += self._format_transcript_with_screenshots(segments, screenshots)

        return output

    def _build_frontmatter(self) -> str:
        """Build YAML frontmatter."""
        output = f"""---
mode: agent-review
source: {self.source_path.name}
duration: {self.duration:.1f}
images_dir: {self.images_dir.name}/
---
"""
        return output

    def _count_speakers(self, segments: List[Any]) -> int:
        """Count unique speakers in segments."""
        speakers = set()
        for seg in segments:
            if hasattr(seg, 'speaker') and seg.speaker:
                speakers.add(seg.speaker)
        return len(speakers) if speakers else 1

    def _build_metadata_section(self, speaker_count: int) -> str:
        """Build metadata section."""
        # Format duration as MM:SS
        duration_minutes = int(self.duration // 60)
        duration_seconds = int(self.duration % 60)
        duration_str = f"{duration_minutes}:{duration_seconds:02d}"

        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")

        return f"""# Agent Review

**Source:** {self.source_path.name}
**Duration:** {duration_str}
**Speakers:** {speaker_count} detected
**Date:** {today}
"""

    def _format_transcript_with_screenshots(
        self,
        segments: List[Any],
        screenshots: list[ScreenshotAssociation],
    ) -> str:
        """Format transcript with screenshots embedded at relevant points.

        Args:
            segments: Transcript segments.
            screenshots: Screenshot associations.

        Returns:
            Formatted transcript string.
        """
        if not segments:
            return "*No transcript segments available.*"

        # Build a map of timestamps to screenshots for quick lookup
        # A screenshot appears when its timestamp falls within a segment's range
        screenshot_by_segment: dict[str, list[ScreenshotAssociation]] = {}
        for assoc in screenshots:
            for seg in assoc.segments:
                seg_id = seg.segment_id or ""
                if seg_id not in screenshot_by_segment:
                    screenshot_by_segment[seg_id] = []
                screenshot_by_segment[seg_id].append(assoc)

        output = "## Transcript\n\n"
        current_speaker = None

        for seg in segments:
            # Skip very short/empty segments
            if seg.end - seg.start < 0.1 or not seg.text.strip():
                continue

            # Convert speaker label
            speaker_label = self._format_speaker_label(seg.speaker) if seg.speaker else "Unknown"

            # Add speaker header if changed
            if speaker_label != current_speaker:
                if current_speaker is not None:
                    output += "\n"
                output += f"### {speaker_label}\n\n"
                current_speaker = speaker_label

            # Add timestamp
            start_str = format_timestamp(seg.start)
            end_str = format_timestamp(seg.end)
            output += f"[{start_str} - {end_str}]\n"

            # Add transcript text
            output += f"{seg.text}\n\n"

            # Insert screenshots for this segment
            seg_id = seg.segment_id or ""
            if seg_id in screenshot_by_segment:
                for assoc in screenshot_by_segment[seg_id]:
                    output += self._format_screenshot_block(assoc)
                    output += "\n"

        return output

    def _format_screenshot_block(self, assoc: ScreenshotAssociation) -> str:
        """Format a screenshot as a Markdown block.

        Args:
            assoc: Screenshot association.

        Returns:
            Formatted screenshot block.
        """
        # Build relative path to image
        image_path = self.images_dir / assoc.filename

        # Format timestamp for display
        ts_str = format_timestamp(assoc.timestamp)

        # Build trigger type label
        trigger_labels = {
            "time": "Time-based",
            "speech_cue": "Speech cue",
            "scene_change": "Scene change",
        }
        trigger_label = trigger_labels.get(assoc.trigger_type, assoc.trigger_type)

        # Build caption with cue word if present
        caption_parts = [f"Screenshot at {ts_str} ({trigger_label})"]
        if assoc.cue_word:
            caption_parts.append(f'cue: "{assoc.cue_word}"')
        caption = ", ".join(caption_parts)

        return f'![{caption}]({image_path}){{ .screenshot }}\n'

    def _format_speaker_label(self, speaker: Optional[str]) -> str:
        """Convert speaker ID to human-friendly label."""
        if not speaker:
            return "Unknown"
        if speaker == "Multiple speakers":
            return "Multiple speakers"
        elif speaker == "UNKNOWN":
            return "Unknown speaker"
        elif speaker.startswith("SPEAKER_"):
            try:
                speaker_num = int(speaker.split("_")[1])
                return f"Speaker {speaker_num + 1}"
            except (IndexError, ValueError):
                return speaker
        else:
            return speaker
