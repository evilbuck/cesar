# Technology Stack: Artifact Caching and Idempotent Processing

**Project:** Cesar v2.4 Idempotent Processing
**Researched:** 2026-02-02
**Confidence:** HIGH

## Executive Summary

For Cesar's artifact caching needs, **extend the existing SQLite infrastructure** rather than introducing new dependencies. Use SQLite for cache metadata and filesystem for artifact storage in a hybrid approach. This leverages existing aiosqlite expertise, provides excellent performance for small-to-medium artifacts, and integrates seamlessly with the current job persistence layer.

**Why this approach:**
1. **Already in the stack:** SQLite (aiosqlite) is battle-tested in this codebase
2. **Superior performance:** SQLite is 35% faster than filesystem for small BLOBs (<100KB)
3. **Hybrid flexibility:** Use SQLite for metadata + filesystem for large artifacts (>100KB)
4. **No new learning curve:** Team already knows aiosqlite patterns
5. **Atomic operations:** SQLite transactions + stdlib provide all needed safety

## Recommended Stack

### Core Caching Infrastructure

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **aiosqlite** | 0.22.0+ (existing) | Cache metadata and small artifacts | Already in stack, proven reliable, 35% faster than filesystem for small BLOBs |
| **stdlib hashlib** | Python 3.10+ (built-in) | Content hashing (SHA-256) | Zero dependencies, formally verified HACL* implementation as of 2025-2026, excellent performance |
| **stdlib pathlib** | Python 3.10+ (built-in) | Cache directory management | Cross-platform, type-safe, idiomatic Python |
| **stdlib tempfile + os.replace()** | Python 3.10+ (built-in) | Atomic file writes | Native atomic operations, no extra dependencies |

### Optional: File Locking (if concurrent writes needed)

| Technology | Version | Purpose | When to Use |
|------------|---------|---------|-------------|
| **filelock** | 3.20.3 | Cross-platform file locking | If multiple workers write to cache concurrently |
| **portalocker** | 3.2.0 | Alternative file locking with Redis support | If distributed locking needed (unlikely for local cache) |

**Recommendation:** Start without file locking. SQLite WAL mode already handles concurrent reads + single writer. Add filelock only if concurrent writes to filesystem artifacts become a bottleneck.

## Hybrid Architecture: SQLite + Filesystem

### Storage Strategy by Artifact Size

```
┌─────────────────────────────────────────────────────────────┐
│                    Cache Storage Decision                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Artifact < 100KB          →  Store in SQLite BLOB         │
│  (transcription text,         - 35% faster access           │
│   diarization segments,       - Atomic with metadata        │
│   alignment data)             - Single file backup          │
│                                                             │
│  Artifact >= 100KB         →  Store in filesystem          │
│  (audio files,                - Path in SQLite metadata     │
│   large JSON outputs)         - Better performance          │
│                               - Avoid DB bloat              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Cache Schema Extension

Add to existing `~/.local/share/cesar/jobs.db`:

```sql
CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key TEXT PRIMARY KEY,           -- SHA-256 of input params
    source_type TEXT NOT NULL,            -- 'file', 'url', 'youtube'
    source_identifier TEXT NOT NULL,      -- file path, URL, or YouTube ID
    artifact_type TEXT NOT NULL,          -- 'transcription', 'diarization', 'alignment', 'audio'
    artifact_size INTEGER NOT NULL,       -- bytes
    artifact_data BLOB,                   -- For artifacts < 100KB
    artifact_path TEXT,                   -- For artifacts >= 100KB
    cache_params TEXT NOT NULL,           -- JSON of model_size, diarize, etc.
    created_at TEXT NOT NULL,
    accessed_at TEXT NOT NULL,
    access_count INTEGER DEFAULT 1,
    expires_at TEXT,                      -- Optional TTL for URLs
    sha256 TEXT NOT NULL                  -- Content hash for verification
);

CREATE INDEX IF NOT EXISTS idx_cache_source ON cache_entries(source_type, source_identifier);
CREATE INDEX IF NOT EXISTS idx_cache_artifact ON cache_entries(artifact_type);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);
CREATE INDEX IF NOT EXISTS idx_cache_accessed ON cache_entries(accessed_at);
```

### Cache Directory Structure

```
~/.cache/cesar/
├── artifacts/
│   ├── audio/
│   │   └── {sha256[:2]}/
│   │       └── {sha256[2:4]}/
│   │           └── {sha256}.mp3
│   ├── transcription/
│   │   └── {sha256[:2]}/
│   │       └── {sha256[2:4]}/
│   │           └── {sha256}.json
│   ├── diarization/
│   │   └── {sha256[:2]}/
│   │       └── {sha256[2:4]}/
│   │           └── {sha256}.json
│   └── alignment/
│       └── {sha256[:2]}/
│           └── {sha256[2:4]}/
│               └── {sha256}.json
└── .lock                              # Optional: global cache lock file
```

**Rationale for nested structure:**
- Avoid directory size limits (ext4: 64K subdirs, but slow after 10K files)
- First 2 chars: 256 top-level directories
- Next 2 chars: 256 subdirectories per top-level
- Result: Max ~390 files per final directory (for 10M cached artifacts)

## Content Hashing Strategy

### Using stdlib hashlib (SHA-256)

**Why SHA-256:**
- Formally verified implementation (HACL*) as of Python 2025-2026
- Zero collision risk for content-addressable storage
- Excellent performance with chunked reading
- Industry standard for integrity verification

**Implementation pattern:**

```python
import hashlib
from pathlib import Path

def hash_file(filepath: Path) -> str:
    """Hash file contents using SHA-256 with chunked reading.

    Handles large files efficiently without loading into memory.
    Uses 8KB chunks per Python best practices 2026.
    """
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):  # 8KB chunks
            hasher.update(chunk)
    return hasher.hexdigest()

def hash_params(**params) -> str:
    """Hash cache key parameters deterministically.

    Converts params to sorted JSON for consistent hashing.
    """
    import json
    canonical = json.dumps(params, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
```

### Cache Key Construction

```python
def build_cache_key(
    source_type: str,
    source_identifier: str,
    artifact_type: str,
    **params
) -> str:
    """Build deterministic cache key.

    Example:
        build_cache_key(
            source_type='youtube',
            source_identifier='dQw4w9WgXcQ',
            artifact_type='transcription',
            model_size='base',
            diarize=True
        )
    """
    components = {
        'source_type': source_type,
        'source_identifier': source_identifier,
        'artifact_type': artifact_type,
        **params
    }
    return hash_params(**components)
```

## Atomic File Operations

### Using stdlib tempfile + os.replace()

**Why stdlib over atomicwrites library:**
- `os.replace()` added in Python 3.3, atomic on all platforms
- No external dependencies
- Simpler than atomicwrites for local filesystem use
- Fully supported in Python 3.10+

**Implementation pattern:**

```python
import os
import tempfile
from pathlib import Path

def atomic_write(target: Path, content: bytes) -> None:
    """Write file atomically using temp + rename.

    Ensures original file never corrupted on failure.
    Uses os.replace() for atomic operation (Python 3.3+).
    """
    target.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory (same filesystem)
    fd, temp_path = tempfile.mkstemp(
        dir=target.parent,
        prefix=f'.{target.name}.',
        suffix='.tmp'
    )
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
        # Atomic replace (POSIX rename, Windows MoveFileEx)
        os.replace(temp_path, target)
    except Exception:
        # Clean up temp file on failure
        Path(temp_path).unlink(missing_ok=True)
        raise
```

**Key guarantees:**
- Temp file in same directory ensures same filesystem (no cross-fs issues)
- `os.replace()` is atomic on POSIX and Windows
- Original file untouched until successful write
- Automatic cleanup on failure

## SQLite Configuration for Caching

### Extend Existing Repository Pattern

Already in codebase (from `cesar/api/repository.py`):

```python
# Already configured in JobRepository.connect():
await connection.execute("PRAGMA journal_mode=WAL;")      # Concurrent reads + single writer
await connection.execute("PRAGMA busy_timeout=5000;")     # 5s retry on lock contention
await connection.execute("PRAGMA synchronous=NORMAL;")    # Balance durability/performance
```

**No changes needed.** Existing settings are optimal for cache workload.

### Cache Repository Class (New)

```python
class CacheRepository:
    """Async repository for artifact cache entries.

    Extends existing SQLite patterns from JobRepository.
    Shares database file: ~/.local/share/cesar/jobs.db
    """

    async def get(self, cache_key: str) -> Optional[CacheEntry]:
        """Retrieve cached artifact by key."""

    async def set(
        self,
        cache_key: str,
        artifact_type: str,
        content: bytes | None = None,
        path: Path | None = None,
        **metadata
    ) -> CacheEntry:
        """Store artifact in cache (BLOB or filesystem)."""

    async def invalidate(self, cache_key: str) -> None:
        """Remove cache entry and associated file."""

    async def prune(self, max_age_days: int = 30) -> int:
        """Remove expired or old entries. Returns count."""
```

## Performance Characteristics

### SQLite BLOB vs Filesystem (Official Benchmarks)

Based on [SQLite official research](https://sqlite.org/fasterthanfs.html) and [internal vs external BLOB guidance](https://sqlite.org/intern-v-extern-blob.html):

| Artifact Size | SQLite BLOB | Filesystem | Recommendation |
|---------------|-------------|------------|----------------|
| < 10KB | **35% faster** | Slower | Use SQLite BLOB |
| 10-100KB | **20% faster** | Slower | Use SQLite BLOB |
| 100KB-1MB | Similar | **Slightly faster** | Use filesystem |
| > 1MB | Slower | **Significantly faster** | Use filesystem |

**Disk usage:** SQLite with 10KB BLOBs uses ~20% less disk space than individual files.

**Cesar artifact size estimates:**
- Transcription text: 1-50KB → **SQLite BLOB**
- Diarization segments: 5-100KB → **SQLite BLOB**
- Alignment data: 10-200KB → **Hybrid (SQLite < 100KB, filesystem ≥ 100KB)**
- Downloaded audio: 1-100MB → **Filesystem**

### Hashing Performance

SHA-256 with 8KB chunks (Python 3.10+ with HACL* implementation):
- **Small files (<1MB):** Sub-millisecond overhead
- **Large files (100MB):** ~100ms on modern CPU
- **Negligible** compared to transcription time (seconds to minutes)

## Alternatives Considered

| Approach | Why Not |
|----------|---------|
| **diskcache library** | Adds dependency for functionality we can build with stdlib + existing SQLite. Not content-addressable by default. Current but doesn't fit our architecture. |
| **hashfs library** | Limited maintenance (last commit unclear), doesn't support Python 3.10+ explicitly. Content-addressable but filesystem-only (loses SQLite benefits for small artifacts). |
| **Pure filesystem cache** | Loses 35% performance advantage for small artifacts. More complex atomicity handling. Harder to query/prune. |
| **Pure SQLite cache** | Would bloat database with large audio files (>1MB). Slower for large artifacts. 2GB BLOB limit. |
| **Redis/external cache** | Overkill for local offline tool. Adds deployment complexity. Cesar philosophy is "works offline, no services". |

## Migration Path

### Phase 1: Metadata + Small Artifacts in SQLite
1. Add `cache_entries` table to existing jobs.db
2. Implement CacheRepository following JobRepository patterns
3. Cache transcription/diarization/alignment outputs (< 100KB) as BLOBs
4. **No filesystem cache yet** (simpler to start)

### Phase 2: Add Filesystem for Large Artifacts
1. Add `~/.cache/cesar/artifacts/` directory structure
2. Implement size threshold logic (100KB cutoff)
3. Cache downloaded audio files to filesystem
4. SQLite stores metadata + path reference

### Phase 3: Advanced Features (Optional)
1. Add TTL support for URL-based caches
2. Implement LRU eviction (track `accessed_at`, `access_count`)
3. Add `--cache-info` CLI command
4. Add cache stats to API health endpoint

## Installation

**No new dependencies required** for MVP (Phase 1-2).

```bash
# Existing dependencies (already in pyproject.toml)
# - aiosqlite>=0.22.0
# - pydantic>=2.0.0

# Python stdlib modules (built-in)
# - hashlib
# - pathlib
# - tempfile
# - os
```

**Optional dependency** (only if concurrent writes needed):

```bash
# If adding file locking later
pip install filelock>=3.20.3
```

## Integration Points with Existing Stack

### Shared Database File

```python
# From cesar/api/database.py
def get_default_db_path() -> Path:
    """Returns: ~/.local/share/cesar/jobs.db"""
    # Cache schema added to same database
    # Shares WAL journal, connection pool
```

### Pydantic Models

```python
# New model in cesar/api/models.py
class CacheEntry(BaseModel):
    cache_key: str
    source_type: Literal['file', 'url', 'youtube']
    artifact_type: Literal['transcription', 'diarization', 'alignment', 'audio']
    artifact_size: int
    artifact_data: Optional[bytes] = None  # For BLOB storage
    artifact_path: Optional[str] = None    # For filesystem storage
    cache_params: dict                     # Serialized as JSON
    created_at: datetime
    accessed_at: datetime
    access_count: int = 1
    expires_at: Optional[datetime] = None
    sha256: str                            # Content verification
```

### Async Patterns

```python
# Follow existing aiosqlite patterns from repository.py
async def get_cached_artifact(cache_key: str) -> Optional[bytes]:
    """Example cache retrieval following JobRepository patterns."""
    repo = CacheRepository(get_default_db_path())
    await repo.connect()
    try:
        entry = await repo.get(cache_key)
        if entry:
            if entry.artifact_data:
                return entry.artifact_data  # SQLite BLOB
            elif entry.artifact_path:
                return Path(entry.artifact_path).read_bytes()  # Filesystem
        return None
    finally:
        await repo.close()
```

## Security Considerations

### Cache Tampering Protection

**Content verification:**
```python
async def verify_cache_entry(entry: CacheEntry) -> bool:
    """Verify cached artifact hasn't been tampered with."""
    if entry.artifact_data:
        actual_hash = hashlib.sha256(entry.artifact_data).hexdigest()
    else:
        actual_hash = hash_file(Path(entry.artifact_path))
    return actual_hash == entry.sha256
```

### Cache Poisoning Prevention

- **Input validation:** Validate source URLs before hashing
- **Path traversal:** Use `pathlib.resolve()` to prevent directory traversal
- **Size limits:** Reject artifacts > reasonable limit (e.g., 500MB)

### Privacy

- **No sensitive data:** Cache contains transcription artifacts, not credentials
- **Local only:** Cache in user home directory, never transmitted
- **Transparent:** User can inspect/delete `~/.cache/cesar/` anytime

## Testing Strategy

### Unit Tests

```python
# tests/test_cache_repository.py
class TestCacheRepository:
    async def test_cache_small_artifact_in_blob()
    async def test_cache_large_artifact_in_filesystem()
    async def test_cache_key_deterministic()
    async def test_cache_hit_returns_same_content()
    async def test_cache_miss_returns_none()
    async def test_prune_removes_expired_entries()
    async def test_atomic_write_on_failure()

# tests/test_hashing.py
class TestContentHashing:
    def test_hash_file_deterministic()
    def test_hash_params_deterministic()
    def test_hash_params_order_independent()
```

### Integration Tests

```python
# tests/test_cache_integration.py
class TestCacheIntegration:
    async def test_transcribe_uses_cache_on_second_run()
    async def test_cache_invalidation_forces_reprocess()
    async def test_cache_survives_process_restart()
```

## Monitoring and Observability

### Cache Metrics (for --cache-info)

```python
class CacheStats(BaseModel):
    total_entries: int
    total_size_bytes: int
    hit_rate: float  # access_count / total_entries
    oldest_entry: datetime
    newest_entry: datetime
    entries_by_type: dict[str, int]
```

### Logging

```python
# Use existing logging patterns
logger.debug(f"Cache hit: {cache_key[:8]}... (artifact_type={artifact_type})")
logger.debug(f"Cache miss: {cache_key[:8]}... (reprocessing)")
logger.info(f"Cache pruned: {removed_count} entries, {freed_bytes} bytes freed")
```

## Summary: Why This Stack

| Criterion | Decision | Rationale |
|-----------|----------|-----------|
| **Cache metadata** | SQLite (aiosqlite) | Already in stack, proven reliable, excellent query capabilities |
| **Small artifacts** | SQLite BLOBs | 35% faster than filesystem, atomic with metadata, single-file backup |
| **Large artifacts** | Filesystem | Better performance, avoid DB bloat |
| **Content hashing** | stdlib hashlib (SHA-256) | Zero dependencies, formally verified, excellent performance |
| **Atomic writes** | stdlib os.replace() | Native atomic operations, no dependencies |
| **File locking** | Defer (use SQLite WAL) | Start simple, add filelock only if needed |
| **Directory structure** | Nested (2-char/2-char/hash) | Avoids filesystem limits, optimal for millions of files |

**Total new dependencies: 0** (MVP uses stdlib + existing aiosqlite)

**Integration effort: Low** (extends existing SQLite patterns, familiar async/await code)

**Performance: Optimal** (hybrid approach uses best tool for each artifact size)

## Sources

### Official Documentation
- [SQLite: 35% Faster Than The Filesystem](https://sqlite.org/fasterthanfs.html)
- [SQLite: Internal Versus External BLOBs](https://sqlite.org/intern-v-extern-blob.html)
- [SQLite: Appropriate Uses For SQLite](https://sqlite.org/whentouse.html)
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html)
- [Python os.replace Function](https://zetcode.com/python/os-replace/)

### Libraries and Tools
- [diskcache · PyPI](https://pypi.org/project/diskcache/)
- [filelock · PyPI](https://pypi.org/project/filelock/)
- [portalocker · PyPI](https://pypi.org/project/portalocker/)
- [GitHub - dgilland/hashfs](https://github.com/dgilland/hashfs)
- [DiskCache Documentation](https://grantjenks.com/docs/diskcache/)

### Best Practices and Benchmarks
- [SQLite is 35% Faster than Filesystem with Small BLOBs | Medium](https://levysoft.medium.com/sqlite-is-35-faster-than-filesystem-with-small-blobs-2974c095d324)
- [charles leifer | Going Fast with SQLite and Python](https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/)
- [How to make data pipelines idempotent – Start Data Engineering](https://www.startdataengineering.com/post/why-how-idempotent-data-pipeline/)
- [The Importance of Idempotent Data Pipelines | Prefect](https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience)
- [Python Hexdigest: Hash Comparison and Best Practices](https://copyprogramming.com/howto/compare-result-from-hexdigest-to-a-string)
- [Better File Writing in Python: Atomic Updates | Medium](https://sahmanish20.medium.com/better-file-writing-in-python-embrace-atomic-updates-593843bfab4f)

### Community Discussions
- [SQLite is 35% Faster Than The Filesystem (2017) | Hacker News](https://news.ycombinator.com/item?id=27897427)
- [A shareable content-addressable wheel artifact cache | Python Discussions](https://discuss.python.org/t/a-shareable-content-addressable-wheel-artifact-cache/13719)
- [Python Concurrency Made Easy: Master FileLock | Medium](https://medium.com/top-python-libraries/python-concurrency-made-easy-master-filelock-for-seamless-file-locking-6ca26dce7493)
