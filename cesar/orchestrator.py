"""
Orchestrator for coordinating transcription and formatting pipeline.

Provides a single entry point that runs the WhisperX unified pipeline for
transcription with speaker diarization, with graceful fallback to plain
transcription using AudioTranscriber when diarization fails.
"""
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any

from cesar.transcriber import AudioTranscriber, TranscriptionSegment
from cesar.diarization import DiarizationError, AuthenticationError
from cesar.whisperx_wrapper import WhisperXPipeline, WhisperXSegment
from cesar.transcript_formatter import MarkdownTranscriptFormatter
from cesar.video_processor import VideoProcessor
from cesar.ffmpeg_scene_detector import FFmpegSceneDetector
from cesar.speech_cue_detector import SpeechCueDetector
from cesar.association import (
    associate_screenshots,
    format_timestamp_for_filename,
)
from cesar.sidecar_generator import SidecarGenerator
from cesar.transcript_formatter import AgentReviewMarkdownFormatter

logger = logging.getLogger(__name__)


class FormattingError(Exception):
    """Error during transcript formatting."""
    pass


@dataclass(frozen=True)
class OrchestrationResult:
    """Result of full transcription orchestration.

    Attributes:
        output_path: Path to final output file (.md or .txt)
        speakers_detected: Number of speakers found (0 if diarization disabled/failed)
        audio_duration: Total audio duration in seconds
        transcription_time: Time spent on transcription in seconds
        diarization_time: Time spent on diarization in seconds (None if disabled/failed)
        formatting_time: Time spent on formatting in seconds
        diarization_succeeded: Whether diarization completed successfully
    """
    output_path: Path
    speakers_detected: int
    audio_duration: float
    transcription_time: float
    diarization_time: Optional[float]
    formatting_time: float
    diarization_succeeded: bool

    @property
    def total_processing_time(self) -> float:
        """Total processing time across all steps."""
        total = self.transcription_time + self.formatting_time
        if self.diarization_time is not None:
            total += self.diarization_time
        return total

    @property
    def speed_ratio(self) -> float:
        """Speed ratio: audio_duration / processing_time."""
        if self.total_processing_time > 0:
            return self.audio_duration / self.total_processing_time
        return 0.0


class TranscriptionOrchestrator:
    """Orchestrate WhisperX pipeline with graceful fallback.

    Uses WhisperXPipeline for unified transcription with speaker diarization.
    Falls back to AudioTranscriber for plain transcription when diarization
    fails or is disabled.
    """

    def __init__(
        self,
        pipeline: Optional[WhisperXPipeline] = None,
        transcriber: Optional[AudioTranscriber] = None,
        formatter: Optional[MarkdownTranscriptFormatter] = None
    ):
        """Initialize orchestrator with components.

        Args:
            pipeline: Optional WhisperXPipeline for transcription with diarization
            transcriber: Optional AudioTranscriber for fallback plain transcription
            formatter: Optional MarkdownTranscriptFormatter for formatting
                      (created automatically if not provided)
        """
        self.pipeline = pipeline
        self.transcriber = transcriber
        self.formatter = formatter

    def orchestrate(
        self,
        audio_path: Path,
        output_path: Path,
        enable_diarization: bool = True,
        keep_intermediate: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> OrchestrationResult:
        """Run transcription with optional diarization.

        Gracefully falls back to plain transcript if diarization fails.

        Args:
            audio_path: Path to input audio file
            output_path: Path to output file (extension may be changed)
            enable_diarization: Whether to run speaker diarization
            keep_intermediate: Whether to save intermediate debug files
            progress_callback: Optional callback for progress updates
                              Called with (step_name, overall_percentage)
            min_speakers: Minimum expected speakers (passed to pipeline)
            max_speakers: Maximum expected speakers (passed to pipeline)

        Returns:
            OrchestrationResult with metrics and output path

        Raises:
            ValueError: If neither pipeline nor transcriber provided
            AuthenticationError: If HuggingFace authentication fails

        Note:
            Diarization errors trigger fallback to plain transcript with warning logs.
            AuthenticationError is always re-raised for user to fix HF token.
        """
        # Track timing for each step
        pipeline_time = 0.0
        transcription_time = 0.0
        diarization_time = None
        formatting_time = 0.0
        diarization_succeeded = False
        speakers_detected = 0
        audio_duration = 0.0

        # Wrap progress callback to scale pipeline progress to 0-90%
        def scaled_progress(phase: str, pct: float) -> None:
            if progress_callback:
                # Scale pipeline progress (0-100%) to (0-90%)
                progress_callback(phase, pct * 0.9)

        # Attempt full pipeline with diarization
        if enable_diarization and self.pipeline is not None:
            try:
                if progress_callback:
                    progress_callback("Starting pipeline...", 0.0)

                start = time.time()
                segments, speakers_detected, audio_duration = self.pipeline.transcribe_and_diarize(
                    str(audio_path),
                    min_speakers=min_speakers,
                    max_speakers=max_speakers,
                    progress_callback=scaled_progress
                )
                pipeline_time = time.time() - start
                # For timing purposes, treat pipeline time as combined transcription + diarization
                transcription_time = pipeline_time * 0.6  # Approximate transcription portion
                diarization_time = pipeline_time * 0.4   # Approximate diarization portion
                diarization_succeeded = True

                if progress_callback:
                    progress_callback("Pipeline complete", 90.0)

                # Save intermediate diarization data if requested
                if keep_intermediate:
                    self._save_intermediate_diarization(segments, speakers_detected, output_path)

            except AuthenticationError:
                # Authentication errors should propagate - user must fix HF token
                raise

            except DiarizationError as e:
                # Diarization failed, attempt fallback to plain transcription
                logger.warning(
                    f"Transcription succeeded, diarization failed: {e}. "
                    f"Falling back to plain transcript."
                )

                if self.transcriber is not None:
                    # Fall back to plain transcription
                    segments, audio_duration, transcription_time = self._transcribe_fallback(
                        audio_path, progress_callback
                    )
                    diarization_succeeded = False
                else:
                    # No fallback available
                    raise DiarizationError(
                        f"Diarization failed and no fallback transcriber available: {e}"
                    ) from e

            except Exception as e:
                # Wrap unknown exceptions
                logger.error(f"Pipeline failed with unexpected error: {e}")
                raise DiarizationError(f"Pipeline failed: {e}") from e

        elif self.transcriber is not None:
            # Diarization disabled or no pipeline - use plain transcription
            segments, audio_duration, transcription_time = self._transcribe_fallback(
                audio_path, progress_callback
            )
            diarization_succeeded = False

        else:
            raise ValueError(
                "Transcription requires either pipeline (for diarization) or transcriber (for plain transcription)"
            )

        # Step: Format and save (90-100%)
        if progress_callback:
            progress_callback("Formatting...", 90.0)

        start = time.time()

        if diarization_succeeded:
            # Format with speaker labels
            try:
                # Create formatter if not provided
                formatter = self.formatter or MarkdownTranscriptFormatter(
                    speaker_count=speakers_detected,
                    duration=audio_duration
                )

                formatted_text = formatter.format(segments)

                # Ensure output has .md extension
                final_output = output_path.with_suffix('.md')
                if final_output != output_path:
                    logger.info("Changed output extension to .md for speaker-labeled transcript")

                with open(final_output, 'w', encoding='utf-8') as f:
                    f.write(formatted_text)

            except Exception as e:
                logger.warning(f"Formatting failed: {e}. Falling back to plain transcript.")
                final_output = self._save_plain_transcript(segments, output_path)
                diarization_succeeded = False
        else:
            # Save plain transcript
            final_output = self._save_plain_transcript(segments, output_path)

        formatting_time = time.time() - start

        if progress_callback:
            progress_callback("Complete", 100.0)

        return OrchestrationResult(
            output_path=final_output,
            speakers_detected=speakers_detected,
            audio_duration=audio_duration,
            transcription_time=transcription_time,
            diarization_time=diarization_time,
            formatting_time=formatting_time,
            diarization_succeeded=diarization_succeeded
        )

    def _transcribe_fallback(
        self,
        audio_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> tuple[list, float, float]:
        """Perform plain transcription as fallback.

        Args:
            audio_path: Path to audio file
            progress_callback: Progress callback

        Returns:
            Tuple of (segments, audio_duration, transcription_time)
        """
        if progress_callback:
            progress_callback("Transcribing (plain)...", 0.0)

        start = time.time()
        segments, metadata = self.transcriber.transcribe_to_segments(
            str(audio_path),
            progress_callback=lambda pct, count, elapsed: progress_callback(
                "Transcribing...", pct * 0.9 / 100
            ) if progress_callback else None
        )
        transcription_time = time.time() - start
        audio_duration = metadata['audio_duration']

        if progress_callback:
            progress_callback("Transcription complete", 90.0)

        return segments, audio_duration, transcription_time

    def _save_intermediate_diarization(
        self,
        segments: list[WhisperXSegment],
        speaker_count: int,
        output_path: Path
    ) -> None:
        """Save intermediate diarization data for debugging.

        Args:
            segments: WhisperX segments with speaker labels
            speaker_count: Number of detected speakers
            output_path: Base output path
        """
        import json
        intermediate_path = output_path.parent / f"{output_path.stem}_diarization.json"
        with open(intermediate_path, 'w', encoding='utf-8') as f:
            data = {
                'speaker_count': speaker_count,
                'segments': [
                    {
                        'start': seg.start,
                        'end': seg.end,
                        'speaker': seg.speaker,
                        'text': seg.text
                    }
                    for seg in segments
                ]
            }
            json.dump(data, f, indent=2)
        logger.info(f"Saved intermediate diarization: {intermediate_path}")

    def _save_plain_transcript(self, segments: list, output_path: Path) -> Path:
        """Save plain text transcript without speaker labels.

        Args:
            segments: Transcription segments (TranscriptionSegment or WhisperXSegment)
            output_path: Desired output path

        Returns:
            Actual output path (.txt extension)
        """
        # Ensure output has .txt extension
        final_output = output_path.with_suffix('.txt')
        if final_output != output_path:
            logger.info("Changed output extension to .txt for plain transcript")

        with open(final_output, 'w', encoding='utf-8') as f:
            f.write("# Transcript\n\n")
            f.write("(Speaker detection unavailable)\n\n")
            for seg in segments:
                f.write(f"{seg.text}\n")

        logger.info("Saved plain transcript (speaker detection unavailable)")
        return final_output


@dataclass
class AgentReviewResult:
    """Result of agent-review mode processing.

    Attributes:
        output_path: Path to final output Markdown file
        sidecar_path: Path to JSON sidecar file
        images_dir: Directory containing screenshots
        screenshots_count: Number of screenshots extracted
        segments_count: Number of transcript segments
        speakers_detected: Number of speakers found
        audio_duration: Total media duration in seconds
        processing_time: Total processing time in seconds
        transcription_time: Time spent on transcription
        screenshot_time: Time spent on screenshot extraction
        formatting_time: Time spent on output formatting
    """
    output_path: Path
    sidecar_path: Path
    images_dir: Path
    screenshots_count: int
    segments_count: int
    speakers_detected: int
    audio_duration: float
    processing_time: float
    transcription_time: float
    screenshot_time: float
    formatting_time: float


class AgentReviewOrchestrator:
    """Orchestrate agent-review mode processing pipeline.

    Coordinates:
    1. Video metadata extraction
    2. Audio transcription with diarization
    3. Screenshot trigger detection (time-based, speech cues, scene changes)
    4. Screenshot extraction via FFmpeg
    5. Screenshot-to-segment association
    6. Markdown + JSON sidecar output generation
    """

    def __init__(
        self,
        pipeline: Optional[WhisperXPipeline] = None,
        transcriber: Optional[AudioTranscriber] = None,
    ):
        """Initialize agent-review orchestrator.

        Args:
            pipeline: Optional WhisperXPipeline for transcription with diarization.
                     If None, uses transcriber only.
            transcriber: AudioTranscriber for plain transcription fallback.
        """
        self.pipeline = pipeline
        self.transcriber = transcriber
        self._video_processor = VideoProcessor()
        self._scene_detector = FFmpegSceneDetector()

    def orchestrate(
        self,
        video_path: Path,
        output_path: Path,
        screenshots_interval: int = 30,
        speech_cues: Optional[list[str]] = None,
        scene_threshold: float = 0.3,
        enable_scene_detection: bool = True,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> AgentReviewResult:
        """Run complete agent-review pipeline.

        Args:
            video_path: Path to input video file.
            output_path: Path for output Markdown file (without extension).
            screenshots_interval: Seconds between time-based screenshots.
            speech_cues: List of trigger words for speech cue detection.
                        None uses default list.
            scene_threshold: Scene detection threshold (0.0-1.0).
            enable_scene_detection: Whether to enable scene change detection.
            progress_callback: Optional progress callback (step_name, percentage).

        Returns:
            AgentReviewResult with output paths and metrics.

        Raises:
            FileNotFoundError: If video file doesn't exist.
            RuntimeError: If FFmpeg is not available.
        """
        start_time = time.time()
        transcription_time = 0.0
        screenshot_time = 0.0
        formatting_time = 0.0

        # Validate FFmpeg is available
        if not self._video_processor.ffmpeg_available:
            raise RuntimeError("FFmpeg is required for agent-review mode")

        # Validate video file
        self._video_processor.validate_video_file(video_path)

        # Get video metadata
        if progress_callback:
            progress_callback("Extracting video metadata...", 0.0)

        video_metadata = self._video_processor.get_video_metadata(video_path)
        duration = video_metadata.duration

        # Create output directory structure
        # output_path is like /path/to/review.md -> we want /path/to/review/
        output_base = output_path.with_suffix('')  # Remove .md if present
        images_dir = output_base / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Transcribe audio (0-50%)
        if progress_callback:
            progress_callback("Transcribing audio...", 5.0)

        segments, audio_duration = self._transcribe(
            video_path,
            progress_callback=lambda pct: progress_callback(
                "Transcribing...", 5.0 + pct * 0.45
            ) if progress_callback else None
        )
        transcription_time = time.time() - start_time

        # Step 2: Detect screenshot triggers (50-60%)
        if progress_callback:
            progress_callback("Detecting screenshot triggers...", 50.0)

        all_timestamps: list[tuple[float, str, str]] = []  # (timestamp, filename, trigger_type)

        # 2a: Time-based timestamps
        from cesar.ffmpeg_scene_detector import generate_time_based_timestamps
        time_timestamps = generate_time_based_timestamps(duration, screenshots_interval)
        for ts in time_timestamps:
            filename = f"{output_base.stem}_{format_timestamp_for_filename(ts)}.png"
            all_timestamps.append((ts, filename, "time"))

        # 2b: Speech cue timestamps
        if speech_cues:
            detector = SpeechCueDetector(speech_cues)
        else:
            detector = SpeechCueDetector()  # Uses default cues

        cue_matches = detector.detect_cues(segments)
        for match in cue_matches:
            filename = f"{output_base.stem}_{format_timestamp_for_filename(match.timestamp)}.png"
            all_timestamps.append((match.timestamp, filename, "speech_cue"))

        # 2c: Scene change timestamps
        if enable_scene_detection:
            try:
                scene_timestamps = self._scene_detector.detect_scenes(
                    video_path,
                    threshold=scene_threshold
                )
                for ts in scene_timestamps:
                    filename = f"{output_base.stem}_{format_timestamp_for_filename(ts)}.png"
                    all_timestamps.append((ts, filename, "scene_change"))
            except Exception as e:
                logger.warning(f"Scene detection failed, continuing without: {e}")

        # Deduplicate timestamps
        all_timestamps = self._deduplicate_timestamps(all_timestamps)

        # Step 3: Extract screenshots (60-90%)
        if progress_callback:
            progress_callback(f"Extracting {len(all_timestamps)} screenshots...", 60.0)

        screenshot_start = time.time()
        successful_screenshots: list[tuple[float, str]] = []

        for i, (timestamp, filename, trigger_type) in enumerate(all_timestamps):
            output_file = images_dir / Path(filename).name
            try:
                self._video_processor.extract_frame(
                    video_path,
                    timestamp,
                    output_file
                )
                successful_screenshots.append((timestamp, output_file.name))
            except Exception as e:
                logger.warning(f"Failed to extract screenshot at {timestamp}s: {e}")

            # Update progress
            if progress_callback and len(all_timestamps) > 0:
                pct = 60.0 + (i + 1) / len(all_timestamps) * 30.0
                progress_callback(f"Extracting screenshots... ({i + 1}/{len(all_timestamps)})", pct)

        screenshot_time = time.time() - screenshot_start

        # Step 4: Associate screenshots with segments
        if progress_callback:
            progress_callback("Associating screenshots with transcript...", 90.0)

        # Build association data
        associations = []
        trigger_groups = {
            "time": [],
            "speech_cue": [],
            "scene_change": [],
        }

        for timestamp, filename, trigger_type in all_timestamps:
            # Find segments containing this timestamp
            overlapping = []
            for seg in segments:
                # Tolerance of 2 seconds
                if seg.start <= timestamp + 2.0 and seg.end >= timestamp - 2.0:
                    overlapping.append(seg)

            # Find cue word if speech cue
            cue_word = None
            if trigger_type == "speech_cue":
                for match in cue_matches:
                    if abs(match.timestamp - timestamp) < 1.0:
                        cue_word = match.cue_word
                        break

            from cesar.association import ScreenshotAssociation
            associations.append(ScreenshotAssociation(
                timestamp=timestamp,
                filename=filename,
                trigger_type=trigger_type,
                segments=overlapping,
                cue_word=cue_word,
            ))

        # Step 5: Generate outputs (90-100%)
        formatting_start = time.time()

        # Generate sidecar
        if progress_callback:
            progress_callback("Generating sidecar...", 92.0)

        sidecar_gen = SidecarGenerator(
            output_path=output_base,
            source_path=video_path,
            duration=duration,
        )
        sidecar_gen.configure(
            screenshots_interval=screenshots_interval,
            speech_cues_enabled=speech_cues is not None or True,  # Always enabled if cue detector has defaults
            scene_detection_enabled=enable_scene_detection,
        )
        sidecar_path = sidecar_gen.generate(segments, associations)

        # Generate Markdown
        if progress_callback:
            progress_callback("Generating Markdown...", 95.0)

        formatter = AgentReviewMarkdownFormatter(
            source_path=video_path,
            duration=duration,
            output_name=output_base.stem,
            images_dir=images_dir,
        )
        markdown_content = formatter.format(segments, associations)

        # Write Markdown file
        final_output_path = output_base.with_suffix('.md')
        with open(final_output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        formatting_time = time.time() - formatting_start
        total_time = time.time() - start_time

        # Count unique speakers
        speakers = set()
        for seg in segments:
            if seg.speaker:
                speakers.add(seg.speaker)

        if progress_callback:
            progress_callback("Complete", 100.0)

        return AgentReviewResult(
            output_path=final_output_path,
            sidecar_path=sidecar_path,
            images_dir=images_dir,
            screenshots_count=len(successful_screenshots),
            segments_count=len(segments),
            speakers_detected=len(speakers),
            audio_duration=duration,
            processing_time=total_time,
            transcription_time=transcription_time,
            screenshot_time=screenshot_time,
            formatting_time=formatting_time,
        )

    def _transcribe(
        self,
        video_path: Path,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> tuple[list[TranscriptionSegment], float]:
        """Transcribe audio from video.

        Args:
            video_path: Path to video file.
            progress_callback: Optional progress callback (percentage 0-100).

        Returns:
            Tuple of (segments, duration).
        """
        # First try WhisperXPipeline with diarization if available
        if self.pipeline is not None:
            try:
                segments, speakers, duration = self.pipeline.transcribe_and_diarize(
                    str(video_path),
                    progress_callback=progress_callback,
                )
                # Convert WhisperXSegments to TranscriptionSegments
                transcription_segments = []
                for i, seg in enumerate(segments, start=1):
                    transcription_segments.append(TranscriptionSegment(
                        start=seg.start,
                        end=seg.end,
                        text=seg.text,
                        speaker=seg.speaker,
                        segment_id=f"seg_{i:03d}",
                    ))
                return transcription_segments, duration
            except Exception as e:
                logger.warning(f"Pipeline transcription failed: {e}. Falling back.")

        # Fallback to plain transcription
        if self.transcriber is not None:
            segments, metadata = self.transcriber.transcribe_to_segments(
                str(video_path),
                progress_callback=progress_callback,
            )
            return segments, metadata['audio_duration']

        raise ValueError("No transcription method available")

    def _deduplicate_timestamps(
        self,
        timestamps: list[tuple[float, str, str]],
        tolerance: float = 1.0,
    ) -> list[tuple[float, str, str]]:
        """Deduplicate timestamps within tolerance.

        Args:
            timestamps: List of (timestamp, filename, trigger_type) tuples.
            tolerance: Seconds within which timestamps are considered duplicates.

        Returns:
            Deduplicated list, preserving first occurrence.
        """
        if not timestamps:
            return []

        # Sort by timestamp
        sorted_ts = sorted(timestamps, key=lambda x: x[0])
        result = [sorted_ts[0]]

        for current in sorted_ts[1:]:
            last = result[-1]
            if current[0] - last[0] >= tolerance:
                result.append(current)

        return result
