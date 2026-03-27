# Phase 10: Speaker Diarization Core - Research

**Researched:** 2026-02-01
**Domain:** Speaker diarization using pyannote.audio with offline capability and timestamp alignment
**Confidence:** HIGH

## Summary

Speaker diarization identifies "who spoke when" in audio by detecting speaker changes and assigning anonymous labels. The pyannote.audio library is the de facto standard for open-source speaker diarization, with version 3.1 offering the best balance of maturity and ease of use, while the newer community-1 (v4.0) provides improved accuracy and exclusive speaker diarization mode that simplifies alignment with transcription timestamps.

The core challenges are: (1) offline model download and authentication with HuggingFace tokens, (2) aligning fine-grained diarization timestamps with coarser Whisper transcription timestamps, and (3) providing meaningful progress feedback during potentially lengthy processing. The standard approach uses temporal intersection to match segments, with strategies to handle overlapping speech and timestamp misalignment.

**Primary recommendation:** Use pyannote.audio 3.1 or community-1 with HuggingFace token authentication, implement offline model caching, align timestamps via temporal intersection, and integrate with existing Rich progress UI.

## Standard Stack

The established libraries/tools for speaker diarization:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyannote.audio | 4.0.3+ | Speaker diarization pipeline | Industry standard open-source diarization, actively maintained |
| torch | Latest stable | PyTorch backend for models | Required dependency for pyannote neural models |
| huggingface_hub | Latest stable | Model authentication and download | Official HuggingFace integration for model access |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| torchaudio | Latest stable | Audio loading for in-memory processing | When processing from memory instead of files |
| ffmpeg | System package | Audio decoding backend | Required by torchcodec for audio processing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pyannote.audio 3.1 | community-1 (4.0) | community-1 has better accuracy but 3.1 is more mature and stable |
| pyannote.audio | WhisperX | WhisperX integrates transcription+diarization but less control over each step |
| Open-source | pyannoteAI premium (precision-2) | Premium offers better accuracy and speed but requires paid API subscription |

**Installation:**
```bash
pip install pyannote.audio torch
```

Note: ffmpeg must be installed at system level (not Python package)

## Architecture Patterns

### Recommended Module Structure
```
cesar/
├── diarization.py           # Core SpeakerDiarizer class
├── timestamp_aligner.py     # Timestamp alignment utilities
├── transcriber.py           # Existing transcriber (unchanged)
└── config.py               # Config extended with HF token
```

### Pattern 1: Pipeline Initialization with Offline Support
**What:** Load pyannote pipeline with HuggingFace authentication, cache models locally, handle token errors gracefully
**When to use:** Every diarization operation

**Example:**
```python
# Source: https://huggingface.co/pyannote/speaker-diarization-3.1
from pyannote.audio import Pipeline
from pathlib import Path

class SpeakerDiarizer:
    def __init__(self, model_name="pyannote/speaker-diarization-3.1", hf_token=None):
        """Initialize diarization pipeline with offline caching."""
        # Models auto-cache to ~/.cache/huggingface/hub/
        try:
            self.pipeline = Pipeline.from_pretrained(
                model_name,
                use_auth_token=hf_token  # Use token= in newer versions
            )
        except Exception as e:
            if "401" in str(e) or "Unauthorized" in str(e):
                raise AuthenticationError(
                    "HuggingFace authentication failed. "
                    "Visit https://hf.co/settings/tokens to create token, "
                    "accept conditions at https://hf.co/pyannote/speaker-diarization-3.1"
                )
            raise

        # Move to GPU if available
        import torch
        if torch.cuda.is_available():
            self.pipeline.to(torch.device("cuda"))

    def diarize(self, audio_path, num_speakers=None, min_speakers=None, max_speakers=None):
        """Run diarization with speaker count hints."""
        kwargs = {}
        if num_speakers:
            kwargs['num_speakers'] = num_speakers
        else:
            if min_speakers:
                kwargs['min_speakers'] = min_speakers
            if max_speakers:
                kwargs['max_speakers'] = max_speakers

        return self.pipeline(audio_path, **kwargs)
```

### Pattern 2: Progress Monitoring with ProgressHook
**What:** Use pyannote's built-in ProgressHook to track diarization progress, integrate with Rich UI
**When to use:** All diarization operations to provide user feedback

**Example:**
```python
# Source: https://huggingface.co/pyannote/speaker-diarization-community-1
from pyannote.audio.pipelines.utils.hook import ProgressHook
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

def diarize_with_progress(self, audio_path, **kwargs):
    """Run diarization with progress tracking."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("Detecting speakers...", total=None)

        # pyannote's ProgressHook can be used with context manager
        with ProgressHook() as hook:
            diarization = self.pipeline(audio_path, hook=hook, **kwargs)

        progress.update(task, completed=True)

    return diarization
```

### Pattern 3: Timestamp Alignment via Temporal Intersection
**What:** Match Whisper transcription segments to pyannote speaker segments based on maximum time overlap
**When to use:** When combining transcription with diarization results

**Example:**
```python
# Source: https://scalastic.io/en/whisper-pyannote-ultimate-speech-transcription/
def align_timestamps(transcription_segments, diarization):
    """Align transcription segments to speaker labels via temporal intersection."""
    aligned_segments = []

    for segment in transcription_segments:
        start_time = segment['start']
        end_time = segment['end']
        text = segment['text']

        # Find best matching speaker based on time overlap
        best_speaker = None
        max_intersection = 0

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            intersection_start = max(start_time, turn.start)
            intersection_end = min(end_time, turn.end)

            if intersection_start < intersection_end:
                intersection_length = intersection_end - intersection_start
                if intersection_length > max_intersection:
                    max_intersection = intersection_length
                    best_speaker = speaker

        aligned_segments.append({
            'start': start_time,
            'end': end_time,
            'speaker': best_speaker or 'UNKNOWN',
            'text': text
        })

    return aligned_segments
```

### Pattern 4: Handling Single Speaker Detection
**What:** Skip diarization output formatting when only one speaker detected - output looks like normal transcription
**When to use:** When diarization detects only 1 unique speaker

**Example:**
```python
def format_output(aligned_segments):
    """Format output, skipping speaker labels if only one speaker."""
    speakers = set(seg['speaker'] for seg in aligned_segments if seg['speaker'] != 'UNKNOWN')

    if len(speakers) <= 1:
        # Single speaker - format like normal transcription
        return '\n'.join(seg['text'].strip() for seg in aligned_segments)
    else:
        # Multiple speakers - include labels
        return '\n'.join(
            f"[{seg['speaker']}] {seg['text'].strip()}"
            for seg in aligned_segments
        )
```

### Pattern 5: HuggingFace Token Management
**What:** Store and retrieve HuggingFace tokens from config, prompt user if missing, use huggingface_hub.login for persistence
**When to use:** First-time setup and token error recovery

**Example:**
```python
# Source: https://huggingface.co/docs/huggingface_hub/en/quick-start
from huggingface_hub import login
from pathlib import Path

def ensure_hf_token(config_token=None):
    """Ensure HuggingFace token is available, prompt if missing."""
    # Try config first
    if config_token:
        return config_token

    # Try environment variable
    import os
    env_token = os.getenv('HF_TOKEN')
    if env_token:
        return env_token

    # Check if already logged in (token in ~/.cache/huggingface/token)
    token_path = Path.home() / '.cache' / 'huggingface' / 'token'
    if token_path.exists():
        return token_path.read_text().strip()

    # Prompt user for token
    from rich.prompt import Prompt
    token = Prompt.ask(
        "\n[yellow]HuggingFace token required for speaker diarization[/yellow]\n"
        "Visit https://hf.co/settings/tokens to create a token\n"
        "Accept conditions at https://hf.co/pyannote/speaker-diarization-3.1\n"
        "Enter your HuggingFace token"
    )

    # Save for future use
    login(token=token)

    return token
```

### Anti-Patterns to Avoid
- **Using file paths instead of token strings:** pyannote expects token string, not path to file
- **Not accepting user conditions:** Models require accepting conditions on HuggingFace before download works
- **Forcing exact speaker count when auto-detection better:** num_speakers should be used sparingly, min/max range preferred
- **Not handling offline mode:** After first download, pipeline should work without internet
- **Ignoring GPU availability:** Diarization is slow on CPU, should check and use GPU when available
- **Not merging consecutive same-speaker segments:** Creates fragmented output, should merge adjacent segments from same speaker

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Speaker detection algorithm | Custom ML model or heuristics | pyannote.audio Pipeline | Pre-trained on massive datasets, handles edge cases (overlapping speech, noise, multiple speakers) |
| Audio format handling | Manual ffmpeg calls and conversion | pyannote auto-conversion | Automatically handles stereo→mono, sample rate conversion |
| Timestamp alignment | Simple nearest-neighbor matching | Temporal intersection algorithm | Handles segment boundaries, overlapping speech, misaligned timestamps correctly |
| HuggingFace authentication | Manual HTTP requests with tokens | huggingface_hub.login() | Handles token storage, refresh, multiple auth methods |
| Progress tracking | Custom progress implementation | ProgressHook + Rich | Built-in integration, handles pipeline stages automatically |
| Model caching | Custom download and storage | Pipeline.from_pretrained() auto-cache | Standard HF cache location, handles versioning, partial downloads |

**Key insight:** Speaker diarization is a deep learning problem with many edge cases (overlapping speech, background noise, different speaker counts, varying audio quality). Pre-trained models from pyannote significantly outperform any custom approach, and the ecosystem handles authentication, caching, and format conversion automatically.

## Common Pitfalls

### Pitfall 1: Confusing Diarization with Identification
**What goes wrong:** Users expect actual speaker names (e.g., "John", "Sarah") but get anonymous labels (e.g., "SPEAKER_00", "SPEAKER_01")
**Why it happens:** Diarization only answers "who spoke when" with anonymous labels - it doesn't identify who the speakers are by name
**How to avoid:**
- Document clearly that output will be anonymous labels like "[SPEAKER_00]"
- Don't use terms like "speaker recognition" or "speaker identification" in UI/docs
- Consider future phase for speaker identification (voice matching) if needed
**Warning signs:** User asking "how do I tell it who the speakers are"

### Pitfall 2: Authentication Token Errors on First Use
**What goes wrong:** Pipeline fails with 401 Unauthorized or "Repository Not Found" errors
**Why it happens:** Three required steps: (1) accept conditions at pyannote/speaker-diarization-3.1, (2) accept conditions at pyannote/segmentation-3.0, (3) provide valid HuggingFace token
**How to avoid:**
- Implement interactive token prompt with clear instructions including both URLs
- Catch authentication errors specifically and provide helpful error messages
- Use huggingface_hub.login() to persist token for future runs
- Test offline mode after first successful download
**Warning signs:** "401 Client Error", "Repository Not Found", "Unauthorized"

### Pitfall 3: Timestamp Misalignment Between Whisper and Pyannote
**What goes wrong:** Speaker labels don't match the actual speaker in transcription, words attributed to wrong speaker
**Why it happens:** Whisper timestamps are segment-level (often 30s chunks) while pyannote is sub-second precision, plus Whisper can be imprecise
**How to avoid:**
- Use temporal intersection algorithm (maximum overlap) not simple proximity
- Handle edge cases: segments extending beyond ranges, None end timestamps
- Use community-1 model's "exclusive speaker diarization" mode for cleaner alignment
- Merge consecutive segments from same speaker to reduce fragmentation
- Log warnings when alignment confidence is low (small overlap)
**Warning signs:** User reports "the speaker labels are wrong", "it says speaker A but that's speaker B talking"

### Pitfall 4: Slow Processing Without GPU
**What goes wrong:** Diarization takes 10-20x longer than transcription on CPU
**Why it happens:** Pyannote uses deep neural networks that are much faster on GPU, but defaults to CPU
**How to avoid:**
- Check for GPU availability (torch.cuda.is_available()) and use if present
- Document processing time expectations (GPU: near real-time, CPU: 10-20x slower)
- Consider skipping diarization on very long files when CPU-only
- Show estimated time remaining based on audio length
**Warning signs:** User reports "it's been processing for 30 minutes" on 10-minute audio

### Pitfall 5: File Naming Matters for Offline Models
**What goes wrong:** Offline model loading fails with cryptic errors about model type inference
**Why it happens:** When loading models from local directory, pyannote infers model type from file naming conventions - wrong names break inference
**How to avoid:**
- Use pipeline repository cloning (git lfs clone) instead of individual model files
- If downloading individual models, follow exact naming from official repo
- Test offline mode immediately after setup to catch issues early
**Warning signs:** "Could not infer model type", errors when loading from local path

### Pitfall 6: Not Handling Single Speaker Case
**What goes wrong:** Output shows "[SPEAKER_00]" labels for every line when only one person is talking
**Why it happens:** Diarization still runs and assigns labels even when only 1 speaker detected
**How to avoid:**
- Count unique speakers after diarization completes
- If only 1 speaker, skip speaker label formatting (output looks like normal transcription)
- Only show speaker summary if 2+ speakers detected
**Warning signs:** User says "why does it say SPEAKER_00 when I'm the only person talking"

### Pitfall 7: Overlapping Speech Attribution
**What goes wrong:** When multiple speakers talk simultaneously, transcription may be garbled or attributed to wrong speaker
**Why it happens:** Whisper struggles with overlapping speech, pyannote detects both speakers but can't split the transcription
**How to avoid:**
- Use temporal intersection to assign to speaker with most overlap
- Consider marking segments with very short speaker segments as "Multiple speakers"
- Document limitation that overlapping speech may have reduced accuracy
- community-1's exclusive mode helps by assigning to most likely single speaker
**Warning signs:** Transcription quality drops during overlapping speech

## Code Examples

Verified patterns from official sources:

### Basic Diarization Pipeline
```python
# Source: https://huggingface.co/pyannote/speaker-diarization-3.1
from pyannote.audio import Pipeline

# Initialize pipeline (downloads models on first use to ~/.cache/huggingface/)
pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token="YOUR_HF_TOKEN"
)

# Run diarization
diarization = pipeline("audio.wav")

# Iterate results
for turn, _, speaker in diarization.itertracks(yield_label=True):
    print(f"{speaker} speaks between t={turn.start:.3f}s and t={turn.end:.3f}s")
```

### Using Speaker Count Parameters
```python
# Known exact count
diarization = pipeline("audio.wav", num_speakers=2)

# Range (preferred for flexibility)
diarization = pipeline("audio.wav", min_speakers=2, max_speakers=5)
```

### GPU Acceleration
```python
import torch

# Check GPU availability and move pipeline
if torch.cuda.is_available():
    pipeline.to(torch.device("cuda"))
```

### Progress Monitoring
```python
# Source: https://huggingface.co/pyannote/speaker-diarization-community-1
from pyannote.audio.pipelines.utils.hook import ProgressHook

with ProgressHook() as hook:
    diarization = pipeline("audio.wav", hook=hook)
```

### In-Memory Processing
```python
# Source: https://huggingface.co/pyannote/speaker-diarization-3.1
import torchaudio

waveform, sample_rate = torchaudio.load("audio.wav")
diarization = pipeline({"waveform": waveform, "sample_rate": sample_rate})
```

### HuggingFace Token Persistence
```python
# Source: https://huggingface.co/docs/huggingface_hub/en/quick-start
from huggingface_hub import login

# Save token for future use (stores in ~/.cache/huggingface/token)
login(token="your_token_here")

# Later, pipeline can access without explicit token
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")
```

### Offline Model Cloning
```bash
# Source: https://github.com/pyannote/pyannote-audio/blob/develop/tutorials/community/offline_usage_speaker_diarization.ipynb
# Requires git-lfs
git lfs install
git clone https://hf.co/pyannote/speaker-diarization-3.1 /path/to/local/dir
```

```python
# Load from local directory
pipeline = Pipeline.from_pretrained('/path/to/local/dir')
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pyannote.audio 2.x | pyannote.audio 3.1 | 2023 | Simpler API, better accuracy, unified pipeline |
| Individual model loading | Pipeline.from_pretrained() | 3.0+ | Auto-downloads dependencies, handles versioning |
| Manual token in code | huggingface_hub.login() | 2023+ | Token persisted, no hardcoding needed |
| Separate diarization+transcription | WhisperX integration | 2024 | Tighter integration but less control |
| Legacy speaker-diarization-2.1 | speaker-diarization-3.1 | 2023 | Significantly better speaker counting |
| speaker-diarization-3.1 | community-1 (4.0) | Late 2024 | 20-40% error reduction, exclusive mode for alignment |
| CPU-only | GPU auto-detection | 3.0+ | 10-20x speedup when GPU available |

**Deprecated/outdated:**
- **pyannote.audio 2.x:** Use 3.1+ for better API and accuracy
- **speaker-diarization-2.1:** Replaced by 3.1 with better speaker counting
- **Manual model downloads:** Use Pipeline.from_pretrained() auto-caching
- **use_auth_token parameter:** Newer versions use token= parameter (but use_auth_token still works)

**Current best practice (early 2026):**
- Use speaker-diarization-3.1 for stability or community-1 for best accuracy
- Authenticate once with huggingface_hub.login(), models auto-cache
- Use GPU when available for 10-20x speedup
- Use min/max speaker range instead of exact count for flexibility
- Use exclusive diarization mode (community-1) for easier alignment with transcription

## Open Questions

Things that couldn't be fully resolved:

1. **Time Estimation Algorithm**
   - What we know: Diarization processing time varies with audio length and speaker count
   - What's unclear: Exact formula for estimation (appears to be 0.1-0.2x real-time on GPU, 2-5x on CPU)
   - Recommendation: Implement empirical timing on first segment, extrapolate for remainder

2. **Optimal Min/Max Speaker Defaults**
   - What we know: Context says 1-5 speakers when auto-detecting, HF docs suggest narrower range improves accuracy
   - What's unclear: Whether 1-5 is too broad for typical use cases (conversations often 2-3 speakers)
   - Recommendation: Use min_speakers=1, max_speakers=5 as stated in context, allow user override via config

3. **Misalignment Warning Threshold**
   - What we know: Should warn when timestamp alignment confidence is low
   - What's unclear: What constitutes "significant misalignment" (50% overlap? 30%?)
   - Recommendation: Warn if any segment has <30% overlap with assigned speaker, log for user awareness

4. **Community-1 vs 3.1 Choice**
   - What we know: Community-1 (4.0) has better accuracy, exclusive mode; 3.1 more mature
   - What's unclear: Stability and edge case handling in community-1 since it's newer
   - Recommendation: Start with 3.1 for stability, provide community-1 as opt-in for users wanting best accuracy

5. **Model Storage Size**
   - What we know: Models cache to ~/.cache/huggingface/
   - What's unclear: Total disk space required (likely 500MB-2GB for pipeline + dependencies)
   - Recommendation: Document disk space requirements, consider warning user on first download

## Sources

### Primary (HIGH confidence)
- [pyannote/speaker-diarization-3.1 - Hugging Face](https://huggingface.co/pyannote/speaker-diarization-3.1) - Official model card, usage examples, parameters
- [pyannote/speaker-diarization-community-1 - Hugging Face](https://huggingface.co/pyannote/speaker-diarization-community-1) - Community-1 model, exclusive diarization feature
- [pyannote/pyannote-audio - GitHub](https://github.com/pyannote/pyannote-audio) - Official repository, version info, ProgressHook
- [HuggingFace Hub Quick Start](https://huggingface.co/docs/huggingface_hub/en/quick-start) - Official token authentication docs
- [HuggingFace Hub CLI](https://huggingface.co/docs/huggingface_hub/en/guides/cli) - Command line authentication

### Secondary (MEDIUM confidence)
- [Whisper and Pyannote: Ultimate Solution](https://scalastic.io/en/whisper-pyannote-ultimate-speech-transcription/) - Verified timestamp alignment implementation
- [Offline Usage Tutorial - pyannote-audio](https://github.com/pyannote/pyannote-audio/blob/develop/tutorials/community/offline_usage_speaker_diarization.ipynb) - Community tutorial on offline usage
- [Community-1 Announcement - pyannoteAI](https://www.pyannote.ai/blog/community-1) - New features and performance improvements
- [Whisper Speaker Diarization Tutorial 2026](https://brasstranscripts.com/blog/whisper-speaker-diarization-guide) - Recent integration patterns

### Tertiary (LOW confidence)
- Various GitHub issues and discussions - Anecdotal experiences with authentication, offline mode, and common problems
- WebSearch results from 2024-2026 showing ecosystem trends

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official documentation confirms pyannote.audio 3.1/4.0 as current versions with clear installation
- Architecture: HIGH - Patterns verified from official Hugging Face model cards and GitHub examples
- Pitfalls: MEDIUM - Combination of official docs and community experience (GitHub issues), not all verified in production
- Timestamp alignment: MEDIUM - Algorithm well-documented but specific implementation details require testing
- Progress estimation: LOW - No official documentation on timing formulas, requires empirical testing

**Research date:** 2026-02-01
**Valid until:** ~2026-03-01 (30 days - relatively stable domain, pyannote updates quarterly)

**Critical for planning:**
- Planner MUST include HuggingFace token management in setup tasks
- Planner MUST include timestamp alignment as separate component from diarization
- Planner MUST handle single-speaker special case
- Planner should consider GPU detection and performance warnings
- Planner should include offline mode verification in testing
