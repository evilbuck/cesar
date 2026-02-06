# Architecture Research: Speaker Diarization & Config Integration

**Domain:** Audio Transcription with Speaker Identification
**Researched:** 2026-02-01
**Confidence:** HIGH

## Executive Summary

Adding speaker diarization and configuration management to Cesar requires integrating two major architectural components:

1. **Speaker Diarization Pipeline**: Runs parallel or sequential to transcription, produces speaker labels, requires timestamp alignment with transcription segments
2. **Configuration System**: Hierarchical config loading at startup (API lifespan) and runtime (CLI per-invocation) with validation

**Key Integration Pattern:** Sequential diarization + post-processing alignment (not parallel) for simplicity and memory efficiency. Config loaded at startup for API (FastAPI lifespan), per-invocation for CLI (Click context).

## Current Architecture Baseline

### Existing Components

| Component | Layer | Responsibility | Current State |
|-----------|-------|----------------|---------------|
| `cli.py` | Presentation | Click commands, Rich UI, argument parsing | Stable - v2.1 |
| `transcriber.py` | Core | AudioTranscriber class, model loading, transcription | Stable - v2.1 |
| `api/server.py` | API | FastAPI server, lifespan management, endpoints | Stable - v2.0 |
| `api/worker.py` | Background | Async job queue processing | Stable - v2.0 |
| `api/repository.py` | Data | SQLite job persistence | Stable - v2.0 |
| `device_detection.py` | Infrastructure | Hardware detection, optimization | Stable - v2.0 |

### Current Data Flow

```
CLI/API Input → AudioTranscriber → faster-whisper → Segments → Text File
     ↓                                    ↓
File/URL/YouTube              Model Loading (lazy)
                                    ↓
                              Device Detection
```

## New Architecture: Speaker Diarization Integration

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                             │
├──────────────────────────┬──────────────────────────────────────┤
│       CLI (Click)        │      API (FastAPI)                    │
│  - Commands              │  - Endpoints                           │
│  - Config from file/args │  - Config from lifespan               │
└──────────┬───────────────┴─────────────────┬────────────────────┘
           │                                  │
           ↓                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER (NEW)                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────────┐  ┌──────────────┐   │
│  │ ConfigManager  │  │ TranscriptionOrch. │  │  Formatter   │   │
│  │ - Load config  │  │ - Coordinate steps │  │ - Markdown   │   │
│  │ - Validate     │  │ - Pass config down │  │ - Speaker    │   │
│  └────────────────┘  └────────────────────┘  │   labels     │   │
│                                               └──────────────┘   │
└────────────┬───────────────────────┬──────────────────┬─────────┘
             │                       │                  │
             ↓                       ↓                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                        PROCESSING LAYER                           │
├────────────────────────┬─────────────────────┬──────────────────┤
│  AudioTranscriber      │  SpeakerIdentifier  │  SegmentAligner  │
│  (existing)            │  (new)              │  (new)           │
│  - faster-whisper      │  - pyannote.audio   │  - Timestamp     │
│  - Returns segments    │  - Returns speakers │  - Merge logic   │
└────────────────────────┴─────────────────────┴──────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| **ConfigManager** | Load, merge, validate config hierarchy (defaults → file → env → CLI args) | Pydantic BaseSettings with custom source priority |
| **TranscriptionOrchestrator** | Coordinate transcription → diarization → alignment → formatting | New class wrapping AudioTranscriber + SpeakerIdentifier |
| **SpeakerIdentifier** | Run pyannote.audio diarization, extract speaker segments | pyannote.audio Pipeline API |
| **SegmentAligner** | Match transcription segments to speaker timestamps | Temporal overlap algorithm |
| **MarkdownFormatter** | Format segments with speaker labels (SPEAKER_00, SPEAKER_01, etc.) | String building with speaker prefixes |
| **AudioTranscriber** | (unchanged) Core transcription with faster-whisper | Existing implementation |

## Integration Point 1: Configuration System

### Config Loading Lifecycle

**CLI Path:**
```
CLI Startup
    ↓
ConfigManager.load()
    ↓
1. Load defaults (in code)
2. Load config file (~/.config/cesar/config.yaml)
3. Override with env vars (CESAR_*)
4. Override with CLI args (--model, --speaker-detection, etc.)
    ↓
Validated Config Object → Pass to TranscriptionOrchestrator
    ↓
Execute transcription with config
```

**API Path:**
```
FastAPI Lifespan Startup
    ↓
ConfigManager.load_for_api()
    ↓
1. Load defaults
2. Load config file
3. Override with env vars
    ↓
Store in app.state.config
    ↓
Per-Request: Merge app.state.config + request params
    ↓
Execute transcription with merged config
```

### Configuration Hierarchy Design

**Implementation Pattern:** Pydantic BaseSettings with custom sources

```python
# config.py (new)
from pydantic import BaseSettings, Field
from typing import Optional, Literal

class TranscriptionConfig(BaseSettings):
    """Transcription settings."""
    model_size: Literal["tiny", "base", "small", "medium", "large"] = "base"
    device: Optional[str] = None  # auto-detect if None
    compute_type: Optional[str] = None  # auto-detect if None

class SpeakerConfig(BaseSettings):
    """Speaker diarization settings."""
    enabled: bool = False
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None
    hf_token: Optional[str] = Field(None, env="HF_TOKEN")

class CesarConfig(BaseSettings):
    """Main application configuration."""
    transcription: TranscriptionConfig = TranscriptionConfig()
    speaker: SpeakerConfig = SpeakerConfig()

    class Config:
        env_prefix = "CESAR_"
        env_nested_delimiter = "__"
        # CESAR_SPEAKER__ENABLED=true
        # CESAR_TRANSCRIPTION__MODEL_SIZE=large
```

**Source Priority (highest to lowest):**
1. CLI arguments (CLI only)
2. Environment variables (`CESAR_*`)
3. Config file (`~/.config/cesar/config.yaml`)
4. Defaults (in code)

### Config Loading Locations

| Interface | When Config Loads | Where Config Stored | Lifetime |
|-----------|-------------------|---------------------|----------|
| **CLI** | Per-invocation (command startup) | Local variable in command function | Single command execution |
| **API** | Lifespan startup | `app.state.config` | Server lifetime |
| **API (per-request)** | Endpoint execution | Merged from app.state + request params | Single request |

**Rationale for API startup loading:**
- Heavy initialization (model downloads, device detection) should happen once
- Config validation errors fail fast at startup, not on first request
- Per-request overhead minimized (only merge request params, not re-load entire config)
- Consistent with existing API architecture (repository, worker initialized in lifespan)

## Integration Point 2: Speaker Diarization Pipeline

### Processing Flow: Sequential vs Parallel

**Evaluated Approaches:**

| Approach | Description | Pros | Cons | Decision |
|----------|-------------|------|------|----------|
| **Parallel** | Run diarization and transcription simultaneously | Faster (65% time reduction in WhisperX) | High VRAM (≥10GB), complex sync, harder debugging | ❌ REJECT for MVP |
| **Sequential** | Transcribe first, then diarize | Simpler, lower memory, easier debugging | Slower (2x processing time) | ✅ ACCEPT for MVP |
| **Diarization-first** | Diarize, then transcribe speaker turns | Accurate speaker boundaries | Whisper struggles with short segments, more complex | ❌ REJECT |

**Decision: Sequential (transcription → diarization → alignment)**

**Rationale:**
1. **Simplicity**: Existing AudioTranscriber unchanged, diarization is separate module
2. **Memory efficiency**: Cesar targets CPU inference (cross-platform), parallel requires ≥10GB VRAM
3. **Debugging**: Clear separation between transcription and speaker identification
4. **Build order**: MVP can ship transcription-only, add diarization as enhancement

### Detailed Processing Flow

```
Input Audio File
    ↓
┌─────────────────────────────────────────────┐
│ Step 1: Transcription                       │
│ AudioTranscriber.transcribe_file()          │
│   → Returns: List[Segment]                  │
│      segment = {text, start, end}           │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ Step 2: Speaker Diarization (if enabled)    │
│ SpeakerIdentifier.identify_speakers()       │
│   → Returns: List[SpeakerSegment]           │
│      segment = {speaker, start, end}        │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ Step 3: Alignment                           │
│ SegmentAligner.align()                      │
│   → Match transcription to speakers         │
│   → Algorithm: Temporal overlap             │
│      For each transcript segment:           │
│        Find speaker segment with max overlap│
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│ Step 4: Formatting                          │
│ MarkdownFormatter.format()                  │
│   → Produces: Markdown with speaker labels  │
│      **SPEAKER_00:** [text]                 │
│      **SPEAKER_01:** [text]                 │
└─────────────────┬───────────────────────────┘
                  ↓
Output: transcript.md
```

### Segment Alignment Algorithm

**Problem:** Transcription segments and diarization segments have different boundaries.

**Example:**
```
Transcription:  [----Segment 1 (0:00-0:05)----][----Segment 2 (0:05-0:10)----]
Diarization:    [---Speaker A (0:00-0:07)---][------Speaker B (0:07-0:15)-----]
```

**Solution: Temporal Overlap Matching** (used by WhisperX, whisper-diarization)

```python
def find_best_speaker(transcript_segment, speaker_segments):
    """Find speaker with maximum temporal overlap."""
    max_overlap = 0
    best_speaker = None

    for speaker_seg in speaker_segments:
        # Calculate overlap duration
        overlap_start = max(transcript_segment.start, speaker_seg.start)
        overlap_end = min(transcript_segment.end, speaker_seg.end)
        overlap_duration = max(0, overlap_end - overlap_start)

        if overlap_duration > max_overlap:
            max_overlap = overlap_duration
            best_speaker = speaker_seg.speaker

    return best_speaker
```

**Edge Cases:**
- No overlap: Assign to nearest speaker (by timestamp)
- Equal overlap: Assign to first speaker (deterministic)
- Overlapping speakers: Assign to speaker with max overlap
- Speaker turns mid-segment: Accept inaccuracy for MVP, refine in future (split segment)

### Data Structure Changes

**Current (v2.1):**
```python
# AudioTranscriber.transcribe_file() returns
{
    'language': 'en',
    'audio_duration': 120.5,
    'segment_count': 42,
    'output_path': '/path/to/output.txt'
}
```

**New (v3.0):**
```python
# TranscriptionOrchestrator.transcribe() returns
{
    'language': 'en',
    'audio_duration': 120.5,
    'segment_count': 42,
    'speaker_count': 3,  # NEW
    'speakers_detected': ['SPEAKER_00', 'SPEAKER_01', 'SPEAKER_02'],  # NEW
    'output_path': '/path/to/output.md'  # .md instead of .txt
}

# Internally: Segment objects gain speaker field
class TranscriptSegment:
    text: str
    start: float
    end: float
    speaker: Optional[str] = None  # NEW: "SPEAKER_00", etc.
```

## Architectural Patterns

### Pattern 1: Orchestrator with Optional Steps

**What:** TranscriptionOrchestrator coordinates a pipeline of optional processing steps based on config.

**When to use:** When you have a core workflow (transcription) that can be extended with optional enhancements (speaker ID, language detection, etc.)

**Trade-offs:**
- ✅ Clean separation: Each step is independent module
- ✅ Easy to test: Mock individual steps
- ✅ Easy to extend: Add new steps without modifying existing code
- ❌ More complexity: Additional layer between CLI/API and core logic

**Example:**
```python
class TranscriptionOrchestrator:
    def __init__(self, config: CesarConfig):
        self.config = config
        self.transcriber = AudioTranscriber(
            model_size=config.transcription.model_size
        )
        if config.speaker.enabled:
            self.speaker_identifier = SpeakerIdentifier(
                hf_token=config.speaker.hf_token
            )
        self.aligner = SegmentAligner()
        self.formatter = MarkdownFormatter()

    def transcribe(self, audio_path: str, output_path: str):
        # Step 1: Always transcribe
        segments = self.transcriber.transcribe_file(audio_path)

        # Step 2: Optional speaker identification
        if self.config.speaker.enabled:
            speaker_segments = self.speaker_identifier.identify(audio_path)
            segments = self.aligner.align(segments, speaker_segments)

        # Step 3: Format output
        output = self.formatter.format(
            segments,
            include_speakers=self.config.speaker.enabled
        )

        # Write to file
        with open(output_path, 'w') as f:
            f.write(output)
```

### Pattern 2: Config Injection at Boundaries

**What:** Config is loaded once at system boundary (CLI invocation, API startup), then passed down as constructor argument or method parameter.

**When to use:** When you want centralized config validation and explicit dependencies (no hidden global state).

**Trade-offs:**
- ✅ Testable: Easy to pass test config objects
- ✅ Explicit: Clear what config each component needs
- ✅ No globals: No hidden config.get() calls
- ❌ Verbose: Must pass config through layers

**Example:**
```python
# API lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load config once at startup
    config = ConfigManager.load_for_api()
    app.state.config = config

    # Pass config to components
    repo = JobRepository(config.database.path)
    worker = BackgroundWorker(repo, config)

    yield

    await worker.shutdown()

# Endpoint
@app.post("/transcribe")
async def transcribe(file: UploadFile):
    # Get config from app state
    config = app.state.config

    # Merge with request params (request overrides config file)
    request_config = config.copy(
        update={'transcription': {'model_size': 'large'}}
    )

    # Pass to orchestrator
    orchestrator = TranscriptionOrchestrator(request_config)
    result = orchestrator.transcribe(audio_path, output_path)
```

### Pattern 3: Lazy Model Loading with Config

**What:** Models are loaded only when needed (first use), but initialization parameters come from config loaded at startup.

**When to use:** When model downloads are expensive but you want to fail fast on config errors.

**Trade-offs:**
- ✅ Fast startup: Config validation happens immediately, model download delayed
- ✅ Memory efficient: Don't load models unless actually used
- ❌ First-request latency: API first request slower (model download)

**Example:**
```python
class SpeakerIdentifier:
    def __init__(self, config: SpeakerConfig):
        self.config = config
        self._pipeline = None  # Lazy-loaded

    def _load_pipeline(self):
        if self._pipeline is None:
            from pyannote.audio import Pipeline
            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.config.hf_token
            )
        return self._pipeline

    def identify_speakers(self, audio_path: str):
        pipeline = self._load_pipeline()  # Loads on first call
        return pipeline(audio_path)
```

## Data Flow Changes

### Current Flow (v2.1)

```
CLI: transcribe <audio> -o <output>
    ↓
AudioTranscriber(model="base")
    ↓
faster-whisper.transcribe() → segments
    ↓
Write segments to text file
    ↓
Output: plain text transcript
```

### New Flow with Speaker Diarization (v3.0)

```
CLI: transcribe <audio> -o <output> --speaker-detection
    ↓
ConfigManager.load_cli(args)
    ↓
TranscriptionOrchestrator(config)
    ↓
├─ AudioTranscriber.transcribe() → text segments (0:00-0:05, text)
│
├─ SpeakerIdentifier.identify() → speaker segments (0:00-0:07, SPEAKER_00)
│
├─ SegmentAligner.align(text_seg, spkr_seg) → labeled segments
│       ↓
│   For each text segment:
│       Find speaker with max temporal overlap
│       Attach speaker label to segment
│
└─ MarkdownFormatter.format(labeled_segments)
    ↓
Output: Markdown with speaker labels
**SPEAKER_00:** [text from 0:00-0:05]
**SPEAKER_01:** [text from 0:05-0:10]
```

### State Management

| Component | State | Lifetime | Storage |
|-----------|-------|----------|---------|
| **ConfigManager** | Loaded config object | Single transcription | Local variable (CLI), app.state (API) |
| **AudioTranscriber** | Loaded whisper model | Persistent (lazy-loaded) | Instance variable `._model` |
| **SpeakerIdentifier** | Loaded pyannote pipeline | Persistent (lazy-loaded) | Instance variable `._pipeline` |
| **TranscriptionOrchestrator** | References to sub-components | Single transcription | Instance variables |

**Key principle:** Models are lazy-loaded and cached in instance variables. Config is loaded once at boundary and passed down.

## Scaling Considerations

| Scale | Current (v2.1) | With Diarization (v3.0) |
|-------|----------------|-------------------------|
| **0-10 files** | Fast CPU transcription | 2x slower (sequential diarization), acceptable |
| **10-100 files** | Batch mode with progress | Same, but consider async API for parallel jobs |
| **100+ files** | API with job queue | API becomes required for queue management |

### Performance Characteristics

**Transcription only (existing):**
- Speed: 60-70x real-time (base model, CPU)
- Memory: ~2GB (base model)

**Transcription + Speaker Diarization (new):**
- Speed: 30-40x real-time (2x slower due to sequential processing)
- Memory: ~4GB (both models loaded)
- Bottleneck: Diarization is the slower step (pyannote model inference)

**Optimization Paths (future):**
1. **Parallel processing** (requires GPU): Run both models simultaneously → 65% time reduction
2. **Batch diarization**: Process multiple files in parallel (API only)
3. **Model quantization**: Smaller pyannote model for faster inference

## Anti-Patterns

### Anti-Pattern 1: Global Config Singleton

**What people do:**
```python
# config.py
config = load_config()  # Global singleton

# transcriber.py
from config import config  # Import global
```

**Why it's wrong:**
- Impossible to test (can't inject test config)
- Hidden dependency (not clear what config each component uses)
- Hard to override (CLI args can't easily override)

**Do this instead:**
```python
# Load config at boundary
config = ConfigManager.load()

# Pass explicitly
transcriber = AudioTranscriber(config.transcription)
```

### Anti-Pattern 2: Parallel Processing Without Memory Check

**What people do:**
```python
# Run both models simultaneously without checking VRAM
with concurrent.futures.ThreadPoolExecutor():
    future1 = executor.submit(transcribe, audio)
    future2 = executor.submit(diarize, audio)
```

**Why it's wrong:**
- OOM errors on systems without GPU (Cesar's target: cross-platform CPU)
- Requires ≥10GB VRAM, not available on most laptops
- Complex error handling (one fails, need to cancel other)

**Do this instead:**
```python
# Sequential processing for MVP
segments = transcriber.transcribe(audio)  # Step 1
speaker_segments = diarizer.identify(audio)  # Step 2
aligned = aligner.align(segments, speaker_segments)  # Step 3

# Future: Parallel only if GPU available and sufficient VRAM
if has_gpu and gpu_memory_gb >= 10:
    # Parallel path
else:
    # Sequential path (MVP)
```

### Anti-Pattern 3: Config Validation at Use Time

**What people do:**
```python
def transcribe(audio, model_size):
    if model_size not in VALID_MODELS:  # Validation at use time
        raise ValueError("Invalid model")
    # ... transcribe
```

**Why it's wrong:**
- Errors happen late (after user waits for download, etc.)
- Can't provide helpful error messages at CLI invocation
- API returns 500 errors instead of 400 (validation errors)

**Do this instead:**
```python
# Pydantic validation at config load time (startup)
class Config(BaseSettings):
    model_size: Literal["tiny", "base", "small", "medium", "large"]
    # Validation error raised immediately if invalid

# CLI gets Click validation
@click.option('--model', type=click.Choice([...]))
```

### Anti-Pattern 4: Modifying AudioTranscriber for Diarization

**What people do:**
```python
class AudioTranscriber:
    def transcribe_file(self, audio_path, enable_speakers=False):
        # ... transcription logic
        if enable_speakers:
            # Diarization logic embedded in transcriber
            speakers = self._identify_speakers(audio_path)
```

**Why it's wrong:**
- Violates Single Responsibility Principle
- AudioTranscriber now depends on pyannote (heavy dependency)
- Can't test transcription without diarization dependencies
- Harder to make diarization optional

**Do this instead:**
```python
# Keep AudioTranscriber focused
class AudioTranscriber:
    def transcribe_file(self, audio_path):
        # Only transcription logic
        return segments

# New component for diarization
class SpeakerIdentifier:
    def identify_speakers(self, audio_path):
        # Diarization logic
        return speaker_segments

# Orchestrator coordinates both
class TranscriptionOrchestrator:
    def transcribe(self, audio_path, enable_speakers):
        segments = self.transcriber.transcribe(audio_path)
        if enable_speakers:
            speakers = self.speaker_identifier.identify(audio_path)
            segments = self.aligner.align(segments, speakers)
        return segments
```

## Integration Boundaries

### CLI ↔ Core

**Interface:** TranscriptionOrchestrator

```python
# cli.py
@cli.command()
def transcribe(input_file, output, speaker_detection, ...):
    # 1. Load config
    config = ConfigManager.load_cli(
        args={'speaker': {'enabled': speaker_detection}, ...}
    )

    # 2. Create orchestrator
    orchestrator = TranscriptionOrchestrator(config)

    # 3. Execute with progress callback
    result = orchestrator.transcribe(
        input_file,
        output,
        progress_callback=progress_tracker.update
    )

    # 4. Display results
    console.print(f"Detected {result['speaker_count']} speakers")
```

**Boundary Responsibility:**
- CLI: User interaction, argument parsing, progress display, error formatting
- Core: Business logic (transcription, diarization, alignment)

### API ↔ Core

**Interface:** TranscriptionOrchestrator (same as CLI)

```python
# api/server.py lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load config once
    config = ConfigManager.load_for_api()
    app.state.config = config

    # Initialize components (models lazy-loaded later)
    app.state.orchestrator = TranscriptionOrchestrator(config)

    yield

# api/worker.py
async def _process_job(self, job):
    # Get config from app state
    config = app.state.config

    # Merge with job params
    job_config = config.copy(
        update={'transcription': {'model_size': job.model_size}}
    )

    # Create orchestrator with job-specific config
    orchestrator = TranscriptionOrchestrator(job_config)

    # Execute (blocking, run in thread pool)
    result = await asyncio.to_thread(
        orchestrator.transcribe,
        job.audio_path,
        output_path
    )
```

**Boundary Responsibility:**
- API: HTTP layer, job queue, async coordination, authentication (future)
- Core: Transcription logic (same as CLI)

### Core ↔ External Services

| Service | Integration | Notes |
|---------|-------------|-------|
| **faster-whisper** | Direct import, PyTorch model | Existing, no changes |
| **pyannote.audio** | Direct import, requires HF token | New dependency, optional (only if speaker detection enabled) |
| **HuggingFace Hub** | Model downloads via HF API | Both whisper and pyannote download from HF |

**Authentication:**
- pyannote models require HuggingFace token (config: `speaker.hf_token` or env: `HF_TOKEN`)
- Token loaded from config hierarchy (env var → config file → fail if missing and speaker detection enabled)

## Build Order Recommendations

### Phase 1: Configuration System
**Goal:** Config loading without diarization

**Tasks:**
1. Create `config.py` with Pydantic BaseSettings
2. Implement ConfigManager with hierarchy (defaults → file → env → args)
3. Integrate with CLI (load config, pass to AudioTranscriber)
4. Integrate with API (load in lifespan, store in app.state)
5. Tests: Config loading, hierarchy, validation

**Why first:**
- Foundation for all new features
- Can ship independently (existing transcription now uses config)
- Easier to test (no ML models)

**Validation:** CLI and API work with config file, env vars, and CLI args. Existing transcription functionality unchanged.

### Phase 2: Speaker Diarization Core
**Goal:** Diarization module and alignment logic

**Tasks:**
1. Create `speaker_identifier.py` with SpeakerIdentifier class
2. Implement pyannote pipeline integration
3. Create `segment_aligner.py` with temporal overlap algorithm
4. Tests: Diarization on sample audio, alignment accuracy

**Why second:**
- Core logic independent of orchestration
- Can test with simple audio files
- Establishes diarization API before integration

**Validation:** SpeakerIdentifier.identify() returns speaker segments. SegmentAligner.align() correctly matches segments.

### Phase 3: Orchestration & Formatting
**Goal:** Integrate diarization with transcription

**Tasks:**
1. Create `transcription_orchestrator.py`
2. Implement step-by-step pipeline (transcribe → diarize → align)
3. Create `markdown_formatter.py` for speaker-labeled output
4. Tests: End-to-end orchestration with sample files

**Why third:**
- Depends on Phases 1 & 2
- Integration logic distinct from core modules
- Tests validate full pipeline

**Validation:** Orchestrator produces markdown output with speaker labels. All steps execute in correct order.

### Phase 4: CLI Integration
**Goal:** Expose speaker detection in CLI

**Tasks:**
1. Add `--speaker-detection` flag to CLI
2. Add `--speaker-config` options (min/max speakers)
3. Update progress display for diarization step
4. Update result display (show speaker count)
5. Tests: CLI with speaker detection enabled/disabled

**Why fourth:**
- User-facing feature
- Depends on Phases 1-3
- Easiest interface to test manually

**Validation:** `cesar transcribe audio.mp3 -o output.md --speaker-detection` produces speaker-labeled transcript.

### Phase 5: API Integration
**Goal:** Expose speaker detection in API

**Tasks:**
1. Add speaker detection params to API endpoints
2. Update Job model with speaker-related fields
3. Update worker to use orchestrator
4. Update API responses with speaker info
5. Tests: API endpoints with speaker detection

**Why fifth:**
- Parallel to CLI integration (can do Phase 4 & 5 in any order)
- More complex due to async job queue

**Validation:** API `/transcribe/url` with `speaker_detection=true` produces speaker-labeled transcript in job result.

## Sources

**Speaker Diarization:**
- [pyannote/pyannote-audio GitHub](https://github.com/pyannote/pyannote-audio)
- [pyannote/speaker-diarization-3.1 on Hugging Face](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [Best Speaker Diarization Models Compared 2026](https://brasstranscripts.com/blog/speaker-diarization-models-comparison)
- [Whisper Speaker Diarization: Python Tutorial 2026](https://brasstranscripts.com/blog/whisper-speaker-diarization-guide)
- [MahmoudAshraf97/whisper-diarization GitHub](https://github.com/MahmoudAshraf97/whisper-diarization)
- [WhisperX GitHub](https://github.com/m-bain/whisperX)
- [Whisper and Pyannote: The Ultimate Solution for Speech Transcription](https://scalastic.io/en/whisper-pyannote-ultimate-speech-transcription/)
- [Building a Custom Audio Transcription Pipeline (Medium)](https://medium.com/@rafaelgalle1/building-a-custom-scalable-audio-transcription-pipeline-whisper-pyannote-ffmpeg-d0f03f884330)

**Configuration Management:**
- [Pydantic BaseSettings vs. Dynaconf Guide](https://leapcell.io/blog/pydantic-basesettings-vs-dynaconf-a-modern-guide-to-application-configuration)
- [Dynaconf GitHub](https://github.com/dynaconf/dynaconf)
- [Python Structured Config with Dynaconf/Pydantic (Medium)](https://medium.com/@2nick2patel2/python-structured-config-with-dynaconf-pydantic-twelve-factor-services-without-surprises-518349d92d4f)
- [FastAPI Settings and Environment Variables](https://fastapi.tiangolo.com/advanced/settings/)
- [Pydantic Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [FastAPI + Pydantic Settings (Medium)](https://medium.com/@hadiyolworld007/fastapi-pydantic-settings-twelve-factor-secrets-and-config-without-footguns-7990e2f20919)

**FastAPI Lifecycle:**
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI Lifespan vs @lru_cache Discussion](https://github.com/fastapi/fastapi/discussions/11987)
- [FastAPI/Starlette Lifecycle Guide (Medium)](https://medium.com/@dynamicy/fastapi-starlette-lifecycle-guide-startup-order-pitfalls-best-practices-and-a-production-ready-53e29dcb9249)

---

*Architecture research for speaker diarization and config integration in Cesar transcription tool*
*Researched: 2026-02-01*
