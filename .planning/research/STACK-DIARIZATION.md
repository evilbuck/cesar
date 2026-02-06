# Stack Research: Speaker Diarization & Config System

**Domain:** Offline audio transcription with speaker identification
**Researched:** 2026-02-01
**Confidence:** HIGH

## Executive Summary

This research focuses on adding speaker diarization and config file management to an existing offline transcription tool (Cesar) built on faster-whisper. The stack recommendations prioritize offline capability, cross-platform support, and integration with existing Python 3.12+, Click, Rich, and FastAPI infrastructure.

**Key findings:**
- **pyannote.audio 3.1+** is the clear winner for offline speaker diarization in 2026
- **pydantic-settings 2.x** with TOML support provides type-safe config management
- **tomli-w** for TOML writing (Python's stdlib tomllib is read-only)
- Integration with faster-whisper is well-established with proven patterns

## Recommended Stack

### Speaker Diarization

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **pyannote.audio** | >=3.1.0, <4.0 | Neural speaker diarization pipeline | Best open-source option in 2026: runs fully offline after model download, pure PyTorch (no onnxruntime issues), excellent accuracy (DER ~11-19%), strong community support, proven integration with Whisper-family models |
| **torch** | >=2.0.0 | Deep learning framework | Required by pyannote.audio; already in project (v2.7.1), GPU-optional (works on CPU) |
| **torchaudio** | >=2.0.0 | Audio processing for PyTorch | Required for pyannote.audio audio I/O; already in project (v2.7.1) |

**Model Requirements:**
- **speaker-diarization-3.1** pipeline (recommended for stability)
- **segmentation-3.0** model (auto-downloaded, ~100MB)
- **embedding model** (auto-downloaded, ~40MB)
- Total download: ~150-200MB on first use
- Storage: Models cached in `~/.cache/huggingface/hub/`
- Requires: Hugging Face account + access token (one-time setup)

### Configuration Management

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **pydantic-settings** | >=2.0.0, <3.0 | Type-safe settings loader | Native support for TOML, environment variables, and secrets; integrates seamlessly with existing Pydantic v2 in FastAPI stack; validation built-in |
| **tomli-w** | >=1.2.0 | TOML file writer | Standard TOML writer for Python 3.9+; complements stdlib tomllib (read-only); simple API matching json.dump/dumps pattern |

**Note:** Python 3.11+ includes `tomllib` for reading TOML (already available in Python 3.12 environment).

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **tomlkit** | >=0.12.0 | Style-preserving TOML editor | Optional: Only if config editing must preserve comments/formatting (e.g., interactive config wizard); heavier than tomli-w |
| **python-dotenv** | >=1.0.0 | .env file loading | Optional: If supporting .env files for environment-specific overrides (pydantic-settings includes .env support) |

## Installation

```bash
# Speaker Diarization (Core)
pip install pyannote.audio>=3.1.0

# Config Management (Core)
pip install pydantic-settings>=2.0.0 tomli-w>=1.2.0

# Optional: Style-preserving TOML editing
pip install tomlkit>=0.12.0
```

**Additional Requirements:**
- ffmpeg (system package, required by pyannote.audio for audio decoding)
- Hugging Face account + access token (one-time setup for model download)

## Alternatives Considered

### Speaker Diarization

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **pyannote.audio 3.1** | **WhisperX** | If you need tighter Whisper integration with improved timestamp alignment; trades simplicity for all-in-one solution; may have dependency conflicts with faster-whisper |
| **pyannote.audio 3.1** | **Resemblyzer** | If targeting Python 3.12+ and need lightweight solution without Hugging Face tokens; less accurate than pyannote; unmaintained (last update 2020) |
| **pyannote.audio 3.1** | **NVIDIA NeMo** | If deploying on NVIDIA GPU infrastructure at scale; overkill for CLI/small API; heavier dependencies |
| **pyannote.audio 3.1** | **SpeechBrain** | If building custom diarization pipeline; requires more ML expertise; pyannote is pre-trained and ready |

### Config Management

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **pydantic-settings + tomli-w** | **dynaconf** | If supporting many config sources (Redis, Vault, etc.); overkill for CLI + local API use case |
| **pydantic-settings + tomli-w** | **python-decouple** | If avoiding Pydantic; lighter but loses type safety and validation |
| **pydantic-settings + tomli-w** | **configparser (INI)** | If config is very simple; TOML is more expressive for nested structures |
| **tomli-w** | **tomlkit** | If config editing must preserve formatting/comments; use tomlkit when human-editable config files matter more than simplicity |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **pyannote.audio 2.x** | Deprecated; uses problematic onnxruntime dependency; 3.1+ is pure PyTorch | **pyannote.audio >=3.1.0** |
| **toml library** | Unmaintained since 2020; superseded by tomllib (stdlib) | **tomllib (read) + tomli-w (write)** |
| **resemblyzer** | Unmaintained since 2020; less accurate; no recent updates | **pyannote.audio** |
| **Cloud diarization APIs** | Violates offline-first constraint; costs money; privacy concerns | **pyannote.audio (local)** |
| **JSON for config** | No comments support; less human-friendly than TOML | **TOML with tomllib/tomli-w** |
| **YAML for config** | Overkill for simple config; security issues (arbitrary code execution); ambiguous parsing | **TOML** |

## Integration Patterns

### faster-whisper + pyannote.audio

**Proven Pattern (2026):**
1. Run pyannote diarization first → get speaker segments with timestamps
2. Run faster-whisper transcription → get text segments with timestamps
3. Align by timestamp overlap → assign speakers to transcription segments
4. Output as markdown with speaker labels

**Known Issues:**
- Dependency conflict between faster-whisper and pyannote.audio 3.0.0 (resolved in 3.1+)
- Audio preprocessing: both expect mono 16kHz (handle once, reuse)
- Timestamp alignment: use temporal intersection approach (standard practice)

**Code Structure:**
```python
# Separate concerns for testability
class SpeakerDiarizer:
    def __init__(self, model="pyannote/speaker-diarization-3.1"):
        self.pipeline = Pipeline.from_pretrained(model)

    def diarize(self, audio_path) -> List[SpeakerSegment]:
        # Returns: [(start, end, speaker_id), ...]
        pass

class TranscriptAligner:
    def align(self, diarization, transcription) -> List[TranscriptSegment]:
        # Aligns by timestamp overlap
        pass
```

### Config File Structure

**CLI Config (~/.config/cesar/config.toml):**
```toml
[transcription]
model = "base"  # tiny, base, small, medium, large-v3
device = "auto"  # auto, cpu, cuda, mps
compute_type = "auto"

[diarization]
enabled = true
model = "pyannote/speaker-diarization-3.1"
min_speakers = 2
max_speakers = 4
hf_token = ""  # Optional: read from env HF_TOKEN

[output]
format = "markdown"  # txt, json, markdown, srt
speaker_labels = true
timestamps = true
```

**API Config (./config.toml in API directory):**
```toml
[server]
host = "127.0.0.1"
port = 8000
workers = 1

[paths]
upload_dir = "./uploads"
output_dir = "./outputs"
cache_dir = "~/.cache/cesar"

[transcription]
# Inherits CLI config structure
```

**pydantic-settings Implementation:**
```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class TranscriptionSettings(BaseSettings):
    model: str = "base"
    device: str = "auto"
    compute_type: str = "auto"

class DiarizationSettings(BaseSettings):
    enabled: bool = True
    model: str = "pyannote/speaker-diarization-3.1"
    min_speakers: int | None = None
    max_speakers: int | None = None
    hf_token: str | None = Field(default=None, alias="HF_TOKEN")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file=["~/.config/cesar/config.toml", "./config.toml"],
        env_prefix="CESAR_",
        env_nested_delimiter="__",
    )

    transcription: TranscriptionSettings = Field(default_factory=TranscriptionSettings)
    diarization: DiarizationSettings = Field(default_factory=DiarizationSettings)
```

**Precedence:** CLI args > Env vars > Config file > Defaults

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| pyannote.audio 3.1.x | torch >=2.0, <2.8 | Current project has torch 2.7.1 (compatible) |
| pyannote.audio 3.1.x | Python >=3.8, <3.13 | Current project uses Python 3.12 (compatible) |
| pyannote.audio 3.1.x | faster-whisper 1.x | No conflicts in 3.1+ (pure PyTorch) |
| pydantic-settings 2.x | pydantic >=2.0 | Current project has pydantic 2.11.7 (compatible) |
| tomli-w 1.2.x | Python >=3.9 | Current project uses Python 3.12 (compatible) |
| tomlkit 0.12.x | Python >=3.8 | Current project uses Python 3.12 (compatible) |

**Critical:** pyannote.audio 3.0.0 had onnxruntime conflicts with faster-whisper. Use 3.1+ (pure PyTorch).

## System Requirements

### Model Storage
- **~/.cache/huggingface/hub/**: 150-200MB for diarization models
- **~/.cache/huggingface/hub/**: Already used by faster-whisper (existing)

### Memory
- **CPU mode**: 4-8GB RAM for typical podcast (2-4 speakers, 1-2 hours)
- **GPU mode**: 2-4GB VRAM (optional, speeds up processing 3-5x)

### Performance Estimates
- **Diarization**: ~0.1-0.3x real-time on CPU (10min audio → 30-90s)
- **Transcription**: Already optimized by faster-whisper
- **Total overhead**: +30-60% processing time vs transcription-only

## Config File Locations

### CLI Mode
- **Primary**: `~/.config/cesar/config.toml` (user-level, persistent)
- **Override**: `./cesar.toml` (project-level, optional)
- **Env vars**: `CESAR_*` prefix (e.g., `CESAR_TRANSCRIPTION__MODEL=large-v3`)

### API Mode
- **Primary**: `./config.toml` (local to API directory)
- **Override**: Environment variables (for Docker/cloud deployments)

**Rationale:**
- CLI uses user config (user's preferences persist across projects)
- API uses local config (each deployment has own settings)
- Both support env vars for Docker/CI/CD

## Sources

### Speaker Diarization
- [pyannote.audio GitHub](https://github.com/pyannote/pyannote-audio) — Installation, offline usage, Python requirements (HIGH confidence)
- [speaker-diarization-3.1 on Hugging Face](https://huggingface.co/pyannote/speaker-diarization-3.1) — Model requirements, usage instructions, offline capabilities (HIGH confidence)
- [Best Speaker Diarization Models Compared [2026]](https://brasstranscripts.com/blog/speaker-diarization-models-comparison) — Pyannote 3.1 vs alternatives, accuracy comparison (MEDIUM confidence, verified with official docs)
- [Whisper Speaker Diarization: Python Tutorial 2026](https://brasstranscripts.com/blog/whisper-speaker-diarization-guide) — Integration patterns, best practices (MEDIUM confidence)
- [Whisper and Pyannote: The Ultimate Solution for Speech Transcription](https://scalastic.io/en/whisper-pyannote-ultimate-speech-transcription/) — Integration architecture, alignment approaches (MEDIUM confidence)
- [Speaker Diarization with Pyannote on VAST](https://vast.ai/article/speaker-diarization-with-pyannote-on-vast) — System requirements, storage estimates (MEDIUM confidence)

### Config Management
- [Settings Management - Pydantic Validation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — Official pydantic-settings documentation, TOML support (HIGH confidence)
- [Python and TOML: Read, Write, and Configure with tomllib – Real Python](https://realpython.com/python-toml/) — tomllib, tomli-w, tomlkit comparison and best practices (HIGH confidence)
- [tomli-w · PyPI](https://pypi.org/project/tomli-w/) — TOML writer library details, version compatibility (HIGH confidence)
- [tomlkit · PyPI](https://pypi.org/project/tomlkit/) — Style-preserving TOML library, use cases (HIGH confidence)
- [Python TOML libraries comparison](https://docs.python.org/3/library/tomllib.html) — stdlib tomllib documentation (HIGH confidence)

### Integration
- [WhisperX GitHub](https://github.com/m-bain/whisperX) — Whisper + diarization integration patterns (MEDIUM confidence)
- [pyannote-whisper GitHub](https://github.com/yinruiqing/pyannote-whisper) — Alternative integration approach (LOW confidence, reference only)

---
*Stack research for: Cesar speaker diarization & config system*
*Researched: 2026-02-01*
