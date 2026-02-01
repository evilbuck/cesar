"""
Markdown transcript formatter with speaker labels.

Formats aligned transcription segments into clean Markdown output with
speaker headers, timestamps, and metadata.
"""
from datetime import datetime
from typing import List

from cesar.timestamp_aligner import AlignedSegment, format_timestamp


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

    def format(self, segments: List[AlignedSegment]) -> str:
        """Format aligned segments into Markdown transcript.

        Args:
            segments: List of aligned segments with speaker labels

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

    def _format_segments(self, segments: List[AlignedSegment]) -> str:
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
