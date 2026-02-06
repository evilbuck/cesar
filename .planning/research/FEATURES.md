# Feature Landscape: Caching and Idempotent Processing

**Domain:** CLI tools with caching and resumable operations
**Researched:** 2026-02-02
**Confidence:** HIGH

## Executive Summary

Caching in CLI tools follows predictable patterns: content-addressable storage, cache inspection commands, force-bypass flags, and granular invalidation. Processing pipelines add resumability (save intermediate artifacts, retry from failure point) and idempotency (same input = same output, regardless of execution count).

**Cesar context:** Multi-stage pipeline (download → transcribe → diarize → format) where each stage is expensive (minutes) and failures mid-pipeline waste prior work. Users expect to skip reprocessing identical inputs and resume from failure points.

## Table Stakes

Features users expect. Missing = product feels broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Skip reprocessing identical inputs** | Docker, npm, pip all do this | Low | Hash-based cache keys (source URL/path + params) |
| **--no-cache flag** | Universal override pattern | Low | Force reprocess even if cached |
| **Cache location visibility** | Users need to clean cache manually | Low | Print location in --cache-info or docs |
| **Automatic cache directory creation** | User shouldn't create ~/.cache/cesar/ | Low | mkdir -p on first use |
| **Cache survives crashes** | Cache exists to survive failures | Low | Atomic writes, temp + rename pattern |
| **Reasonable cache expiration** | URL content changes over time | Medium | Time-step function (15min windows) for URLs |
| **Disk space management** | Caches grow unbounded | Medium | LRU eviction or manual purge command |

### Evidence

**Docker:** `docker build --no-cache` forces rebuild ([Docker Docs](https://docs.docker.com/build/cache/)).

**npm:** `npm cache verify` checks integrity, `npm cache clean --force` purges ([npm Docs](https://docs.npmjs.com/cli/v8/commands/npm-cache/)).

**pip:** `pip cache info`, `pip cache list`, `pip cache purge` commands ([pip v26.0 Docs](https://pip.pypa.io/en/stable/cli/pip_cache/)).

**wget/curl:** `-c` (wget) and `-C -` (curl) for resuming interrupted downloads ([nixCraft wget](https://www.cyberciti.biz/tips/wget-resume-broken-download.html), [curl docs](https://everything.curl.dev/usingcurl/downloads/resume.html)).

**rsync:** `--partial` keeps partial files, `-P` = `--partial --progress` ([rsync guide](https://www.cyberciti.biz/faq/rsync-resume-partially-transferred-downloaded-files-option/)).

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **--cache-info flag** | Inspect what's cached without side effects | Low | Show cache dir, size, hit/miss stats |
| **Resume from failure point** | Save minutes on retry (don't re-transcribe after diarization fails) | Medium | Save intermediate artifacts (transcription.txt, diarization.json) |
| **Granular cache invalidation** | `--invalidate-stage=diarize` forces re-run from that stage | Medium | Stage-level cache keys |
| **Time-step function for URLs** | Smart freshness (15min windows, not second-level precision) | Low | Round timestamp to 15min intervals for URL cache keys |
| **Smart extension correction** | Auto-fix .txt to .md when diarize=True | Low | Warn user, update file path (already implemented in v2.2) |
| **Cache warming** | Pre-download models/artifacts for offline use | Low | `cesar cache warm` downloads Whisper models, diarization models |
| **Dry-run mode** | `--dry-run` shows what would be cached/reused | Low | Useful for debugging cache behavior |

### Evidence

**Build systems:** Make, Ninja, Bazel use target-level caching with incremental rebuilds ([Make optimization](https://moldstud.com/articles/p-master-incremental-builds-ultimate-makefile-optimization-techniques-for-developers)).

**Task queues:** BullMQ supports idempotent jobs with unique identifiers, retry with exponential backoff ([BullMQ patterns](https://docs.bullmq.io/patterns/idempotent-jobs)).

**Content-addressable storage:** npm's cacache uses SRI hashes for content addressing ([npm/cacache](https://github.com/npm/cacache)), Git uses SHA-1 content hashing.

**Checkpoint/resume:** Cloud Run recommends checkpointing partial results to storage for resume ([Google Cloud Run](https://docs.cloud.google.com/run/docs/jobs-retries)).

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Per-second cache freshness for URLs** | Excessive invalidation, cache thrashing | 15-minute time-step windows (rounded timestamps) |
| **Automatic cache cleanup on exit** | User loses cache benefit, unexpected behavior | Explicit `cesar cache clean` command |
| **Cache inside project directory** | Pollutes repo, breaks .gitignore expectations | Use XDG Base Directory (~/.cache/cesar/) |
| **Mandatory cache** | User loses control, no override | Always honor --no-cache flag |
| **Silent cache misses** | User confused why reprocessing | Log cache hit/miss in verbose mode |
| **Cache without version metadata** | Incompatible cache from old Cesar version | Include version in cache key or metadata |
| **Blocking on cache locks** | Concurrent runs deadlock | Timeout + fallback to reprocess |
| **Re-download on every URL transcription** | Wastes bandwidth, user frustration | Cache downloaded files with time-step keys |

### Evidence

**Docker layer caching:** Dependencies change less often than code, so copy package files before source ([Docker best practices](https://docs.docker.com/build/building/best-practices/)).

**yt-dlp resume issues:** Fragmented downloads fail to resume properly with 403 errors ([yt-dlp #14087](https://github.com/yt-dlp/yt-dlp/issues/14087)). Lesson: Resumability requires atomic writes and careful error handling.

**CI/CD cache purging:** Improper cache invalidation causes stale builds ([Datadog blog](https://www.datadoghq.com/blog/cache-purge-ci-cd/)). Lesson: Include dependency fingerprints in cache keys.

## Feature Dependencies

```
Cache Foundation
├── Cache directory creation
├── Content-addressable keys (hash-based)
└── Atomic writes (temp + rename)
    ↓
Basic Cache Operations
├── Cache lookup (key → path)
├── Cache store (key + data → disk)
└── --no-cache flag (bypass cache)
    ↓
Intermediate Artifact Storage
├── Stage-level cache keys (transcribe, diarize, format)
├── Resume from failure point
└── keep_intermediate flag (debug mode, already exists)
    ↓
Advanced Features
├── --cache-info (inspect cache)
├── --invalidate-stage (granular control)
├── Time-step function for URLs
└── Cache warming (cesar cache warm)
```

**Dependency rationale:**
1. Foundation must exist before operations
2. Basic operations enable intermediate artifacts
3. Intermediate artifacts enable resume functionality
4. Advanced features build on working cache

## MVP Recommendation

For MVP (v2.4 Idempotent Processing), prioritize:

### Phase 1: Cache Foundation (must-have)
1. Cache directory at ~/.cache/cesar/ (XDG Base Directory)
2. Content-addressable keys: hash(source_path/url + model_size + diarize + min/max_speakers)
3. Stage-level cache keys (transcription, diarization artifacts)
4. Atomic writes with temp + rename pattern
5. --no-cache flag to force reprocess

### Phase 2: Resumability (must-have)
1. Save transcription.txt after transcribe stage
2. Save diarization.json after diarize stage (WhisperXSegment list)
3. Resume on retry: check cache for prior stages, skip if present
4. Cache lookup in orchestrator before each stage

### Phase 3: Visibility (should-have)
1. --cache-info flag (location, size, hit/miss stats)
2. Verbose logging of cache hits/misses
3. Cache size in health endpoint (API)

### Phase 4: URL Freshness (should-have)
1. Time-step function for URLs (15-minute windows)
2. Include rounded timestamp in URL cache keys
3. Config option for time-step interval (default: 15min)

## Defer to Post-MVP

- **cesar cache clean**: Manual cache purge command
  - Reason: Users can delete ~/.cache/cesar/ manually
- **--invalidate-stage**: Granular invalidation
  - Reason: --no-cache covers 80% of use cases
- **cesar cache warm**: Pre-download models
  - Reason: Models auto-download on first use already
- **--dry-run**: Show cache behavior without execution
  - Reason: Debugging feature, not core functionality
- **LRU eviction**: Automatic cache size management
  - Reason: Complexity, manual cleanup sufficient for v2.4

## Cesar-Specific Integration

### Existing Features That Support Caching

| Feature | How It Helps Caching |
|---------|---------------------|
| keep_intermediate flag (v2.4) | Already saves transcription.txt and diarization.json in debug mode |
| SQLite job queue (v2.0) | Store cache metadata (cache_key, cached_stages) per job |
| OrchestrationResult.diarized (v2.6) | Detect fallback scenarios (transcription cached, diarization failed) |
| PARTIAL status (v2.6) | Retry endpoint already supports resume from failure |
| UUID temp filenames (v2.1) | Collision-free concurrent cache writes |

### Pipeline Stage Mapping

| Stage | Input | Output | Cache Key Components |
|-------|-------|--------|---------------------|
| Download (URLs/YouTube) | URL | audio file | hash(url + time_step) |
| Transcribe | audio file | transcription.txt | hash(audio_path + model_size) |
| Diarize | audio file + transcription | diarization.json | hash(audio_path + min/max_speakers) |
| Format | transcription + diarization | final .md/.txt | hash(inputs + format_options) |

### CLI Cache Flags

```bash
# Force reprocess (bypass cache)
cesar transcribe youtube.com/watch?v=xyz --no-cache

# Inspect cache status
cesar transcribe file.mp3 --cache-info
# Output: Cache hit: transcription (saved 2m 15s), Cache miss: diarization

# Normal operation (use cache if available)
cesar transcribe file.mp3 -o out.md
# Output: Using cached transcription from 2026-02-02 15:30:00
```

### API Cache Parameters

```json
POST /transcribe/url
{
  "url": "https://example.com/audio.mp3",
  "model": "base",
  "diarize": true,
  "use_cache": true,        // default: true
  "cache_ttl_minutes": 15   // URL freshness window
}
```

### Cache Metadata in Job Model

```python
class Job(BaseModel):
    # ... existing fields ...
    cache_key: Optional[str]              # Content-addressable key
    cached_stages: List[str] = []         # ["transcription", "diarization"]
    cache_saved_seconds: Optional[float]  # Time saved by cache hits
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Cache corruption** | Failed jobs, user frustration | Atomic writes (temp + rename), validate on read |
| **Cache size explosion** | Disk space issues | Document manual cleanup, log cache size in --cache-info |
| **Stale URL content** | Outdated transcriptions | Time-step function (15min windows) |
| **Cache key collisions** | Wrong transcription returned | Include all parameters in hash (model, diarize, speakers) |
| **Concurrent access conflicts** | Race conditions, corrupted writes | Use UUID temp filenames, atomic renames |
| **Version incompatibility** | Old cache breaks new Cesar | Include Cesar version in cache metadata, ignore old cache |

## Success Metrics

Cache implementation succeeds when:

1. **Idempotency:** Running same command twice with same input produces identical output in <1s on second run
2. **Resume works:** Retry after diarization failure skips transcription (saves 2-5 minutes)
3. **No false cache hits:** Different inputs never return same cached output
4. **Disk space predictable:** Cache growth rate documented, users can estimate size
5. **Cache visible:** --cache-info shows what's cached, how much space used

## Sources

**Content-addressable caching:**
- [npm/cacache - Content-addressable cache](https://github.com/npm/cacache)
- [Docker Build Cache](https://docs.docker.com/build/cache/)
- [pip cache commands](https://pip.pypa.io/en/stable/cli/pip_cache/)
- [npm cache verify/clean](https://docs.npmjs.com/cli/v8/commands/npm-cache/)

**Resumable operations:**
- [wget resume downloads](https://www.cyberciti.biz/tips/wget-resume-broken-download.html)
- [curl resume with -C flag](https://everything.curl.dev/usingcurl/downloads/resume.html)
- [rsync --partial flag](https://www.cyberciti.biz/faq/rsync-resume-partially-transferred-downloaded-files-option/)

**Idempotent processing:**
- [BullMQ idempotent jobs](https://docs.bullmq.io/patterns/idempotent-jobs)
- [Google Cloud Run retry best practices](https://docs.cloud.google.com/run/docs/jobs-retries)
- [Temporal retry policies](https://docs.temporal.io/encyclopedia/retry-policies)

**Build system caching:**
- [Make incremental builds](https://moldstud.com/articles/p-master-incremental-builds-ultimate-makefile-optimization-techniques-for-developers)
- [Docker layer caching best practices](https://docs.docker.com/build/building/best-practices/)

**Cache invalidation:**
- [Datadog CI/CD cache purging patterns](https://www.datadoghq.com/blog/cache-purge-ci-cd/)
- [Docker build cache invalidation](https://docs.docker.com/build/cache/invalidation/)

**Known issues to avoid:**
- [yt-dlp resume failures with 403](https://github.com/yt-dlp/yt-dlp/issues/14087)
- [ffmpeg corrupt segment caching](https://github.com/blakeblackshear/frigate/issues/6260)
