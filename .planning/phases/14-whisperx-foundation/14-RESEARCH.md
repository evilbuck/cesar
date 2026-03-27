# Phase 14: WhisperX Foundation - Research

**Researched:** 2026-02-01
**Domain:** WhisperX speech recognition with word-level timestamps and speaker diarization
**Confidence:** HIGH

## Summary

WhisperX is a unified speech recognition pipeline that combines Whisper-based transcription, wav2vec2 forced alignment for word-level timestamps, and pyannote-based speaker diarization. The library (v3.7.6) is well-maintained and provides a cleaner architecture than the current separate-component approach used in Cesar.

The key advantage of WhisperX is that it handles the complexity of aligning transcription segments with speaker segments internally, producing word-level timestamps with speaker labels. This eliminates the need for Cesar's custom `timestamp_aligner.py` module.

WhisperX uses the same underlying technologies as Cesar's current implementation (faster-whisper for transcription, pyannote for diarization) but orchestrates them more efficiently with better alignment through wav2vec2.

**Primary recommendation:** Replace pyannote.audio and timestamp_aligner.py with WhisperX wrapper that exposes the same interfaces (DiarizationError, AuthenticationError, AlignedSegment) while leveraging WhisperX's unified pipeline internally.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| whisperx | >=3.7.6 | Unified ASR+alignment+diarization pipeline | Official INTERSPEECH 2023 implementation |
| torch | ~=2.8.0 | Deep learning framework | Required by WhisperX |
| torchaudio | ~=2.8.0 | Audio processing for PyTorch | Required for alignment models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyannote-audio | >=3.3.2,<4.0.0 | Speaker diarization backend | Bundled with WhisperX |
| faster-whisper | >=1.1.1 | CTranslate2 Whisper inference | Bundled with WhisperX |
| ctranslate2 | >=4.5.0 | Efficient transformer inference | Bundled with WhisperX |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| WhisperX | whisper-timestamped | WhisperX has better diarization integration |
| WhisperX | pyannote-whisper | WhisperX is more actively maintained |
| wav2vec2 alignment | Whisper native timestamps | wav2vec2 provides ~10x more accurate word boundaries |

**Installation:**
```bash
pip install whisperx>=3.7.6
```

**Note:** WhisperX transitively installs pyannote-audio, faster-whisper, and torch. The current Cesar dependencies should be replaced, not supplemented.

## Architecture Patterns

### Recommended Project Structure
```
cesar/
├── whisperx_wrapper.py     # NEW: Wrapper module for WhisperX pipeline
├── diarization.py          # MODIFIED: Keep exceptions, delegate to wrapper
├── orchestrator.py         # MODIFIED: Use wrapper instead of separate components
├── timestamp_aligner.py    # DELETED: WhisperX handles alignment internally
└── transcript_formatter.py # UNCHANGED: Still formats AlignedSegment output
```

### Pattern 1: WhisperX Pipeline Wrapper
**What:** Encapsulate WhisperX's three-step pipeline (transcribe -> align -> diarize) behind a clean interface
**When to use:** Always - this is the recommended approach for Cesar integration
**Example:**
```python
# Source: WhisperX README + PyPI documentation
import whisperx
from dataclasses import dataclass
from typing import Optional, Callable, List

@dataclass
class AlignedSegment:
    """Output segment compatible with Cesar's transcript_formatter."""
    start: float
    end: float
    speaker: str
    text: str

class WhisperXPipeline:
    """Wrapper for WhisperX unified pipeline."""

    def __init__(
        self,
        model_name: str = "large-v2",
        device: str = "cuda",
        compute_type: str = "float16",
        hf_token: Optional[str] = None,
        batch_size: int = 16
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.hf_token = hf_token
        self.batch_size = batch_size

        # Lazy-loaded models
        self._whisper_model = None
        self._align_model = None
        self._align_metadata = None
        self._diarize_model = None

    def transcribe_and_diarize(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> tuple[List[AlignedSegment], int]:
        """Run full pipeline: transcribe, align, diarize.

        Returns:
            Tuple of (aligned_segments, speaker_count)
        """
        # Step 1: Load audio
        audio = whisperx.load_audio(audio_path)

        # Step 2: Transcribe
        if progress_callback:
            progress_callback("Transcribing...")
        if self._whisper_model is None:
            self._whisper_model = whisperx.load_model(
                self.model_name,
                self.device,
                compute_type=self.compute_type
            )
        result = self._whisper_model.transcribe(audio, batch_size=self.batch_size)
        language = result["language"]

        # Step 3: Align for word-level timestamps
        if progress_callback:
            progress_callback("Aligning timestamps...")
        if self._align_model is None:
            self._align_model, self._align_metadata = whisperx.load_align_model(
                language_code=language,
                device=self.device
            )
        result = whisperx.align(
            result["segments"],
            self._align_model,
            self._align_metadata,
            audio,
            self.device,
            return_char_alignments=False
        )

        # Step 4: Diarize
        if progress_callback:
            progress_callback("Detecting speakers...")
        if self._diarize_model is None:
            self._diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=self.hf_token,
                device=self.device
            )
        diarize_segments = self._diarize_model(
            audio,
            min_speakers=min_speakers,
            max_speakers=max_speakers
        )

        # Step 5: Assign speakers to words
        result = whisperx.assign_word_speakers(diarize_segments, result)

        # Convert to Cesar's AlignedSegment format
        return self._convert_to_aligned_segments(result)

    def _convert_to_aligned_segments(self, result: dict) -> tuple[List[AlignedSegment], int]:
        """Convert WhisperX output to Cesar's AlignedSegment format."""
        segments = []
        speakers_seen = set()

        for segment in result["segments"]:
            speaker = segment.get("speaker", "UNKNOWN")
            speakers_seen.add(speaker)

            segments.append(AlignedSegment(
                start=segment["start"],
                end=segment["end"],
                speaker=speaker,
                text=segment["text"]
            ))

        return segments, len(speakers_seen)
```

### Pattern 2: Exception Preservation
**What:** Maintain existing exception hierarchy for backward compatibility
**When to use:** Always - Cesar's CLI and API depend on these exceptions
**Example:**
```python
# Keep in diarization.py
class DiarizationError(Exception):
    """Base exception for diarization errors."""
    pass

class AuthenticationError(DiarizationError):
    """HuggingFace authentication failed."""
    pass

# In wrapper, catch and re-raise with Cesar's exceptions
def _load_diarize_model(self):
    try:
        self._diarize_model = whisperx.DiarizationPipeline(
            use_auth_token=self.hf_token,
            device=self.device
        )
    except Exception as e:
        error_str = str(e)
        if "401" in error_str or "Unauthorized" in error_str:
            raise AuthenticationError(
                "HuggingFace authentication failed.\n"
                "1. Get token at: https://hf.co/settings/tokens\n"
                "2. Accept conditions at: https://hf.co/pyannote/speaker-diarization-3.1\n"
                "3. Accept conditions at: https://hf.co/pyannote/segmentation-3.0\n"
                "4. Set hf_token in config or HF_TOKEN environment variable"
            ) from e
        raise DiarizationError(f"Failed to load diarization model: {e}") from e
```

### Anti-Patterns to Avoid
- **Running transcription separately:** Don't use Cesar's existing AudioTranscriber alongside WhisperX - use WhisperX's built-in transcription for consistent segment alignment
- **Manual timestamp alignment:** Don't try to align WhisperX segments manually - the library handles this internally
- **Mixing pyannote versions:** WhisperX bundles its own pyannote version - don't import pyannote.audio directly

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Word-level timestamps | Custom forced alignment | `whisperx.align()` | Complex phoneme model selection per language |
| Speaker-to-word assignment | Temporal intersection | `whisperx.assign_word_speakers()` | Handles edge cases, overlapping speech |
| VAD preprocessing | Custom silence detection | WhisperX built-in VAD | Reduces hallucination, integrated |
| Language detection | Manual language code | WhisperX auto-detect | Returns `result["language"]` |

**Key insight:** WhisperX's value is in the orchestration and alignment - these are research-validated approaches from INTERSPEECH 2023 that handle edge cases Cesar's current implementation may miss.

## Common Pitfalls

### Pitfall 1: Dependency Version Conflicts
**What goes wrong:** torch, torchaudio, ctranslate2, and pyannote have complex version interdependencies
**Why it happens:** WhisperX pins specific versions that may conflict with existing installations
**How to avoid:**
- Remove `pyannote.audio>=3.1.0` from Cesar's pyproject.toml
- Let WhisperX manage its own dependencies
- Test in clean virtual environment
**Warning signs:** Import errors, CUDA/cuDNN version mismatches

### Pitfall 2: Memory Exhaustion on Alignment
**What goes wrong:** wav2vec2 alignment models can consume significant GPU memory
**Why it happens:** Large alignment models (~1.2GB for WAV2VEC2_ASR_LARGE_LV60K_960H)
**How to avoid:**
- Use smaller batch_size (4 instead of 16)
- Use "int8" compute_type for low-memory GPUs
- Consider CPU fallback for alignment
**Warning signs:** CUDA OOM errors during align step

### Pitfall 3: Missing HuggingFace Agreements
**What goes wrong:** DiarizationPipeline fails with 403/401 errors
**Why it happens:** pyannote models require accepting user agreements on HuggingFace
**How to avoid:**
- Document required agreements in error messages (already in Cesar)
- Verify token has read permissions
- User must accept agreements at:
  - https://hf.co/pyannote/speaker-diarization-3.1
  - https://hf.co/pyannote/segmentation-3.0
**Warning signs:** HTTP 401/403 errors, "access" in error messages

### Pitfall 4: Language-Specific Alignment Models
**What goes wrong:** Alignment fails or produces poor results for non-English audio
**Why it happens:** Default alignment models support limited languages (en, fr, de, es, it via torchaudio)
**How to avoid:**
- WhisperX auto-selects alignment model based on detected language
- For unsupported languages, alignment is skipped (uses Whisper timestamps)
- Document this limitation for users
**Warning signs:** Alignment warnings in logs, coarser timestamps

### Pitfall 5: Words Without Dictionary Characters
**What goes wrong:** Numbers, symbols, and special characters don't get word-level timestamps
**Why it happens:** wav2vec2 phoneme models only recognize alphabetic characters
**How to avoid:**
- Accept this limitation (documented in WhisperX)
- Fall back to segment-level timestamps for affected words
**Warning signs:** Words with `null` start/end times in output

## Code Examples

Verified patterns from official sources:

### Complete Pipeline Example
```python
# Source: WhisperX README (https://github.com/m-bain/whisperX)
import whisperx
import gc

device = "cuda"
audio_file = "audio.mp3"
batch_size = 16
compute_type = "float16"

# 1. Transcribe with original whisper (batched)
model = whisperx.load_model("large-v2", device, compute_type=compute_type)
audio = whisperx.load_audio(audio_file)
result = model.transcribe(audio, batch_size=batch_size)
print(result["segments"])  # before alignment

# 2. Align whisper output
model_a, metadata = whisperx.load_align_model(
    language_code=result["language"],
    device=device
)
result = whisperx.align(
    result["segments"],
    model_a,
    metadata,
    audio,
    device,
    return_char_alignments=False
)
print(result["segments"])  # after alignment (with word-level timestamps)

# 3. Assign speaker labels
diarize_model = whisperx.DiarizationPipeline(use_auth_token=YOUR_HF_TOKEN, device=device)
diarize_segments = diarize_model(audio)
# diarize_model(audio, min_speakers=2, max_speakers=4)  # optional speaker hints

result = whisperx.assign_word_speakers(diarize_segments, result)
print(result["segments"])  # segments now include speaker labels
```

### Output Data Structure
```python
# Source: WhisperX documentation
# After transcription (before alignment):
{
    "segments": [
        {"text": "Hello world", "start": 0.0, "end": 2.5},
        ...
    ],
    "language": "en"
}

# After alignment:
{
    "segments": [
        {
            "text": "Hello world",
            "start": 0.0,
            "end": 2.5,
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.8, "score": 0.95},
                {"word": "world", "start": 1.0, "end": 2.5, "score": 0.92}
            ]
        }
    ],
    "word_segments": [...]  # flattened word list
}

# After speaker assignment:
{
    "segments": [
        {
            "text": "Hello world",
            "start": 0.0,
            "end": 2.5,
            "speaker": "SPEAKER_00",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.8, "speaker": "SPEAKER_00"},
                {"word": "world", "start": 1.0, "end": 2.5, "speaker": "SPEAKER_00"}
            ]
        }
    ]
}
```

### CPU Fallback Pattern
```python
# Source: WhisperX README
# For CPU-only processing (or Mac OS X):
model = whisperx.load_model("large-v2", "cpu", compute_type="int8")
```

### DiarizationPipeline Initialization
```python
# Source: whisperx/diarize.py (GitHub)
from whisperx.diarize import DiarizationPipeline

diarize_model = DiarizationPipeline(
    model_name="pyannote/speaker-diarization-3.1",  # default
    use_auth_token="YOUR_HF_TOKEN",
    device="cuda"  # or "cpu"
)

# Returns pandas DataFrame with columns: segment, label, speaker, start, end
diarize_segments = diarize_model(
    audio,
    num_speakers=None,      # auto-detect
    min_speakers=None,      # optional hint
    max_speakers=None       # optional hint
)
```

## State of the Art

| Old Approach (Cesar v2.2) | Current Approach (WhisperX) | When Changed | Impact |
|---------------------------|------------------------------|--------------|--------|
| Separate faster-whisper + pyannote | Unified WhisperX pipeline | 2023 | Simpler architecture |
| Custom timestamp alignment | wav2vec2 forced alignment | 2023 | ~10x timestamp accuracy |
| Segment-level speaker labels | Word-level speaker labels | 2023 | Finer granularity |
| Manual pyannote integration | Built-in diarization | 2023 | Fewer dependency conflicts |

**Deprecated/outdated:**
- Manual `timestamp_aligner.py`: WhisperX handles this internally with wav2vec2
- Direct `pyannote.audio.Pipeline` usage: WhisperX wraps this with better defaults

## Open Questions

Things that couldn't be fully resolved:

1. **Exact dependency resolution with existing Cesar packages**
   - What we know: WhisperX bundles pyannote, torch will be upgraded
   - What's unclear: Whether faster-whisper coexistence causes issues
   - Recommendation: Create clean venv, install whisperx only, verify imports

2. **Performance comparison: Cesar current vs WhisperX**
   - What we know: WhisperX claims 70x realtime with large-v2
   - What's unclear: How this compares to Cesar's current faster-whisper implementation
   - Recommendation: Benchmark both approaches during Phase 14 implementation

3. **Handling existing AudioTranscriber integration**
   - What we know: WhisperX has its own transcription step
   - What's unclear: Whether to keep AudioTranscriber for non-diarized transcription
   - Recommendation: Consider WhisperX for all transcription (consistency)

## Sources

### Primary (HIGH confidence)
- [WhisperX GitHub README](https://github.com/m-bain/whisperX) - Official documentation, API examples
- [WhisperX PyPI](https://pypi.org/project/whisperx/) - Version 3.7.6, dependency constraints
- [whisperx/diarize.py](https://github.com/m-bain/whisperX/blob/main/whisperx/diarize.py) - DiarizationPipeline implementation
- [whisperx/asr.py](https://github.com/m-bain/whisperX/blob/main/whisperx/asr.py) - load_model, transcribe implementation
- [whisperx/alignment.py](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py) - wav2vec2 alignment

### Secondary (MEDIUM confidence)
- [WhisperX pyproject.toml](https://github.com/m-bain/whisperX/blob/main/pyproject.toml) - Exact dependency versions
- [DeepWiki WhisperX Installation](https://deepwiki.com/m-bain/whisperX/2-installation-and-setup) - Installation guidance
- [GoTranscript WhisperX Tutorial](https://gotranscript.com/public/master-word-level-timestamping-with-whisperx-a-comprehensive-tutorial) - Usage patterns

### Tertiary (LOW confidence)
- [GitHub Issues on dependency conflicts](https://github.com/m-bain/whisperX/issues/1051) - Known issues, workarounds
- Community blog posts - Real-world usage patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official documentation, PyPI verified
- Architecture: HIGH - Based on official API, code review
- Pitfalls: MEDIUM - Community issues + official limitations docs

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (30 days - stable library, active development)
