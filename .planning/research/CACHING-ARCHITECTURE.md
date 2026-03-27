# Architecture Research: Artifact Caching Integration

**Project:** Cesar Offline Transcription
**Research Date:** 2026-02-02
**Confidence:** HIGH

## Executive Summary

This research examines how to integrate artifact caching into Cesar's existing multi-stage processing pipeline (Download → Transcription → Diarization → Formatting). The architecture must support idempotent processing with partial failure recovery while integrating cleanly with the existing TranscriptionOrchestrator pattern.

**Key Finding:** Implement a content-addressable cache layer that preserves artifacts from successful stages, enabling pipeline resumption from the last successful checkpoint after failure. This requires introducing a CacheManager component that coordinates with the orchestrator while maintaining backward compatibility with existing CLI and API interfaces.

## Current Architecture Analysis

### Existing Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    TranscriptionOrchestrator                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. Download (if YouTube URL)                                    │
│     └─> YouTubeHandler.download_youtube_audio()                 │
│                                                                   │
│  2. Transcription                                                │
│     └─> WhisperXPipeline.transcribe() OR                        │
│         AudioTranscriber.transcribe_to_segments() (fallback)     │
│                                                                   │
│  3. Diarization                                                  │
│     └─> WhisperXPipeline.diarize()                              │
│         (integrated in transcribe_and_diarize())                 │
│                                                                   │
│  4. Formatting                                                   │
│     └─> MarkdownTranscriptFormatter.format()                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Current Integration Points

| Component | Role | Caching Impact |
|-----------|------|----------------|
| **TranscriptionOrchestrator** | Coordinates pipeline stages | **PRIMARY INTEGRATION POINT** |
| **BackgroundWorker** | Async job processor (API mode) | Job status tracking coordination |
| **JobRepository** | SQLite persistence | Job metadata storage |
| **CLI** | Direct orchestrator usage | Cache-aware invocation |
| **API Server** | Job submission | Cache invalidation on retry |

### Existing Error Handling

The orchestrator already implements **graceful degradation**:
- Diarization failure → Falls back to plain transcription
- Authentication error → Re-raised to user
- Transcription segments preserved even when diarization fails

This pattern aligns with artifact caching goals: **preserve successful work, retry only failed stages**.

## Recommended Architecture

### Component Design

```
┌───────────────────────────────────────────────────────────────────┐
│                      CacheManager (NEW)                            │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  - check_cache(key: str, stage: Stage) -> Optional[Path]          │
│  - store_artifact(key: str, stage: Stage, data: Path) -> None     │
│  - invalidate(key: str) -> None                                   │
│  - get_cache_key(input_params: dict) -> str                       │
│                                                                     │
│  Storage: ~/.cache/cesar/artifacts/{stage}/{hash[:2]}/{hash}      │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
              ↑                                    ↑
              │                                    │
┌─────────────┴────────────────────────────────────┴────────────────┐
│            TranscriptionOrchestrator (MODIFIED)                    │
├───────────────────────────────────────────────────────────────────┤
│                                                                     │
│  + __init__(..., cache_manager: Optional[CacheManager] = None)    │
│  + orchestrate(..., enable_cache: bool = True)                    │
│                                                                     │
│  Modified flow:                                                    │
│  1. Generate cache key from input parameters                      │
│  2. Check cache for each stage before execution                   │
│  3. Execute stage only if cache miss                              │
│  4. Store successful stage outputs to cache                       │
│  5. On stage failure, preserve prior stage artifacts              │
│                                                                     │
└───────────────────────────────────────────────────────────────────┘
```

### Cache Key Strategy

**Content-Addressable Storage (CAS)** using cryptographic hashing ensures idempotent operations.

#### Stage-Specific Keys

| Stage | Key Components | Hash Algorithm | Example Key |
|-------|---------------|----------------|-------------|
| **Download** | `youtube_url + quality_preference` | SHA256 | `yt_8a3f2e...` |
| **Transcription** | `audio_file_hash + model_size + device + compute_type` | SHA256 | `tx_4d9c1a...` |
| **Diarization** | `audio_file_hash + min_speakers + max_speakers + hf_token_hash` | SHA256 | `dz_7e2b4f...` |
| **Formatting** | **NOT CACHED** (cheap operation, style may change) | N/A | N/A |

#### Key Generation Algorithm

```python
def generate_cache_key(stage: Stage, params: dict) -> str:
    """Generate content-addressable cache key.

    Args:
        stage: Pipeline stage (download, transcription, diarization)
        params: Stage-specific parameters

    Returns:
        Cache key format: {stage_prefix}_{sha256_hash}
    """
    # Stage-specific parameter serialization
    if stage == Stage.DOWNLOAD:
        key_data = f"{params['url']}|{params.get('quality', 'best')}"
    elif stage == Stage.TRANSCRIPTION:
        audio_hash = _compute_file_hash(params['audio_path'])
        key_data = f"{audio_hash}|{params['model_size']}|{params['device']}|{params['compute_type']}"
    elif stage == Stage.DIARIZATION:
        audio_hash = _compute_file_hash(params['audio_path'])
        # Hash HF token rather than including plaintext
        token_hash = _hash_string(params.get('hf_token', 'none'))
        key_data = f"{audio_hash}|{params['min_speakers']}|{params['max_speakers']}|{token_hash}"

    # Generate SHA256 hash
    key_hash = hashlib.sha256(key_data.encode('utf-8')).hexdigest()
    stage_prefix = stage.value[:2]  # 'yt', 'tx', 'dz'

    return f"{stage_prefix}_{key_hash}"
```

### Storage Structure

```
~/.cache/cesar/
├── artifacts/
│   ├── download/           # YouTube audio files
│   │   ├── 8a/
│   │   │   └── 8a3f2e...{full_hash}.m4a
│   │   └── metadata.json   # Original URL, download date, title
│   ├── transcription/      # Whisper segments (JSON format)
│   │   ├── 4d/
│   │   │   ├── 4d9c1a...{full_hash}.json
│   │   │   └── 4d9c1a...{full_hash}.metadata.json
│   │   └── ...
│   └── diarization/        # WhisperX segments with speakers
│       ├── 7e/
│       │   ├── 7e2b4f...{full_hash}.json
│       │   └── 7e2b4f...{full_hash}.metadata.json
│       └── ...
└── index.db               # SQLite index for cache management
```

**Storage format rationale:**
- **Git-style sharding** (first 2 chars of hash) prevents directory bloat
- **JSON for segments** enables inspection and debugging
- **Metadata files** track creation date, source parameters, duration
- **SQLite index** enables efficient queries (find by date, model, etc.)

### Artifact Data Structures

#### Transcription Artifact

```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "Hello world"
    }
  ],
  "metadata": {
    "audio_duration": 120.5,
    "language": "en",
    "language_probability": 0.98,
    "model_size": "large-v2",
    "processing_time": 15.2,
    "created_at": "2026-02-02T10:30:00Z"
  }
}
```

#### Diarization Artifact

```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "speaker": "SPEAKER_00",
      "text": "Hello world"
    }
  ],
  "metadata": {
    "speaker_count": 2,
    "audio_duration": 120.5,
    "min_speakers": 1,
    "max_speakers": 5,
    "processing_time": 45.8,
    "created_at": "2026-02-02T10:30:45Z"
  }
}
```

## Integration with Orchestrator

### Modified Orchestrator Flow

```python
class TranscriptionOrchestrator:
    def __init__(
        self,
        pipeline: Optional[WhisperXPipeline] = None,
        transcriber: Optional[AudioTranscriber] = None,
        formatter: Optional[MarkdownTranscriptFormatter] = None,
        cache_manager: Optional[CacheManager] = None  # NEW
    ):
        self.pipeline = pipeline
        self.transcriber = transcriber
        self.formatter = formatter
        self.cache_manager = cache_manager

    def orchestrate(
        self,
        audio_path: Path,
        output_path: Path,
        enable_diarization: bool = True,
        enable_cache: bool = True,  # NEW
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        progress_callback: Optional[Callable] = None
    ) -> OrchestrationResult:
        """Run pipeline with optional caching."""

        # Phase 1: Check transcription cache
        tx_cache_key = None
        cached_segments = None

        if enable_cache and self.cache_manager:
            tx_cache_key = self.cache_manager.get_cache_key(
                stage=Stage.TRANSCRIPTION,
                audio_path=audio_path,
                model_size=self.pipeline.model_name if self.pipeline else "base"
            )
            cached_segments = self.cache_manager.check_cache(
                tx_cache_key,
                Stage.TRANSCRIPTION
            )

        # Phase 2: Transcription (cache or compute)
        if cached_segments:
            logger.info("Using cached transcription")
            segments = cached_segments
            # Load metadata from cache
            audio_duration, transcription_time = self.cache_manager.get_metadata(
                tx_cache_key, Stage.TRANSCRIPTION
            )
        else:
            # Compute transcription
            segments, audio_duration, transcription_time = self._execute_transcription(
                audio_path, progress_callback
            )

            # Cache result if enabled
            if enable_cache and self.cache_manager:
                self.cache_manager.store_artifact(
                    tx_cache_key,
                    Stage.TRANSCRIPTION,
                    segments=segments,
                    metadata={
                        'audio_duration': audio_duration,
                        'transcription_time': transcription_time
                    }
                )

        # Phase 3: Diarization (if requested, with cache check)
        if enable_diarization and self.pipeline:
            dz_cache_key = None
            cached_diarization = None

            if enable_cache and self.cache_manager:
                dz_cache_key = self.cache_manager.get_cache_key(
                    stage=Stage.DIARIZATION,
                    audio_path=audio_path,
                    min_speakers=min_speakers,
                    max_speakers=max_speakers
                )
                cached_diarization = self.cache_manager.check_cache(
                    dz_cache_key,
                    Stage.DIARIZATION
                )

            if cached_diarization:
                logger.info("Using cached diarization")
                segments = cached_diarization
                # Extract speaker count from cached segments
                speakers_detected = len(set(seg.speaker for seg in segments))
                diarization_succeeded = True
            else:
                # Attempt diarization
                try:
                    segments, speakers_detected, diarization_time = self._execute_diarization(
                        audio_path, segments, min_speakers, max_speakers, progress_callback
                    )
                    diarization_succeeded = True

                    # Cache successful diarization
                    if enable_cache and self.cache_manager:
                        self.cache_manager.store_artifact(
                            dz_cache_key,
                            Stage.DIARIZATION,
                            segments=segments,
                            metadata={
                                'speaker_count': speakers_detected,
                                'diarization_time': diarization_time
                            }
                        )
                except DiarizationError as e:
                    logger.warning(f"Diarization failed: {e}, using cached transcription")
                    # Segments already contains cached transcription from Phase 2
                    diarization_succeeded = False

        # Phase 4: Format (never cached - cheap operation)
        formatted_text = self.formatter.format(segments)
        final_output = output_path.with_suffix('.md' if diarization_succeeded else '.txt')
        final_output.write_text(formatted_text)

        return OrchestrationResult(...)
```

### Cache Invalidation Strategy

| Trigger | Action | Rationale |
|---------|--------|-----------|
| **User explicit retry** | Clear all stage caches for job | User wants fresh processing |
| **Parameter change** | Automatic (different cache key) | Different params = different cache |
| **Model upgrade** | Manual via CLI command | Allow users to regenerate with new model |
| **Diarization-only retry** | Keep transcription cache, clear diarization | Preserve expensive transcription work |
| **Age-based expiration** | Configurable TTL (default: 30 days) | Prevent unbounded cache growth |

## Integration with API Worker

### Modified Worker Flow

```python
class BackgroundWorker:
    def __init__(
        self,
        repository: JobRepository,
        cache_manager: Optional[CacheManager] = None,  # NEW
        poll_interval: float = 1.0,
        config: Optional[CesarConfig] = None
    ):
        self.repository = repository
        self.cache_manager = cache_manager
        # ... existing fields

    async def _process_job(self, job) -> None:
        """Process job with cache support."""

        # Check for retry scenario with explicit cache invalidation
        is_retry_fresh = (
            job.result_text is not None and
            job.diarization_error is not None and
            job.retry_requested  # NEW field
        )

        if is_retry_fresh and self.cache_manager:
            # User explicitly retried - invalidate all caches for this audio
            audio_hash = self.cache_manager.compute_file_hash(job.audio_path)
            self.cache_manager.invalidate_by_audio_hash(audio_hash)

        # Pass cache_manager to orchestrator
        orchestrator = TranscriptionOrchestrator(
            pipeline=pipeline,
            transcriber=transcriber,
            cache_manager=self.cache_manager  # NEW
        )

        result = await asyncio.to_thread(
            orchestrator.orchestrate,
            audio_path=Path(job.audio_path),
            output_path=temp_output_path,
            enable_diarization=job.diarize,
            enable_cache=True,  # Always enabled unless explicitly disabled
            min_speakers=job.min_speakers,
            max_speakers=job.max_speakers
        )
```

### Job Repository Schema Extension

**OPTIONAL** - Track cache usage in job metadata:

```sql
ALTER TABLE jobs ADD COLUMN transcription_cached BOOLEAN DEFAULT FALSE;
ALTER TABLE jobs ADD COLUMN diarization_cached BOOLEAN DEFAULT FALSE;
ALTER TABLE jobs ADD COLUMN cache_hit_ratio REAL;  -- 0.0 to 1.0
```

This enables analytics on cache effectiveness.

## CLI Integration

### CLI Usage

```bash
# Standard usage with caching enabled (default)
cesar transcribe audio.mp3 -o output.txt

# Disable caching (force fresh processing)
cesar transcribe audio.mp3 -o output.txt --no-cache

# Clear cache for specific audio file
cesar cache clear audio.mp3

# Clear all cache
cesar cache clear --all

# Show cache statistics
cesar cache stats
```

### CLI Implementation

```python
@click.command()
@click.argument('audio_path', type=click.Path(exists=True))
@click.option('-o', '--output', required=True)
@click.option('--no-cache', is_flag=True, help='Disable artifact caching')
def transcribe(audio_path: str, output: str, no_cache: bool):
    """Transcribe audio with optional caching."""

    # Initialize cache manager (unless disabled)
    cache_manager = None if no_cache else CacheManager()

    # Create orchestrator with cache
    orchestrator = TranscriptionOrchestrator(
        pipeline=pipeline,
        transcriber=transcriber,
        cache_manager=cache_manager
    )

    result = orchestrator.orchestrate(
        audio_path=Path(audio_path),
        output_path=Path(output),
        enable_cache=not no_cache
    )

    # Report cache usage
    if cache_manager and not no_cache:
        click.echo(f"Cache hits: {cache_manager.get_hit_count()}")
```

## Suggested Build Order

### Phase 1: Foundation (Core Caching Infrastructure)

**Goal:** Implement CacheManager with basic storage and retrieval.

1. **CacheManager class** (cesar/cache_manager.py)
   - File-based storage with Git-style sharding
   - SHA256 key generation
   - Basic store/retrieve operations
   - No orchestrator integration yet

2. **Unit tests** for CacheManager
   - Key generation with different parameters
   - Storage and retrieval
   - Cache directory structure
   - File hash computation

**Deliverable:** Standalone caching system ready for integration.

### Phase 2: Orchestrator Integration

**Goal:** Integrate cache with transcription pipeline.

1. **Modify TranscriptionOrchestrator**
   - Add optional cache_manager parameter
   - Implement transcription caching logic
   - Preserve existing behavior when cache_manager is None

2. **Add diarization caching**
   - Cache WhisperX diarization results
   - Handle partial failure with cached transcription

3. **Integration tests**
   - Cache hit/miss scenarios
   - Failure recovery with cached artifacts
   - Parameter variation triggering different cache keys

**Deliverable:** Working orchestrator with transparent caching.

### Phase 3: CLI & Cache Management

**Goal:** User-facing cache control.

1. **CLI cache commands**
   - `cesar cache stats` - Show cache size, hit rate
   - `cesar cache clear` - Clear cache
   - `--no-cache` flag for transcribe command

2. **Cache maintenance**
   - Age-based expiration
   - Size-based LRU eviction
   - Orphan cleanup

**Deliverable:** Complete CLI cache management.

### Phase 4: API Worker Integration

**Goal:** Cache support in async API mode.

1. **BackgroundWorker modifications**
   - Pass cache_manager to orchestrator
   - Handle retry scenarios
   - Cache invalidation on explicit retry

2. **Job repository extensions** (optional)
   - Track cache usage metrics
   - Cache hit ratio reporting

3. **API endpoints** (optional)
   - GET /cache/stats
   - DELETE /cache/{job_id}

**Deliverable:** Full API caching support.

### Phase 5: YouTube Download Caching (Optional)

**Goal:** Cache downloaded YouTube audio.

1. **YouTube cache implementation**
   - Cache by URL + quality
   - Store metadata (title, duration, download date)
   - TTL-based expiration (shorter than transcription cache)

2. **YouTubeHandler integration**
   - Check cache before download
   - Store successful downloads

**Deliverable:** Complete multi-stage caching.

## Architecture Patterns & Anti-Patterns

### Patterns to Follow

#### 1. Content-Addressable Storage

**What:** Use cryptographic hash of inputs as cache key.

**When:** For all caching stages.

**Why:** Guarantees cache correctness - same inputs always produce same key. Automatic cache invalidation when inputs change.

**Example:**
```python
# Good: Content-based key
audio_hash = hashlib.sha256(audio_file.read_bytes()).hexdigest()
cache_key = f"tx_{audio_hash}_{model_size}"

# Bad: Path-based key (fails if file moves/changes)
cache_key = f"tx_{audio_file.name}"
```

#### 2. Lazy Model Loading with Cache

**What:** Load models only when cache miss occurs.

**When:** Orchestrator checks cache before initializing WhisperX pipeline.

**Why:** Skip expensive model loading if cached result available.

**Example:**
```python
if cached_result := cache_manager.check_cache(key):
    return cached_result  # No model loading needed!

# Only load model if cache miss
self._load_whisper_model()
result = self.model.transcribe(...)
```

#### 3. Partial Failure Artifact Preservation

**What:** Store successful stage outputs even when later stages fail.

**When:** After each pipeline stage completion.

**Why:** Enables resumption without re-running expensive earlier stages.

**Example:**
```python
# Phase 1: Transcription (expensive)
segments = self._transcribe(audio)
cache_manager.store(tx_key, segments)  # Cache immediately

# Phase 2: Diarization (may fail)
try:
    segments = self._diarize(segments)
    cache_manager.store(dz_key, segments)
except DiarizationError:
    # Transcription cache preserved! Next retry starts from diarization.
    pass
```

#### 4. Optional Caching with Graceful Degradation

**What:** Make cache_manager optional everywhere.

**When:** All components that use caching.

**Why:** Maintains backward compatibility, enables testing without cache, allows cache-disabled operation.

**Example:**
```python
def orchestrate(self, ..., cache_manager: Optional[CacheManager] = None):
    if cache_manager:
        cached = cache_manager.check_cache(key)
        if cached:
            return cached

    # Normal processing continues if no cache
    return self._process()
```

### Anti-Patterns to Avoid

#### 1. Session-Based Cache Keys (AVOID)

**What:** Using job ID or session ID as cache key.

**Why bad:** Same audio with same parameters processed twice generates different keys, defeating cache purpose.

**Instead:** Use content-addressable keys based on file hash and parameters.

```python
# Bad: Session-based key
cache_key = f"tx_{job.id}"  # Different every job!

# Good: Content-based key
cache_key = f"tx_{audio_hash}_{model_size}"  # Reusable!
```

#### 2. Caching Formatted Output (AVOID)

**What:** Caching the final Markdown-formatted transcript.

**Why bad:** Formatting is cheap (<1s), style may change, wastes cache space.

**Instead:** Only cache expensive operations (transcription, diarization). Format on every run.

```python
# Bad: Cache final output
cache_manager.store("formatted", markdown_text)

# Good: Cache expensive segments, format fresh
cache_manager.store("diarization", segments)
final_output = formatter.format(segments)  # Always fresh
```

#### 3. Synchronous Cache I/O in Async Context (AVOID)

**What:** Blocking file I/O in async functions.

**Why bad:** Blocks event loop, degrades API performance.

**Instead:** Use `asyncio.to_thread()` for cache operations in BackgroundWorker.

```python
# Bad: Blocking in async context
async def process_job(self, job):
    cached = self.cache_manager.check_cache(key)  # Blocks!

# Good: Run in thread pool
async def process_job(self, job):
    cached = await asyncio.to_thread(
        self.cache_manager.check_cache, key
    )
```

#### 4. Unbounded Cache Growth (AVOID)

**What:** No cache eviction strategy.

**Why bad:** Cache grows indefinitely, fills disk.

**Instead:** Implement LRU eviction and/or TTL-based expiration.

```python
# Required: Eviction strategy
class CacheManager:
    def __init__(self, max_size_gb: int = 10, ttl_days: int = 30):
        self.max_size = max_size_gb * 1024**3
        self.ttl = timedelta(days=ttl_days)

    def evict_old_entries(self):
        """Remove entries older than TTL or exceeding max size."""
        # Implementation required
```

## Scalability Considerations

### At 100 Users

**Storage:** ~10 GB cache (100 users × 10 files × 10 MB avg)

**Approach:**
- Simple file-based storage adequate
- No distributed caching needed
- Local disk cache per machine

### At 10K Users

**Storage:** ~1 TB cache

**Approach:**
- May need cache size limits per user
- Consider shared cache server (Redis/S3)
- Implement aggressive LRU eviction
- Monitor disk usage, alert on 80% full

### At 1M Users (Hypothetical)

**Storage:** ~100 TB cache

**Approach:**
- **Distributed cache layer required** (Redis Cluster, S3)
- **Sharded storage** by user_id or audio_hash prefix
- **CDN-style architecture** with regional caches
- **Hot/cold tier split:**
  - Hot: Recent/frequently accessed (Redis)
  - Cold: Older artifacts (S3 Glacier)

**Architecture shift:**
```
                    ┌─────────────┐
                    │ API Gateway │
                    └──────┬──────┘
                           │
                 ┌─────────┴─────────┐
                 │                   │
         ┌───────▼────────┐  ┌──────▼────────┐
         │  Regional DC   │  │  Regional DC  │
         │   US-West      │  │   US-East     │
         └───────┬────────┘  └───────┬───────┘
                 │                   │
         ┌───────▼────────┐  ┌───────▼───────┐
         │ Redis Cluster  │  │ Redis Cluster │
         │   (Hot Cache)  │  │  (Hot Cache)  │
         └───────┬────────┘  └───────┬───────┘
                 │                   │
         ┌───────▼────────┐  ┌───────▼───────┐
         │  S3 Regional   │  │  S3 Regional  │
         │  (Cold Cache)  │  │ (Cold Cache)  │
         └────────────────┘  └───────────────┘
```

## Cache Metadata Schema

### SQLite Index (index.db)

```sql
CREATE TABLE cache_entries (
    cache_key TEXT PRIMARY KEY,
    stage TEXT NOT NULL,  -- 'download', 'transcription', 'diarization'
    file_path TEXT NOT NULL,
    created_at INTEGER NOT NULL,  -- Unix timestamp
    last_accessed INTEGER NOT NULL,
    access_count INTEGER DEFAULT 1,
    file_size_bytes INTEGER NOT NULL,

    -- Stage-specific metadata (JSON)
    audio_hash TEXT,  -- For transcription/diarization stages
    model_size TEXT,  -- For transcription
    speaker_count INTEGER,  -- For diarization
    language TEXT,  -- For transcription
    duration_seconds REAL,

    -- Eviction metadata
    ttl_expires_at INTEGER,  -- Unix timestamp or NULL for no expiration

    INDEX idx_stage_created (stage, created_at),
    INDEX idx_audio_hash (audio_hash),
    INDEX idx_ttl_expires (ttl_expires_at)
);

CREATE TABLE cache_stats (
    date TEXT PRIMARY KEY,  -- YYYY-MM-DD
    hits INTEGER DEFAULT 0,
    misses INTEGER DEFAULT 0,
    evictions INTEGER DEFAULT 0,
    total_size_bytes INTEGER DEFAULT 0
);
```

## Sources

Research findings were informed by the following sources:

### Multi-Stage Pipeline Caching
- [Caching in GitLab CI/CD](https://docs.gitlab.com/ci/caching/) - Cache key strategies and artifact management patterns
- [Pipeline caching - Azure Pipelines](https://learn.microsoft.com/en-us/azure/devops/pipelines/release/caching?view=azure-devops) - Multi-stage cache patterns
- [Architectural patterns to minimize inter-cloud data transfer costs with smart caching layers](https://medium.com/@naeemulhaq/architectural-patterns-to-minimize-inter-cloud-data-transfer-costs-with-smart-caching-layers-e8f5bc7bf719) - Distributed caching architecture

### Idempotency & Cache Keys
- [How to Design Idempotent APIs Safely](https://medium.com/@mathildaduku/how-to-design-idempotent-apis-safely-what-to-cache-and-what-to-ignore-feb93a16fc00) - Idempotency key patterns
- [The Importance of Idempotent Data Pipelines for Resilience](https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience) - Pipeline idempotency patterns
- [Understanding Idempotency in Data Pipelines](https://airbyte.com/data-engineering-resources/idempotency-in-data-pipelines) - Content hash strategies
- [Implementing Idempotency Keys in REST APIs](https://zuplo.com/learning-center/implementing-idempotency-keys-in-rest-apis-a-complete-guide) - Request fingerprinting

### Failure Recovery & Checkpointing
- [Resumable Pipelines - SnapLogic](https://docs-snaplogic.atlassian.net/wiki/spaces/SD/pages/721944618/Resumable+Pipelines) - Resume from failure patterns
- [Local recovery and partial snapshot in distributed stateful stream processing](https://link.springer.com/article/10.1007/s10115-025-02509-z) - Partial failure recovery (2025 research)
- [Checkpoint-Based Recovery for Long-Running Data Transformations](https://dev3lop.com/checkpoint-based-recovery-for-long-running-data-transformations/) - Checkpoint strategies
- [Gemini: Fast failure recovery in distributed training with in-memory checkpoints](https://www.amazon.science/publications/gemini-fast-failure-recovery-in-distributed-training-with-in-memory-checkpoints) - Artifact preservation patterns

### Content-Addressable Storage
- [Content-addressable storage - Wikipedia](https://en.wikipedia.org/wiki/Content-addressable_storage) - CAS fundamentals
- [GitHub - npm/cacache](https://github.com/npm/cacache) - Production CAS implementation
- [LLVM Content Addressable Storage](https://llvm.org/docs/ContentAddressableStorage.html) - Hash-based storage patterns
- [BuildStream Caches](https://docs.buildstream.build/master/arch_caches.html) - SHA256-based artifact storage

### Architecture Patterns
- [Architecture strategies for self-healing and self-preservation - Azure](https://learn.microsoft.com/en-us/azure/well-architected/reliability/self-preservation) - Resilience patterns
- [Google SRE - Data Processing Pipelines](https://sre.google/workbook/data-processing/) - Production pipeline patterns
