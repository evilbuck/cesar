"""
Speech cue detector for transcript segments.

Scans transcript segments for trigger words (cue phrases) and returns
timestamps where those cues occur. Used to determine screenshot capture
points during agent-review mode.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# Default cue words that indicate the speaker is referencing something visual
DEFAULT_SPEECH_CUES = [
    "this",
    "here",
    "that",
    "look at",
    "notice",
    "pay attention",
    "see how",
    "issue",
    "problem",
    "bug",
    "wrong",
    "broken",
]


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio with timing information.

    Attributes:
        start: Start time in seconds.
        end: End time in seconds.
        text: The transcribed text content.
        speaker: Optional speaker label (e.g., "SPEAKER_00").
        segment_id: Optional segment identifier (e.g., "seg_001").
    """
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    segment_id: Optional[str] = None


@dataclass
class CueMatch:
    """A detected speech cue within a transcript segment.

    Attributes:
        timestamp: The start time of the segment containing the cue.
        cue_word: The cue word or phrase that was matched.
        segment_text: Full text of the matching segment.
        segment_id: ID of the matching segment (if available).
        speaker: Speaker label for the matching segment (if available).
    """
    timestamp: float
    cue_word: str
    segment_text: str
    segment_id: Optional[str] = None
    speaker: Optional[str] = None


class SpeechCueDetector:
    """Detects speech cue words in transcript segments.

    Scans transcript text for configurable trigger words/phrases and
    returns timestamps where cues were found. Used to trigger screenshot
    captures at moments when a speaker is likely referencing visual content.
    """

    def __init__(self, cue_words: Optional[list[str]] = None):
        """Initialize the speech cue detector.

        Args:
            cue_words: List of cue words/phrases to detect (case-insensitive).
                If None, uses DEFAULT_SPEECH_CUES.
        """
        self.cue_words = cue_words if cue_words is not None else list(DEFAULT_SPEECH_CUES)
        # Pre-compile lowercase versions for efficient matching
        self._cue_words_lower = [cue.lower() for cue in self.cue_words]

    def detect_cues(
        self,
        segments: list[TranscriptSegment],
    ) -> list[CueMatch]:
        """Find all speech cue matches in transcript segments.

        Args:
            segments: List of transcript segments to scan.

        Returns:
            List of CueMatch objects, one per segment that contains
            at least one cue word. Multiple cue words in the same
            segment produce only one CueMatch (the first cue found).
        """
        matches = []

        for segment in segments:
            text_lower = segment.text.lower()
            for cue_lower, cue_original in zip(self._cue_words_lower, self.cue_words):
                if cue_lower in text_lower:
                    matches.append(CueMatch(
                        timestamp=segment.start,
                        cue_word=cue_original,
                        segment_text=segment.text,
                        segment_id=segment.segment_id,
                        speaker=segment.speaker,
                    ))
                    break  # Only one match per segment

        return matches

    def get_cue_timestamps(
        self,
        segments: list[TranscriptSegment],
    ) -> list[float]:
        """Get timestamps of segments containing speech cues.

        Convenience method that returns just the timestamps without
        the full match details.

        Args:
            segments: List of transcript segments to scan.

        Returns:
            Sorted list of unique timestamps where cues were found.
        """
        matches = self.detect_cues(segments)
        timestamps = list({m.timestamp for m in matches})
        return sorted(timestamps)

    @staticmethod
    def parse_cue_string(cue_string: str) -> list[str]:
        """Parse a comma-separated cue word string into a list.

        Args:
            cue_string: Comma-separated cue words (e.g., "this,here,that").

        Returns:
            List of stripped, non-empty cue words.
        """
        return [cue.strip() for cue in cue_string.split(",") if cue.strip()]
