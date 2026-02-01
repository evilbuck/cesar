"""
Orchestrator for coordinating transcription, diarization, and formatting pipeline.

Provides a single entry point that runs transcription, speaker diarization,
and transcript formatting in sequence with unified progress reporting and
graceful fallback handling.
"""
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Any

from cesar.transcriber import AudioTranscriber
from cesar.diarization import SpeakerDiarizer, DiarizationError, DiarizationResult
from cesar.timestamp_aligner import align_timestamps, TranscriptionSegment, AlignedSegment
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
    """Orchestrate transcription, diarization, and formatting pipeline.

    Coordinates all components to produce speaker-labeled transcripts with
    graceful fallback to plain text when diarization fails.
    """

    def __init__(
        self,
        transcriber: AudioTranscriber,
        diarizer: Optional[SpeakerDiarizer] = None,
        formatter: Optional[MarkdownTranscriptFormatter] = None
    ):
        """Initialize orchestrator with components.

        Args:
            transcriber: AudioTranscriber instance for transcription
            diarizer: Optional SpeakerDiarizer for speaker detection
            formatter: Optional MarkdownTranscriptFormatter for formatting
                      (created automatically if not provided)
        """
        self.transcriber = transcriber
        self.diarizer = diarizer
        self.formatter = formatter

    def orchestrate(
        self,
        audio_path: Path,
        output_path: Path,
        enable_diarization: bool = True,
        keep_intermediate: bool = False,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> OrchestrationResult:
        """Run full transcription, diarization, and formatting pipeline.

        Args:
            audio_path: Path to input audio file
            output_path: Path to output file (extension may be changed)
            enable_diarization: Whether to run speaker diarization
            keep_intermediate: Whether to save intermediate debug files
            progress_callback: Optional callback for progress updates
                              Called with (step_name, overall_percentage)

        Returns:
            OrchestrationResult with metrics and output path

        Raises:
            Exception: If transcription fails (transcription is required)

        Note:
            Diarization and formatting errors are caught and trigger fallback
            to plain .txt transcript with warning logs.
        """
        # Track timing for each step
        transcription_time = 0.0
        diarization_time = None
        formatting_time = 0.0
        diarization_succeeded = False
        speakers_detected = 0

        # Step 1: Transcribe audio (0-60%)
        if progress_callback:
            progress_callback("Transcribing...", 0.0)

        start = time.time()
        segments, metadata = self.transcriber.transcribe_to_segments(
            str(audio_path),
            progress_callback=lambda pct, count, elapsed: progress_callback(
                "Transcribing...", pct * 0.6 / 100
            ) if progress_callback else None
        )
        transcription_time = time.time() - start
        audio_duration = metadata['audio_duration']

        if progress_callback:
            progress_callback("Transcribing...", 60.0)

        # Save intermediate transcription if requested
        if keep_intermediate:
            intermediate_path = output_path.parent / f"{output_path.stem}_transcription.txt"
            with open(intermediate_path, 'w', encoding='utf-8') as f:
                for seg in segments:
                    f.write(f"{seg.text}\n")
            logger.info(f"Saved intermediate transcription: {intermediate_path}")

        # Step 2: Diarize (60-90%) if enabled
        diarization_result = None
        if enable_diarization and self.diarizer is not None:
            try:
                if progress_callback:
                    progress_callback("Detecting speakers...", 60.0)

                start = time.time()
                diarization_result = self.diarizer.diarize(
                    str(audio_path),
                    progress_callback=lambda msg: progress_callback(
                        "Detecting speakers...", 75.0
                    ) if progress_callback else None
                )
                diarization_time = time.time() - start
                diarization_succeeded = True
                speakers_detected = diarization_result.speaker_count

                if progress_callback:
                    progress_callback("Detecting speakers...", 90.0)

                # Save intermediate diarization if requested
                if keep_intermediate:
                    intermediate_path = output_path.parent / f"{output_path.stem}_diarization.json"
                    import json
                    with open(intermediate_path, 'w', encoding='utf-8') as f:
                        data = {
                            'speaker_count': diarization_result.speaker_count,
                            'audio_duration': diarization_result.audio_duration,
                            'segments': [
                                {
                                    'start': seg.start,
                                    'end': seg.end,
                                    'speaker': seg.speaker
                                }
                                for seg in diarization_result.segments
                            ]
                        }
                        json.dump(data, f, indent=2)
                    logger.info(f"Saved intermediate diarization: {intermediate_path}")

            except DiarizationError as e:
                logger.warning(f"Diarization failed: {e}. Falling back to plain transcript.")
                diarization_succeeded = False
        else:
            if progress_callback:
                progress_callback("Detecting speakers...", 90.0)

        # Step 3: Format and save (90-100%)
        if progress_callback:
            progress_callback("Formatting...", 90.0)

        start = time.time()

        if diarization_succeeded and diarization_result is not None:
            # Format with speaker labels
            try:
                aligned_segments = align_timestamps(segments, diarization_result)

                # Create formatter if not provided
                formatter = self.formatter or MarkdownTranscriptFormatter(
                    speaker_count=diarization_result.speaker_count,
                    duration=audio_duration
                )

                formatted_text = formatter.format(aligned_segments)

                # Ensure output has .md extension
                final_output = output_path.with_suffix('.md')
                if final_output != output_path:
                    logger.info(f"Changed output extension to .md for speaker-labeled transcript")

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
            progress_callback("Formatting...", 100.0)

        return OrchestrationResult(
            output_path=final_output,
            speakers_detected=speakers_detected,
            audio_duration=audio_duration,
            transcription_time=transcription_time,
            diarization_time=diarization_time,
            formatting_time=formatting_time,
            diarization_succeeded=diarization_succeeded
        )

    def _save_plain_transcript(self, segments: list[TranscriptionSegment], output_path: Path) -> Path:
        """Save plain text transcript without speaker labels.

        Args:
            segments: Transcription segments
            output_path: Desired output path

        Returns:
            Actual output path (.txt extension)
        """
        # Ensure output has .txt extension
        final_output = output_path.with_suffix('.txt')
        if final_output != output_path:
            logger.info(f"Changed output extension to .txt for plain transcript")

        with open(final_output, 'w', encoding='utf-8') as f:
            f.write("# Transcript\n\n")
            f.write("(Speaker detection unavailable)\n\n")
            for seg in segments:
                f.write(f"{seg.text}\n")

        logger.info("Saved plain transcript (speaker detection unavailable)")
        return final_output
