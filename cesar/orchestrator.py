"""
Orchestrator for coordinating transcription and formatting pipeline.

Provides a single entry point that runs the WhisperX unified pipeline for
transcription with speaker diarization, with graceful fallback to plain
transcription using AudioTranscriber when diarization fails.
"""
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Any

from cesar.transcriber import AudioTranscriber
from cesar.diarization import DiarizationError, AuthenticationError
from cesar.whisperx_wrapper import WhisperXPipeline, WhisperXSegment
from cesar.transcript_formatter import MarkdownTranscriptFormatter

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
