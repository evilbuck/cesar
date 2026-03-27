"""
Speaker diarization types and exceptions.

This module provides exception classes for diarization errors and data types
for backward compatibility. The actual diarization implementation has been
replaced by WhisperX pipeline (see cesar.whisperx_wrapper).
"""
from dataclasses import dataclass


class DiarizationError(Exception):
    """Base exception for diarization errors."""
    pass


class AuthenticationError(DiarizationError):
    """HuggingFace authentication failed."""
    pass


@dataclass
class SpeakerSegment:
    """A single speaker segment with timing information.

    Attributes:
        start: Start time in seconds
        end: End time in seconds
        speaker: Speaker label (SPEAKER_00, SPEAKER_01, etc.)
    """
    start: float
    end: float
    speaker: str


@dataclass
class DiarizationResult:
    """Result of speaker diarization analysis.

    Attributes:
        segments: List of speaker segments with timing
        speaker_count: Number of unique speakers detected
        audio_duration: Total audio duration in seconds
    """
    segments: list[SpeakerSegment]
    speaker_count: int
    audio_duration: float
