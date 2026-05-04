"""
JSON sidecar generator for agent-review mode.

Produces a machine-readable sidecar file containing:
- Review metadata (source, duration, timestamps)
- Full transcript with segment details
- Screenshot information with associations
"""
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from cesar.association import ScreenshotAssociation
from cesar.transcriber import TranscriptionSegment

logger = logging.getLogger(__name__)


@dataclass
class ReviewMetadata:
    """Metadata for the agent review artifact.

    Attributes:
        mode: Always "agent-review" for this sidecar type.
        source: Path to the original media file.
        output_name: Base name used for output files.
        duration: Total media duration in seconds.
        created_at: ISO 8601 timestamp of generation.
        screenshots_interval: Time interval for time-based screenshots.
        speech_cues_enabled: Whether speech cue detection was enabled.
        scene_detection_enabled: Whether scene detection was enabled.
    """
    mode: str = "agent-review"
    source: str = ""
    output_name: str = ""
    duration: float = 0.0
    created_at: str = ""
    screenshots_interval: int = 30
    speech_cues_enabled: bool = True
    scene_detection_enabled: bool = True


@dataclass
class SegmentData:
    """Serialized segment data for JSON output.

    Attributes:
        id: Segment identifier (e.g., "seg_001").
        start: Start time in seconds.
        end: End time in seconds.
        text: Transcribed text.
        speaker: Speaker label if available.
    """
    id: str
    start: float
    end: float
    text: str
    speaker: Optional[str] = None


@dataclass
class ScreenshotData:
    """Serialized screenshot data for JSON output.

    Attributes:
        filename: Screenshot filename.
        timestamp: Capture time in seconds.
        trigger_type: How screenshot was triggered ("time", "speech_cue", "scene_change").
        associated_segment_ids: IDs of overlapping transcript segments.
        cue_word: Speech cue that triggered capture (if applicable).
    """
    filename: str
    timestamp: float
    trigger_type: str
    associated_segment_ids: list[str]
    cue_word: Optional[str] = None


@dataclass
class ReviewSidecar:
    """Complete sidecar data structure.

    Attributes:
        metadata: Review metadata.
        transcript: List of transcript segments.
        screenshots: List of screenshot data with associations.
    """
    metadata: ReviewMetadata
    transcript: list[SegmentData]
    screenshots: list[ScreenshotData]


class SidecarGenerator:
    """Generate JSON sidecar files for agent-review mode."""

    def __init__(self, output_dir: Path, output_name: str, source_path: Path, duration: float):
        """Initialize sidecar generator.

        Args:
            output_dir: Directory where all output artifacts are placed.
            output_name: Base name for output files (e.g., "review").
                        The sidecar will be saved as
                        ``{output_dir}/{output_name}.sidecar.json``.
            source_path: Path to the original media file.
            duration: Total media duration in seconds.
        """
        self.output_dir = output_dir
        self.output_name = output_name
        self.source_path = source_path
        self.duration = duration

        # Build sidecar path inside the output directory
        self.sidecar_path = output_dir / f"{output_name}.sidecar.json"

        # Set default values that can be configured
        self._screenshots_interval = 30
        self._speech_cues_enabled = True
        self._scene_detection_enabled = True

    def configure(
        self,
        screenshots_interval: int = 30,
        speech_cues_enabled: bool = True,
        scene_detection_enabled: bool = True
    ) -> None:
        """Configure generation options.

        Args:
            screenshots_interval: Time interval for time-based screenshots.
            speech_cues_enabled: Whether speech cue detection was used.
            scene_detection_enabled: Whether scene detection was used.
        """
        self._screenshots_interval = screenshots_interval
        self._speech_cues_enabled = speech_cues_enabled
        self._scene_detection_enabled = scene_detection_enabled

    def _build_metadata(self) -> ReviewMetadata:
        """Build review metadata."""
        return ReviewMetadata(
            mode="agent-review",
            source=str(self.source_path),
            output_name=self.output_name,
            duration=self.duration,
            created_at=datetime.now().isoformat(),
            screenshots_interval=self._screenshots_interval,
            speech_cues_enabled=self._speech_cues_enabled,
            scene_detection_enabled=self._scene_detection_enabled,
        )

    def _serialize_segments(
        self, segments: list[TranscriptionSegment]
    ) -> list[SegmentData]:
        """Serialize transcript segments to JSON-safe format."""
        result = []
        for seg in segments:
            # Skip segments with zero duration (likely empty)
            if seg.end - seg.start < 0.1:
                continue

            result.append(SegmentData(
                id=seg.segment_id or "",
                start=round(seg.start, 3),
                end=round(seg.end, 3),
                text=seg.text,
                speaker=seg.speaker,
            ))
        return result

    def _serialize_screenshots(
        self, associations: list[ScreenshotAssociation]
    ) -> list[ScreenshotData]:
        """Serialize screenshot associations to JSON-safe format."""
        result = []
        for assoc in associations:
            # Collect segment IDs from overlapping segments
            segment_ids = [
                seg.segment_id or ""
                for seg in assoc.segments
                if seg.segment_id
            ]

            result.append(ScreenshotData(
                filename=assoc.filename,
                timestamp=round(assoc.timestamp, 3),
                trigger_type=assoc.trigger_type,
                associated_segment_ids=segment_ids,
                cue_word=assoc.cue_word,
            ))
        return result

    def generate(
        self,
        segments: list[TranscriptionSegment],
        associations: list[ScreenshotAssociation],
    ) -> Path:
        """Generate and save the JSON sidecar file.

        Args:
            segments: Transcript segments.
            associations: Screenshot-to-segment associations.

        Returns:
            Path to the generated sidecar file.
        """
        # Build the complete sidecar structure
        sidecar = ReviewSidecar(
            metadata=self._build_metadata(),
            transcript=self._serialize_segments(segments),
            screenshots=self._serialize_screenshots(associations),
        )

        # Convert to dict for JSON serialization
        sidecar_dict = {
            "metadata": asdict(sidecar.metadata),
            "transcript": [asdict(s) for s in sidecar.transcript],
            "screenshots": [asdict(s) for s in sidecar.screenshots],
        }

        # Write to file
        with open(self.sidecar_path, 'w', encoding='utf-8') as f:
            json.dump(sidecar_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"Generated sidecar: {self.sidecar_path}")
        return self.sidecar_path

    def to_dict(
        self,
        segments: list[TranscriptionSegment],
        associations: list[ScreenshotAssociation],
    ) -> dict[str, Any]:
        """Generate sidecar data as a dictionary (for testing/debugging).

        Args:
            segments: Transcript segments.
            associations: Screenshot-to-segment associations.

        Returns:
            Dictionary representation of the sidecar.
        """
        sidecar = ReviewSidecar(
            metadata=self._build_metadata(),
            transcript=self._serialize_segments(segments),
            screenshots=self._serialize_screenshots(associations),
        )

        return {
            "metadata": asdict(sidecar.metadata),
            "transcript": [asdict(s) for s in sidecar.transcript],
            "screenshots": [asdict(s) for s in sidecar.screenshots],
        }
