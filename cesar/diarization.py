"""
Speaker diarization module for Cesar transcription tool.

Provides speaker detection and segmentation using pyannote.audio pipeline.
All processing is offline after initial model download from HuggingFace.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable


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


class SpeakerDiarizer:
    """Speaker diarization using pyannote.audio pipeline.

    Handles speaker detection with automatic GPU optimization and progress
    feedback. Models are downloaded from HuggingFace on first use and cached
    locally for offline operation.
    """

    DEFAULT_MODEL = "pyannote/speaker-diarization-3.1"
    DEFAULT_MIN_SPEAKERS = 1
    DEFAULT_MAX_SPEAKERS = 5

    def __init__(self, hf_token: Optional[str] = None, model_name: Optional[str] = None):
        """Initialize diarization pipeline.

        Args:
            hf_token: HuggingFace token. If None, tries:
                     1. HF_TOKEN environment variable
                     2. Cached token from ~/.cache/huggingface/token
            model_name: Pyannote model name. Defaults to speaker-diarization-3.1
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.hf_token = self._resolve_token(hf_token)
        self.pipeline = None

    def _resolve_token(self, provided_token: Optional[str]) -> Optional[str]:
        """Resolve HF token from config, env, or cache.

        Args:
            provided_token: Token provided by user

        Returns:
            Resolved token or None
        """
        if provided_token:
            return provided_token

        # Try environment variable
        env_token = os.getenv('HF_TOKEN')
        if env_token:
            return env_token

        # Try cached token
        token_path = Path.home() / '.cache' / 'huggingface' / 'token'
        if token_path.exists():
            return token_path.read_text().strip()

        return None

    def _load_pipeline(self) -> None:
        """Load pyannote pipeline with GPU optimization.

        Raises:
            DiarizationError: If pyannote.audio not installed
            AuthenticationError: If HuggingFace authentication fails
        """
        if self.pipeline is not None:
            return

        try:
            from pyannote.audio import Pipeline
        except ImportError:
            raise DiarizationError(
                "pyannote.audio not installed. Run: pip install pyannote.audio"
            )

        try:
            self.pipeline = Pipeline.from_pretrained(
                self.model_name,
                use_auth_token=self.hf_token
            )
        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "Unauthorized" in error_str or "access" in error_str.lower():
                raise AuthenticationError(
                    "HuggingFace authentication failed.\n"
                    "1. Get token at: https://hf.co/settings/tokens\n"
                    "2. Accept conditions at: https://hf.co/pyannote/speaker-diarization-3.1\n"
                    "3. Accept conditions at: https://hf.co/pyannote/segmentation-3.0\n"
                    "4. Set hf_token in config or HF_TOKEN environment variable"
                ) from e
            raise DiarizationError(f"Failed to load diarization model: {e}") from e

        # Move to GPU if available
        import torch
        if torch.cuda.is_available():
            self.pipeline.to(torch.device("cuda"))

    def diarize(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> DiarizationResult:
        """Run speaker diarization on audio file.

        Args:
            audio_path: Path to audio file
            min_speakers: Minimum expected speakers (default: 1)
            max_speakers: Maximum expected speakers (default: 5)
            progress_callback: Optional callback for progress updates

        Returns:
            DiarizationResult with speaker segments

        Raises:
            DiarizationError: If diarization fails
            AuthenticationError: If authentication fails
        """
        self._load_pipeline()

        # Apply defaults
        min_spk = min_speakers if min_speakers is not None else self.DEFAULT_MIN_SPEAKERS
        max_spk = max_speakers if max_speakers is not None else self.DEFAULT_MAX_SPEAKERS

        # Build kwargs for pipeline
        kwargs = {
            'min_speakers': min_spk,
            'max_speakers': max_spk,
        }

        # Run diarization with optional progress hook
        if progress_callback:
            from pyannote.audio.pipelines.utils.hook import ProgressHook
            with ProgressHook() as hook:
                progress_callback("Detecting speakers...")
                diarization = self.pipeline(audio_path, hook=hook, **kwargs)
        else:
            diarization = self.pipeline(audio_path, **kwargs)

        # Convert to DiarizationResult
        segments = []
        speakers_seen = set()
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append(SpeakerSegment(
                start=turn.start,
                end=turn.end,
                speaker=speaker
            ))
            speakers_seen.add(speaker)

        # Get audio duration from last segment end (approximate)
        audio_duration = segments[-1].end if segments else 0.0

        return DiarizationResult(
            segments=segments,
            speaker_count=len(speakers_seen),
            audio_duration=audio_duration
        )
