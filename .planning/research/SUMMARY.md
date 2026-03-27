# Project Research Summary

**Project:** Cesar v2.4 Idempotent Processing
**Domain:** Offline audio transcription with artifact caching
**Researched:** 2026-02-02
**Confidence:** HIGH

## Executive Summary

Cesar v2.4 adds artifact caching and idempotent processing to a multi-stage audio transcription pipeline (Download → Transcription → Diarization → Formatting). Expert systems in this domain (Docker, npm, ffmpeg) use content-addressable storage with stage-level caching to enable resumption from failure points. The recommended approach extends Cesar's existing SQLite infrastructure rather than introducing new dependencies, using a hybrid storage model: SQLite BLOBs for small artifacts (<100KB) and filesystem for large artifacts (>=100KB).

The architecture centers on a CacheManager component that integrates with the existing TranscriptionOrchestrator, providing transparent caching without breaking backward compatibility. Cache keys use SHA-256 content hashing to ensure deterministic lookup, while atomic write operations prevent corruption during failures. For URL-based sources, time-step functions (15-minute windows) balance freshness with cache efficiency.

Critical risks center on cache corruption from partial writes, stale content from URLs, and concurrent access race conditions. Prevention requires atomic file operations (temp-then-rename pattern), file-based locking for concurrent writes, and careful cache invalidation strategies. Testing must include failure injection (kill signals, disk exhaustion) to validate resilience patterns.

## Key Findings

### Recommended Stack

Research revealed that extending Cesar's existing SQLite (aiosqlite) infrastructure is superior to introducing new caching libraries. SQLite is 35% faster than filesystem storage for small BLOBs (<100KB), handles concurrent access via WAL mode, and integrates seamlessly with existing job persistence patterns. The hybrid approach leverages both SQLite and filesystem storage, choosing the optimal storage backend based on artifact size.

**Core technologies:**
- **aiosqlite 0.22.0+** (existing): Cache metadata and small artifacts — already in stack, proven reliable, 35% faster than filesystem for small BLOBs
- **stdlib hashlib** (built-in): SHA-256 content hashing — zero dependencies, formally verified HACL* implementation, excellent performance
- **stdlib pathlib/tempfile** (built-in): Cache directory management and atomic writes — cross-platform, type-safe, native atomic operations via os.replace()
- **filelock 3.20.3** (optional): Cross-platform file locking for concurrent writes — defer until needed, SQLite WAL handles read concurrency

**Total new dependencies: 0** for MVP (uses stdlib + existing aiosqlite). Optional filelock only if concurrent writes to filesystem artifacts become necessary.

### Expected Features

Caching in CLI tools follows predictable patterns established by Docker, npm, pip, and other developer tools. Users expect transparent caching with manual override capabilities, automatic cache directory creation, and reasonable defaults for cache expiration and size management.

**Must have (table stakes):**
- Skip reprocessing identical inputs — hash-based cache keys prevent redundant work
- --no-cache flag — universal override pattern users expect
- Cache location visibility — users need to know where cache lives for manual cleanup
- Automatic cache directory creation — user shouldn't create ~/.cache/cesar/ manually
- Cache survives crashes — atomic writes ensure cache integrity after failures
- Reasonable cache expiration — URL content changes over time, needs time-step function

**Should have (competitive):**
- --cache-info flag — inspect cache without side effects (location, size, hit/miss stats)
- Resume from failure point — save minutes on retry by skipping successful stages
- Time-step function for URLs — smart freshness with 15-minute windows, not second-level precision
- Smart extension correction — auto-fix .txt to .md when diarize=True (already implemented in v2.2)
- Verbose logging — cache hit/miss visibility for debugging

**Defer (v2+):**
- cesar cache clean — manual cache purge command (users can delete ~/.cache/cesar/ manually)
- --invalidate-stage — granular invalidation (--no-cache covers 80% of use cases)
- cesar cache warm — pre-download models (models auto-download on first use already)
- --dry-run — show cache behavior without execution (debugging feature, not core)
- LRU eviction — automatic cache size management (complexity, manual cleanup sufficient for v2.4)

### Architecture Approach

The recommended architecture introduces a CacheManager component that integrates with the existing TranscriptionOrchestrator while maintaining backward compatibility. The orchestrator checks cache before each expensive pipeline stage (transcription, diarization), uses cached results when available, and stores successful outputs for future use. This preserves Cesar's existing graceful degradation patterns (diarization failure falls back to cached transcription).

**Major components:**
1. **CacheManager** — content-addressable storage with hybrid backend (SQLite + filesystem), SHA-256 key generation, atomic write operations, and cache metadata tracking
2. **TranscriptionOrchestrator (modified)** — accepts optional cache_manager parameter, checks cache before each stage, stores successful outputs, preserves existing behavior when cache_manager is None
3. **BackgroundWorker (modified)** — passes cache_manager to orchestrator, handles retry scenarios with cache invalidation, tracks cache usage metrics in job metadata
4. **Cache Repository** — extends existing JobRepository patterns, shares database file (~/.local/share/cesar/jobs.db), follows established aiosqlite async/await patterns

**Storage structure:**
```
~/.cache/cesar/artifacts/
  ├── transcription/{hash[:2]}/{hash}.json  (SQLite BLOB if <100KB)
  ├── diarization/{hash[:2]}/{hash}.json    (SQLite BLOB if <100KB)
  └── audio/{hash[:2]}/{hash}.m4a           (filesystem, always >100KB)

~/.local/share/cesar/jobs.db
  └── cache_entries table (metadata for all cached artifacts)
```

### Critical Pitfalls

Research identified 11 pitfalls from production systems (yt-dlp, ffmpeg, pip), with 5 rated as critical.

1. **Cache corruption from partial writes** — System crashes during cache write leave partial/corrupted files that appear valid but contain invalid data. Prevention: write-to-temp-then-rename pattern using stdlib os.replace() for atomic operations, validate before caching, cleanup orphaned .tmp files on startup.

2. **Cache invalidation failures (stale URL content)** — YouTube videos updated/replaced but cache returns old transcription because URL-based keys don't detect content changes. Prevention: time-step function for URLs (15-minute buckets), HTTP conditional requests (ETag/Last-Modified), configurable TTL defaults (24 hours for URLs, infinite for local files).

3. **Concurrent access race conditions** — Multiple API requests for same URL run simultaneously, all check cache (miss), all start download, all write to same cache key causing corruption. Prevention: file-based locking with filelock library (timeout + fallback), in-process request coalescing for single-instance API, cache directory sharding to reduce contention.

4. **Disk space exhaustion** — Cache grows unbounded until disk fills, system crashes, user confusion about hidden cache. Prevention: size-based eviction (10GB default limit), LRU eviction when exceeding threshold, cleanup commands (cesar cache info/clean), aggressive temp file deletion.

5. **Hash collision in cache keys** — Different inputs hash to same cache key, wrong transcription returned. Prevention: use SHA-256 (not MD5), never truncate hashes (use full 64 hex chars), include input type in cache key namespace, validate cache metadata on read.

## Implications for Roadmap

Based on research, suggested phase structure follows dependency ordering: foundation before operations, basic operations before intermediate artifacts, intermediate artifacts before resume functionality, advanced features build on working cache.

### Phase 1: Cache Foundation
**Rationale:** Core infrastructure must exist before any caching operations. Atomic writes and content hashing are table stakes that prevent corruption from day one.

**Delivers:**
- CacheManager class with SHA-256 key generation
- Hybrid storage decision logic (SQLite vs filesystem based on size)
- Atomic write operations (temp-then-rename pattern)
- Cache directory structure (~/.cache/cesar/artifacts/)
- Cache metadata schema in SQLite

**Addresses:**
- Must-have: automatic cache directory creation, cache survives crashes
- Pitfall 1 (cache corruption): atomic writes prevent partial file corruption
- Pitfall 5 (hash collisions): SHA-256 with full hashes guarantees uniqueness

**Avoids:**
- Pitfall 1: Implementation includes atomic write-to-temp-then-rename from start
- Pitfall 5: Use SHA-256, never MD5 or truncated hashes

**Research flag:** Standard patterns (well-documented content-addressable storage, skip deep research)

### Phase 2: Orchestrator Integration
**Rationale:** Cache infrastructure useless without pipeline integration. Transcription caching delivers immediate value (saves 2-5 minutes on cache hit).

**Delivers:**
- TranscriptionOrchestrator accepts optional cache_manager parameter
- Transcription stage caching (check cache, use if hit, store on success)
- Diarization stage caching (separate cache key, preserves transcription on failure)
- keep_intermediate flag integration (already exists in v2.4)

**Uses:**
- CacheManager from Phase 1
- Existing WhisperXPipeline and AudioTranscriber interfaces
- Existing fallback patterns (diarization failure preserves cached transcription)

**Implements:**
- Stage-level cache keys (hash of audio + model_size for transcription, hash of audio + speakers for diarization)
- Partial failure artifact preservation (cache transcription immediately, attempt diarization, fallback if fails)

**Addresses:**
- Must-have: skip reprocessing identical inputs
- Should-have: resume from failure point

**Avoids:**
- Pitfall 8 (incomplete metadata): include all processing options in cache key

**Research flag:** Standard patterns (pipeline caching well-documented in GitLab CI/CD, Azure Pipelines)

### Phase 3: CLI Cache Controls
**Rationale:** Users need visibility and control over caching. Without --no-cache flag, users trapped with stale results. Without --cache-info, cache is invisible.

**Delivers:**
- --no-cache flag (force reprocess, bypass cache)
- --cache-info flag (show cache location, size, hit/miss stats)
- Verbose logging of cache hits/misses
- Cache location documentation in README

**Addresses:**
- Must-have: --no-cache flag, cache location visibility
- Should-have: --cache-info flag, verbose logging

**Avoids:**
- Pitfall 10 (poor observability): users know cache exists and how to manage it
- Pitfall 11 (no override): --no-cache provides escape hatch

**Research flag:** Standard patterns (Docker --no-cache, npm cache verify, pip cache info)

### Phase 4: URL Freshness and Expiration
**Rationale:** URL content changes over time. Without expiration, users get stale transcriptions. Time-step function balances freshness with cache efficiency.

**Delivers:**
- Time-step function for URLs (15-minute buckets by default)
- Configurable cache TTL (default: 24 hours for URLs, infinite for local files)
- HTTP conditional requests (ETag/Last-Modified checking)
- YouTube-specific metadata validation

**Uses:**
- Cache metadata schema from Phase 1
- Existing YouTubeHandler for download orchestration

**Addresses:**
- Must-have: reasonable cache expiration for URLs

**Avoids:**
- Pitfall 2 (stale URL content): time-step function + HTTP conditional requests
- Anti-feature: per-second cache freshness causes cache thrashing

**Research flag:** Needs research (HTTP conditional request patterns, YouTube API metadata)

### Phase 5: API Worker Integration
**Rationale:** Background worker processes most transcription jobs. Cache must work seamlessly in async context without blocking event loop.

**Delivers:**
- BackgroundWorker passes cache_manager to orchestrator
- Retry scenarios with cache invalidation (user explicit retry clears cache)
- Job metadata tracking (transcription_cached, diarization_cached, cache_hit_ratio)
- asyncio.to_thread() for cache I/O in async context

**Uses:**
- CacheManager with thread-safe operations
- Existing JobRepository for metadata persistence

**Implements:**
- Cache invalidation on explicit retry (clear all stage caches for job)
- Cache metadata in Job model (optional analytics)

**Addresses:**
- Should-have: cache stats in health endpoint

**Avoids:**
- Pitfall 3 (concurrent access): file-based locking for multi-instance safety
- Anti-pattern: synchronous cache I/O in async context (use asyncio.to_thread)

**Research flag:** Standard patterns (async file I/O well-documented, filelock library examples)

### Phase 6: Concurrent Access and Locking (Optional)
**Rationale:** Only needed if multiple API instances share cache directory. Defer until needed, start with single-instance deployment.

**Delivers:**
- File-based locking with filelock library
- In-memory request coalescing (cache stampede prevention)
- Lock timeout + fallback to reprocess (no deadlocks)
- Cleanup of orphaned lock files on startup

**Uses:**
- filelock 3.20.3 (first new dependency)
- Cache directory structure with .lock files

**Addresses:**
- Should-have: concurrent cache safety for multi-instance API

**Avoids:**
- Pitfall 3 (race conditions): file locking prevents corrupted writes
- Pitfall 6 (cache stampede): request coalescing prevents duplicate work

**Research flag:** Needs research (filelock patterns, distributed locking strategies)

### Phase Ordering Rationale

- **Phase 1 → Phase 2:** Cache infrastructure must exist before orchestrator integration
- **Phase 2 → Phase 3:** Working cache needed before CLI controls are useful
- **Phase 3 → Phase 4:** Basic caching proven before adding URL complexity
- **Phase 4 → Phase 5:** URL freshness logic needed before API worker (most API jobs use URLs)
- **Phase 5 → Phase 6:** Single-instance API proven before multi-instance complexity
- **Grouping:** Foundation (1), Core Features (2-3), Advanced Features (4-6)
- **Pitfall avoidance:** Atomic writes in Phase 1 prevents corruption throughout, URL freshness in Phase 4 prevents stale content before heavy API usage

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4:** HTTP conditional request patterns, ETag/Last-Modified handling, YouTube API metadata
- **Phase 6:** Distributed file locking patterns, cache stampede prevention in distributed systems

Phases with standard patterns (skip research-phase):
- **Phase 1:** Content-addressable storage well-documented (npm/cacache, Git, BuildStream)
- **Phase 2:** Pipeline caching patterns established (GitLab CI/CD, Azure Pipelines, Google SRE)
- **Phase 3:** CLI cache controls universal (Docker, npm, pip)
- **Phase 5:** Async file I/O patterns well-documented (aiosqlite, asyncio.to_thread)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | SQLite performance verified with official benchmarks, hybrid approach proven in npm/cacache |
| Features | HIGH | Feature expectations verified across Docker, npm, pip, yt-dlp, wget, rsync |
| Architecture | HIGH | Content-addressable storage patterns established in Git, npm/cacache, BuildStream |
| Pitfalls | HIGH | All pitfalls verified with real-world evidence from yt-dlp, ffmpeg, pip production issues |

**Overall confidence:** HIGH

Research findings based on official documentation (SQLite benchmarks, Python stdlib docs), production system behavior (Docker, npm, pip), and verified pitfalls from GitHub issues and technical blogs. The hybrid SQLite + filesystem approach is well-established (npm/cacache uses similar pattern). Content-addressable storage patterns are mature (Git, BuildStream, LLVM).

### Gaps to Address

Minor areas requiring validation during implementation:

- **HTTP conditional request implementation:** Pattern is well-documented (MDN, Zuplo), but integration with yt-dlp/requests needs testing. Test with real YouTube URLs to ensure ETag/Last-Modified headers are present.

- **Concurrent write performance:** File locking overhead unknown for Cesar's workload. Start without locking (Phase 1-5), measure concurrent request latency in Phase 6 before deciding on locking strategy.

- **Cache size estimation:** Research suggests 10GB default limit, but actual Cesar usage patterns unknown. Monitor real-world cache growth during early adoption, adjust limit based on telemetry.

- **SQLite BLOB size threshold:** Research suggests 100KB cutoff for SQLite vs filesystem. Validate with real Cesar transcription outputs (typical size: 10-50KB JSON) to confirm threshold is optimal.

All gaps have clear resolution paths (testing, monitoring, tuning) and don't block MVP implementation.

## Sources

### Primary (HIGH confidence)
- [SQLite: 35% Faster Than The Filesystem](https://sqlite.org/fasterthanfs.html) — Performance benchmarks for BLOB storage
- [SQLite: Internal Versus External BLOBs](https://sqlite.org/intern-v-extern-blob.html) — Size threshold guidance (100KB)
- [Python hashlib Documentation](https://docs.python.org/3/library/hashlib.html) — SHA-256 implementation details
- [Python os.replace Function](https://zetcode.com/python/os-replace/) — Atomic file operations
- [Docker Build Cache](https://docs.docker.com/build/cache/) — Cache invalidation patterns
- [pip cache commands](https://pip.pypa.io/en/stable/cli/pip_cache/) — CLI cache management patterns
- [npm cache verify/clean](https://docs.npmjs.com/cli/v8/commands/npm-cache/) — Cache inspection patterns

### Secondary (MEDIUM confidence)
- [GitHub: npm/cacache](https://github.com/npm/cacache) — Content-addressable storage implementation
- [Prefect: Idempotent Data Pipelines](https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience) — Pipeline idempotency patterns
- [yt-dlp Issue #7669](https://github.com/yt-dlp/yt-dlp/issues/7669) — Partial download failures
- [Ben Boyter: Cache Eviction](https://boyter.org/posts/media-clipping-using-ffmpeg-with-cache-eviction-2-random-for-disk-caching-at-scale/) — Production ffmpeg caching
- [Redis: Cache Invalidation](https://redis.io/glossary/cache-invalidation/) — Invalidation strategies
- [GeeksforGeeks: Cache Invalidation Methods](https://www.geeksforgeeks.org/system-design/cache-invalidation-and-the-methods-to-invalidate-cache/) — Time-based, event-driven, version-based patterns
- [Medium: File Conflicts in Multithreaded Python](https://medium.com/@aman.deep291098/avoiding-file-conflicts-in-multithreaded-python-programs-34f2888f4521) — File locking patterns
- [GitLab CI/CD Caching](https://docs.gitlab.com/ci/caching/) — Cache key strategies
- [Azure Pipelines Caching](https://learn.microsoft.com/en-us/azure/devops/pipelines/release/caching?view=azure-devops) — Multi-stage cache patterns

### Tertiary (LOW confidence)
- [Medium: Cache Stampede](https://medium.com/@sonal.sadafal/cache-stampede-the-thundering-herd-problem-d31d579d93fd) — Thundering herd patterns (needs validation with Cesar workload)
- [IOriver: Cache Warming](https://www.ioriver.io/terms/cache-warming) — Preloading strategies (likely not needed for Cesar)

---
*Research completed: 2026-02-02*
*Ready for roadmap: yes*
