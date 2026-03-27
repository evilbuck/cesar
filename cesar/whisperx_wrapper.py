"""
WhisperX pipeline wrapper for unified transcribe-align-diarize workflow.

Encapsulates WhisperX's three-step pipeline (transcribe -> align -> diarize)
behind a clean interface compatible with Cesar's existing formatting system.
All processing is offline after initial model download from HuggingFace.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, List

from cesar.diarization import DiarizationError, AuthenticationError


@dataclass
class WhisperXSegment:
    """Output segment from WhisperX pipeline.

    Compatible with AlignedSegment from timestamp_aligner.py for
    use with existing MarkdownTranscriptFormatter.

    Attributes:
        start: Start time in seconds
        end: End time in seconds
        speaker: Speaker label (SPEAKER_00, SPEAKER_01, etc.)
        text: Transcribed text for this segment
    """
    start: float
    end: float
    speaker: str
    text: str


class WhisperXPipeline:
    """Wrapper for WhisperX unified pipeline.

    Encapsulates transcription, wav2vec2 alignment, and speaker diarization
    in a single pipeline call. Uses lazy model loading for efficiency.

    Models are downloaded from HuggingFace on first use and cached locally
    for offline operation. Diarization requires a HuggingFace token with
    accepted model agreements.

    Example:
        pipeline = WhisperXPipeline(hf_token="hf_xxx")
        segments, speaker_count, duration = pipeline.transcribe_and_diarize(
            "audio.mp3",
            min_speakers=2,
            max_speakers=4
        )
    """

    DEFAULT_MODEL = "large-v2"
    DEFAULT_BATCH_SIZE = 16
    DEFAULT_MIN_SPEAKERS = 1
    DEFAULT_MAX_SPEAKERS = 5

    def __init__(
        self,
        model_name: str = None,
        device: str = "auto",
        compute_type: str = "auto",
        hf_token: Optional[str] = None,
        batch_size: int = None
    ):
        """Initialize WhisperX pipeline.

        Args:
            model_name: Whisper model size (tiny/base/small/medium/large-v2).
                       Defaults to large-v2.
            device: Compute device. "auto" detects GPU availability.
                   Options: auto, cpu, cuda
            compute_type: Compute precision. "auto" selects based on device.
                         Options: auto, float32, float16, int8
            hf_token: HuggingFace token for diarization models. If None, tries:
                     1. HF_TOKEN environment variable
                     2. Cached token from ~/.cache/huggingface/token
            batch_size: Batch size for transcription. Defaults to 16.
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self.hf_token = self._resolve_token(hf_token)

        # Resolve device and compute type
        self.device = self._resolve_device(device)
        self.compute_type = self._resolve_compute_type(compute_type, self.device)

        # Lazy-loaded models (initialized on first use)
        self._whisper_model = None
        self._align_model = None
        self._align_metadata = None
        self._diarize_model = None
        self._current_language = None  # Track language for alignment model caching

    def _resolve_token(self, provided_token: Optional[str]) -> Optional[str]:
        """Resolve HF token from provided value, env, or cache.

        Token resolution hierarchy:
        1. Explicitly provided token
        2. HF_TOKEN environment variable
        3. Cached token from ~/.cache/huggingface/token

        Args:
            provided_token: Token provided by caller

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

    def _resolve_device(self, device: str) -> str:
        """Resolve device from auto to specific device.

        Args:
            device: Device specification (auto/cpu/cuda)

        Returns:
            Resolved device string (cpu or cuda)
        """
        if device != "auto":
            return device

        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass

        return "cpu"

    def _resolve_compute_type(self, compute_type: str, device: str) -> str:
        """Resolve compute type based on device.

        Args:
            compute_type: Compute type specification (auto/float32/float16/int8)
            device: Resolved device (cpu or cuda)

        Returns:
            Resolved compute type string
        """
        if compute_type != "auto":
            return compute_type

        # Use float16 for GPU, int8 for CPU
        return "float16" if device == "cuda" else "int8"

    def _load_whisper_model(self):
        """Lazy load WhisperX transcription model.

        Raises:
            DiarizationError: If whisperx not installed
        """
        if self._whisper_model is not None:
            return

        try:
            import whisperx
        except ImportError:
            raise DiarizationError(
                "whisperx not installed. Run: pip install whisperx"
            )

        self._whisper_model = whisperx.load_model(
            self.model_name,
            self.device,
            compute_type=self.compute_type
        )

    def _load_align_model(self, language: str):
        """Lazy load alignment model for detected language.

        Args:
            language: Language code from transcription (e.g., 'en', 'fr')

        Note:
            Alignment model is cached per language. If language changes,
            a new model is loaded.
        """
        if self._align_model is not None and self._current_language == language:
            return

        import whisperx

        self._align_model, self._align_metadata = whisperx.load_align_model(
            language_code=language,
            device=self.device
        )
        self._current_language = language

    def _load_diarize_model(self):
        """Lazy load diarization pipeline.

        Raises:
            AuthenticationError: If HuggingFace auth fails (401/403)
            DiarizationError: For other loading failures
        """
        if self._diarize_model is not None:
            return

        import whisperx

        try:
            self._diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=self.hf_token,
                device=self.device
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

    def transcribe_and_diarize(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> tuple[List[WhisperXSegment], int, float]:
        """Run full pipeline: transcribe, align, diarize.

        Executes the complete WhisperX pipeline:
        1. Load audio
        2. Transcribe with Whisper (batched)
        3. Align with wav2vec2 for word-level timestamps
        4. Diarize with pyannote for speaker detection
        5. Assign speakers to words/segments

        Args:
            audio_path: Path to audio file (mp3, wav, m4a, etc.)
            min_speakers: Minimum expected speakers. Defaults to 1.
            max_speakers: Maximum expected speakers. Defaults to 5.
            progress_callback: Called with (phase_name, percentage).
                             Phases: Loading, Transcribing, Aligning,
                             Detecting speakers, Assigning speakers

        Returns:
            Tuple of:
            - segments: List of WhisperXSegment with speaker labels
            - speaker_count: Number of unique speakers detected
            - audio_duration: Total audio duration in seconds

        Raises:
            DiarizationError: If pipeline fails
            AuthenticationError: If HuggingFace auth fails
        """
        import whisperx

        # Apply defaults
        min_spk = min_speakers if min_speakers is not None else self.DEFAULT_MIN_SPEAKERS
        max_spk = max_speakers if max_speakers is not None else self.DEFAULT_MAX_SPEAKERS

        # Step 1: Load audio (0%)
        if progress_callback:
            progress_callback("Loading audio...", 0.0)
        audio = whisperx.load_audio(audio_path)

        # Step 2: Transcribe (0-40%)
        if progress_callback:
            progress_callback("Transcribing...", 5.0)
        self._load_whisper_model()
        result = self._whisper_model.transcribe(audio, batch_size=self.batch_size)
        language = result["language"]

        # Step 3: Align for word-level timestamps (40-60%)
        if progress_callback:
            progress_callback("Aligning timestamps...", 40.0)
        self._load_align_model(language)
        result = whisperx.align(
            result["segments"],
            self._align_model,
            self._align_metadata,
            audio,
            self.device,
            return_char_alignments=False
        )

        # Step 4: Diarize (60-90%)
        if progress_callback:
            progress_callback("Detecting speakers...", 60.0)
        self._load_diarize_model()
        diarize_segments = self._diarize_model(
            audio,
            min_speakers=min_spk,
            max_speakers=max_spk
        )

        # Step 5: Assign speakers to segments (90-100%)
        if progress_callback:
            progress_callback("Assigning speakers...", 90.0)
        result = whisperx.assign_word_speakers(diarize_segments, result)

        # Convert to WhisperXSegment format and return
        if progress_callback:
            progress_callback("Complete", 100.0)

        return self._convert_to_segments(result, audio)

    def _convert_to_segments(
        self,
        result: dict,
        audio
    ) -> tuple[List[WhisperXSegment], int, float]:
        """Convert WhisperX output to WhisperXSegment format.

        Args:
            result: WhisperX result dict with segments
            audio: Loaded audio array for duration calculation

        Returns:
            Tuple of (segments, speaker_count, audio_duration)
        """
        import whisperx

        segments = []
        speakers_seen = set()

        for segment in result.get("segments", []):
            speaker = segment.get("speaker", "UNKNOWN")
            speakers_seen.add(speaker)

            segments.append(WhisperXSegment(
                start=segment["start"],
                end=segment["end"],
                speaker=speaker,
                text=segment.get("text", "").strip()
            ))

        # Calculate duration from audio array length
        # whisperx.load_audio returns numpy array at 16kHz sample rate
        sample_rate = 16000
        audio_duration = len(audio) / sample_rate

        return segments, len(speakers_seen), audio_duration
