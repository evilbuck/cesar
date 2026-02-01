"""
Timestamp alignment between transcription and speaker diarization.

Aligns Whisper transcription segments to pyannote speaker segments using
temporal intersection. Handles segment splitting at speaker changes and
overlapping speech detection.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from cesar.diarization import DiarizationResult, SpeakerSegment

logger = logging.getLogger(__name__)

# Warning threshold: segments with <30% overlap get logged
ALIGNMENT_WARNING_THRESHOLD = 0.30


@dataclass
class TranscriptionSegment:
    """Input segment from Whisper transcription."""
    start: float
    end: float
    text: str


@dataclass
class AlignedSegment:
    """Output segment with speaker label."""
    start: float
    end: float
    speaker: str  # "SPEAKER_00", "SPEAKER_01", "Multiple speakers", or "UNKNOWN"
    text: str


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


def _calculate_intersection(seg_start: float, seg_end: float,
                             spk_start: float, spk_end: float) -> float:
    """Calculate intersection length between two time ranges."""
    intersection_start = max(seg_start, spk_start)
    intersection_end = min(seg_end, spk_end)

    if intersection_start < intersection_end:
        return intersection_end - intersection_start
    return 0.0


def _find_speakers_in_range(start: float, end: float,
                             diarization: DiarizationResult) -> list[tuple[str, float, float]]:
    """Find all speakers active during a time range.

    Returns:
        List of (speaker, overlap_start, overlap_end) tuples
    """
    speakers = []
    for seg in diarization.segments:
        intersection = _calculate_intersection(start, end, seg.start, seg.end)
        if intersection > 0:
            overlap_start = max(start, seg.start)
            overlap_end = min(end, seg.end)
            speakers.append((seg.speaker, overlap_start, overlap_end))
    return speakers


def _detect_overlapping_speech(speakers: list[tuple[str, float, float]]) -> bool:
    """Detect if multiple speakers overlap significantly.

    Two speakers are considered overlapping if their active regions
    within the segment overlap by more than 0.5 seconds.
    """
    if len(speakers) <= 1:
        return False

    # Check pairwise overlap
    for i, (_, start1, end1) in enumerate(speakers):
        for j, (_, start2, end2) in enumerate(speakers[i+1:], i+1):
            overlap = _calculate_intersection(start1, end1, start2, end2)
            if overlap > 0.5:  # 500ms threshold
                return True
    return False


def align_timestamps(
    transcription_segments: list[TranscriptionSegment],
    diarization: DiarizationResult,
) -> list[AlignedSegment]:
    """Align transcription segments to speaker labels.

    Uses temporal intersection to assign speakers. If a transcription segment
    spans multiple speakers, it is split at speaker change boundaries.

    Args:
        transcription_segments: Segments from Whisper transcription
        diarization: Diarization result with speaker segments

    Returns:
        List of AlignedSegment with speaker labels

    Note:
        - Segments with <30% overlap get a warning logged
        - Overlapping speech (multiple speakers at same time) is marked
        - Single speaker in entire audio means all segments get that speaker
    """
    aligned = []

    # Handle single speaker case - no splitting needed
    if diarization.speaker_count == 1:
        single_speaker = diarization.segments[0].speaker if diarization.segments else "UNKNOWN"
        for seg in transcription_segments:
            aligned.append(AlignedSegment(
                start=seg.start,
                end=seg.end,
                speaker=single_speaker,
                text=seg.text
            ))
        return aligned

    # Multiple speakers - need to split at boundaries
    for seg in transcription_segments:
        speakers_in_range = _find_speakers_in_range(seg.start, seg.end, diarization)

        if not speakers_in_range:
            # No speaker found for this segment
            logger.warning(
                f"No speaker found for segment [{format_timestamp(seg.start)} - "
                f"{format_timestamp(seg.end)}]: '{seg.text[:50]}...'"
            )
            aligned.append(AlignedSegment(
                start=seg.start,
                end=seg.end,
                speaker="UNKNOWN",
                text=seg.text
            ))
            continue

        if len(speakers_in_range) == 1:
            # Single speaker covers this segment
            speaker, _, _ = speakers_in_range[0]
            segment_duration = seg.end - seg.start
            _, overlap_start, overlap_end = speakers_in_range[0]
            overlap_duration = overlap_end - overlap_start
            overlap_ratio = overlap_duration / segment_duration if segment_duration > 0 else 0

            if overlap_ratio < ALIGNMENT_WARNING_THRESHOLD:
                logger.warning(
                    f"Low alignment confidence ({overlap_ratio:.0%}) for segment "
                    f"[{format_timestamp(seg.start)} - {format_timestamp(seg.end)}]"
                )

            aligned.append(AlignedSegment(
                start=seg.start,
                end=seg.end,
                speaker=speaker,
                text=seg.text
            ))
        else:
            # Multiple speakers in segment - check for overlap or split
            if _detect_overlapping_speech(speakers_in_range):
                # True overlap - mark as multiple speakers
                aligned.append(AlignedSegment(
                    start=seg.start,
                    end=seg.end,
                    speaker="Multiple speakers",
                    text=seg.text
                ))
            else:
                # Sequential speakers - split segment at boundaries
                # Sort by overlap start time
                speakers_in_range.sort(key=lambda x: x[1])

                # For text splitting, we distribute proportionally by time
                words = seg.text.split()
                total_duration = seg.end - seg.start
                word_idx = 0

                for i, (speaker, overlap_start, overlap_end) in enumerate(speakers_in_range):
                    # Calculate proportion of words for this speaker
                    speaker_duration = overlap_end - overlap_start
                    proportion = speaker_duration / total_duration if total_duration > 0 else 0

                    # Assign words proportionally
                    if i == len(speakers_in_range) - 1:
                        # Last speaker gets remaining words
                        speaker_words = words[word_idx:]
                    else:
                        word_count = max(1, int(len(words) * proportion))
                        speaker_words = words[word_idx:word_idx + word_count]
                        word_idx += word_count

                    if speaker_words:
                        aligned.append(AlignedSegment(
                            start=overlap_start,
                            end=overlap_end,
                            speaker=speaker,
                            text=" ".join(speaker_words)
                        ))

    return aligned


def should_include_speaker_labels(diarization: DiarizationResult) -> bool:
    """Determine if speaker labels should be included in output.

    Returns False for single-speaker audio (output looks like normal transcription).

    Args:
        diarization: Diarization result

    Returns:
        True if speaker labels should be shown, False for single speaker
    """
    return diarization.speaker_count > 1
