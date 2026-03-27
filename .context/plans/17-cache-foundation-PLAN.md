---
phase: 17-cache-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - cesar/cache.py
  - cesar/config.py
  - tests/test_cache.py
autonomous: true

must_haves:
  truths:
    - "Cache directory exists at ~/.cache/cesar/ (XDG-compliant)"
    - "Cache writes are atomic (no partial files from crashes)"
    - "Content is addressable by SHA-256 hash"
    - "Cache survives application crashes without corruption"
    - "YouTube audio downloads can be retrieved from cache by URL"
  artifacts:
    - path: "cesar/cache.py"
      provides: "ContentAddressableCache, CacheEntry, CacheError classes"
      exports: ["ContentAddressableCache", "CacheEntry", "CacheError"]
    - path: "tests/test_cache.py"
      provides: "Unit tests for cache module"
      min_lines: 200
    - path: "cesar/config.py"
      provides: "Updated with cache_dir and cache configuration"
  key_links:
    - from: "cesar/cache.py"
      to: "pathlib.Path"
      via: "File operations"
      pattern: "Path operations for atomic writes"
    - from: "cesar/cache.py"
      to: "hashlib.sha256"
      via: "Content addressing"
      pattern: "hashlib.sha256"
---

<objective>
Create the content-addressable cache foundation for Phase 17: Cache Foundation of v2.4 Idempotent Processing.

Purpose: Enable resumable, cacheable transcription pipelines where intermediate artifacts (starting with YouTube downloads) persist on failure and identical inputs skip reprocessing.

Output: cesar/cache.py module with ContentAddressableCache class implementing:
- XDG-compliant cache directory (~/.cache/cesar/)
- Atomic writes (write-to-temp-then-rename pattern)
- SHA-256 content addressing
- YouTube URL-based lookup with metadata storage
- Cache entry metadata (created_at, content_hash, source_url)

Requirements addressed: CACHE-01, CACHE-02
</objective>

<execution_context>
@/home/buckleyrobinson/.claude/get-shit-done/workflows/execute-plan.md
@/home/buckleyrobinson/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.context/RESEARCH.md
@cesar/config.py  # XDG path patterns and Pydantic model
@cesar/youtube_handler.py  # Integration point for YouTube caching
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create cache module with core classes</name>
  <files>cesar/cache.py</files>
  <action>
Create cesar/cache.py with:

1. **CacheError exception class** for cache-specific errors
   - Inherit from Exception
   - Include optional http_status for API compatibility

2. **CacheEntry dataclass** representing a cached item:
   - `key: str` - The content hash or URL key
   - `path: Path` - Path to cached file
   - `content_hash: str` - SHA-256 hash of content
   - `created_at: datetime` - When entry was created
   - `source_url: Optional[str]` - Original URL (for YouTube downloads)
   - `metadata: Dict[str, Any]` - Additional metadata (file size, etc.)

3. **ContentAddressableCache class**:
   
   **Constructor**:
   - `__init__(self, cache_dir: Optional[Path] = None)`
   - Default cache_dir: ~/.cache/cesar/ (XDG-compliant)
   - Create cache directory on init if it doesn't exist
   - Create subdirectories: `objects/` (for content), `metadata/` (for entry info)
   
   **Core Methods**:
   
   - `get_cache_dir() -> Path`: Return cache directory path
   
   - `_compute_hash(data: bytes) -> str`: Compute SHA-256 hash of data
   
   - `exists(key: str) -> bool`: Check if key exists in cache
   
   - `get(key: str) -> Optional[CacheEntry]`: Retrieve entry by key, return None if not found
   
   - `put(key: str, data: bytes, source_url: Optional[str] = None, metadata: Optional[Dict] = None) -> CacheEntry`:
     * Compute content hash
     * Determine object path: cache_dir/objects/ab/cd/ef... (first 2 chars as subdir to avoid too many files in one dir)
     * Write atomically: write to temp file in same directory, then rename
     * Create metadata JSON file with CacheEntry info
     * Return CacheEntry
   
   - `delete(key: str) -> bool`: Remove entry from cache, return True if existed
   
   - `clear() -> int`: Remove all entries, return count removed
   
   - `list_entries() -> List[CacheEntry]`: Return all cache entries
   
   - `get_size() -> int`: Return total cache size in bytes
   
   **YouTube-Specific Methods**:
   
   - `get_youtube_key(url: str) -> str`: Generate cache key from YouTube URL (normalize URL first)
   
   - `get_by_url(url: str) -> Optional[CacheEntry]`: Look up cached download by URL
   
   - `put_youtube_download(url: str, data: bytes, metadata: Optional[Dict] = None) -> CacheEntry`:
     * Use URL-based key for lookup
     * Store content with hash-based storage
     * Link URL key to content hash in metadata

4. **Helper functions**:
   - `get_default_cache_dir() -> Path`: Return ~/.cache/cesar/
   - `ensure_dir(path: Path) -> None`: Create directory and parents if needed

Follow patterns from cesar/config.py for XDG directory handling.
Use pathlib.Path for all file operations.
Use atomic write pattern: write to temp file, then os.rename (atomic on POSIX).
  </action>
  <verify>
- [ ] CacheError exception can be raised and caught
- [ ] CacheEntry dataclass can be instantiated with all fields
- [ ] ContentAddressableCache creates cache directory on init
- [ ] put() stores data and returns CacheEntry with correct hash
- [ ] get() retrieves existing entry by key
- [ ] exists() returns True for existing keys, False otherwise
- [ ] Atomic write: verify no partial files remain after simulated crash
- [ ] delete() removes entry and returns correct status
- [ ] clear() removes all entries
- [ ] get_size() returns correct total size
- [ ] YouTube URL methods work correctly
  </verify>
</task>

<task type="auto">
  <name>Task 2: Update config module with cache settings</name>
  <files>cesar/config.py</files>
  <action>
Update cesar/config.py to add cache configuration:

1. **Add cache_dir field to CesarConfig**:
   - `cache_dir: Optional[str] = None` - Custom cache directory path
   - If None, use XDG default (~/.cache/cesar/)
   - Use field_validator to validate path is absolute if provided

2. **Add cache configuration to DEFAULT_CONFIG_TEMPLATE**:
   ```toml
   # Cache directory for downloaded audio and intermediate artifacts
   # If not specified, uses XDG standard: ~/.cache/cesar/
   # Default: auto (use XDG)
   # Example: cache_dir = "/mnt/bigdisk/cesar-cache"
   ```

3. **Add helper function**:
   - `get_cache_dir(config: Optional[CesarConfig] = None) -> Path`:
     * If config and config.cache_dir set, use that
     * Otherwise use get_default_cache_dir() -> ~/.cache/cesar/
     * Ensure directory exists before returning

4. **Update imports** if needed for Path type hints.

Follow existing patterns for field validators and default handling.
Maintain backward compatibility (existing configs without cache_dir should work).
  </action>
  <verify>
- [ ] CesarConfig accepts cache_dir field
- [ ] cache_dir=None uses XDG default
- [ ] cache_dir with absolute path is accepted
- [ ] cache_dir with relative path raises validation error
- [ ] DEFAULT_CONFIG_TEMPLATE includes cache documentation
- [ ] get_cache_dir() returns correct path with/without config
- [ ] Existing configs without cache_dir still load successfully
  </verify>
</task>

<task type="auto">
  <name>Task 3: Create comprehensive unit tests</name>
  <files>tests/test_cache.py</files>
  <action>
Create tests/test_cache.py with comprehensive tests:

1. **Test fixtures**:
   - `temp_cache_dir` - pytest fixture providing temporary cache directory
   - `sample_data` - Sample bytes for testing
   - `sample_hash` - Pre-computed SHA-256 hash of sample_data

2. **CacheEntry tests**:
   - Test creation with all fields
   - Test dataclass immutability (frozen=True)

3. **ContentAddressableCache initialization tests**:
   - Test default cache directory creation
   - Test custom cache directory
   - Test directory structure (objects/, metadata/)

4. **Basic operations tests**:
   - `test_put_and_get`: Store and retrieve data
   - `test_exists`: Check existence before and after put
   - `test_get_nonexistent`: Return None for missing keys
   - `test_put_overwrite`: Updating existing key replaces content

5. **Atomic write tests**:
   - `test_atomic_write_no_partial_files`: Simulate crash mid-write, verify no partial files
   - `test_concurrent_writes`: Multiple threads writing same key (should be safe)

6. **Hash-based storage tests**:
   - `test_content_hash_correct`: Verify SHA-256 computation
   - `test_same_content_same_key`: Same data produces same key
   - `test_different_content_different_key`: Different data produces different keys
   - `test_directory_sharding`: Verify first 2 chars used as subdirectory

7. **Deletion tests**:
   - `test_delete_existing`: Remove existing entry
   - `test_delete_nonexistent`: Return False for missing key
   - `test_clear_all`: Remove all entries

8. **Metadata tests**:
   - `test_entry_metadata`: created_at, content_hash, source_url
   - `test_custom_metadata`: Additional metadata storage

9. **YouTube-specific tests**:
   - `test_get_youtube_key_normalization`: URL normalization for consistent keys
   - `test_put_youtube_download`: Store YouTube download
   - `test_get_by_url`: Retrieve by original URL
   - `test_youtube_url_variants`: Different URL formats produce same key

10. **Size calculation tests**:
    - `test_get_size_empty`: Zero for empty cache
    - `test_get_size_with_entries`: Correct sum of all entries

11. **Edge case tests**:
    - `test_empty_data`: Cache empty byte string
    - `test_large_data`: Cache large files (10MB+)
    - `test_special_characters_in_key`: Keys with special characters
    - `test_unicode_content`: Unicode data in metadata

Follow patterns from tests/test_config.py for structure.
Use pytest fixtures and tmp_path for isolation.
Test both success and failure scenarios.
  </action>
  <verify>
- [ ] All test classes have docstrings
- [ ] All test methods have descriptive names
- [ ] Tests cover happy path and error cases
- [ ] Tests use temporary directories (no pollution)
- [ ] Tests can run with: python -m pytest tests/test_cache.py -v
- [ ] Minimum 200 lines of test code
- [ ] All tests pass
  </verify>
</task>

</tasks>

<integration>

## Integration with Existing Code

### youtube_handler.py Integration
The cache module will integrate with youtube_handler.py in Phase 18:

```python
# Future integration (Phase 18):
from cesar.cache import ContentAddressableCache

def download_audio(url: str, cache: Optional[ContentAddressableCache] = None):
    if cache:
        entry = cache.get_by_url(url)
        if entry:
            return entry.path  # Use cached download
    
    # Download fresh
    data = _download_with_yt_dlp(url)
    
    if cache:
        cache.put_youtube_download(url, data)
    
    return path
```

### CLI Integration (Phase 18)
The --no-cache flag will disable caching:

```python
# Future integration (Phase 18):
@click.option('--no-cache', is_flag=True, help='Force reprocessing, bypass cache')
def transcribe(input_path, no_cache):
    cache = None if no_cache else ContentAddressableCache()
    # ... use cache in pipeline
```

### API Integration (Phase 18)
The no_cache parameter will disable caching:

```python
# Future integration (Phase 18):
@app.post("/transcribe")
def transcribe(input_file: UploadFile, no_cache: bool = False):
    cache = None if no_cache else ContentAddressableCache()
    # ... use cache in job processing
```

</integration>

<risks>

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Atomic rename not atomic on Windows | Medium | Low | Use Windows-specific atomic write fallback |
| Hash collisions (SHA-256) | Very Low | Negligible | SHA-256 has 2^256 space, acceptable risk |
| Cache directory permissions | Medium | Medium | Handle PermissionError gracefully, log warning |
| Disk full during write | High | Low | Catch OSError, clean up temp file, raise CacheError |
| Too many files in one directory | Medium | Low | Use 2-char sharding (objects/ab/cd/...) |
| Concurrent access corruption | Medium | Medium | Atomic writes prevent corruption |

</risks>

<verification>

## Verification Checklist

- [ ] CACHE-01: Cache uses XDG-compliant directory (~/.cache/cesar/)
- [ ] CACHE-02: Cache writes are atomic (write-to-temp-then-rename)
- [ ] All unit tests pass (python -m pytest tests/test_cache.py -v)
- [ ] Integration points documented for Phase 18
- [ ] Code follows project style guidelines (see AGENTS.md)
- [ ] Docstrings for all public classes and methods
- [ ] Type hints for all function parameters and return values
- [ ] Error handling follows existing patterns

## Manual Testing

```bash
# Test cache creation
python -c "from cesar.cache import ContentAddressableCache; c = ContentAddressableCache(); print(c.get_cache_dir())"

# Test basic put/get
python -c "
from cesar.cache import ContentAddressableCache
import tempfile
c = ContentAddressableCache()
entry = c.put('test-key', b'hello world')
print(f'Hash: {entry.content_hash}')
retrieved = c.get('test-key')
print(f'Retrieved: {retrieved.path.exists()}')
"

# Test YouTube URL methods
python -c "
from cesar.cache import ContentAddressableCache
c = ContentAddressableCache()
url = 'https://youtube.com/watch?v=dQw4w9WgXcQ'
key = c.get_youtube_key(url)
print(f'YouTube key: {key}')
"
```

</verification>

<references>

## References

- XDG Base Directory Specification: https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
- Atomic file writes: https://alexwlchan.net/2019/03/atomic-cross-filesystem-rename-in-python/
- SHA-256 content addressing: https://en.wikipedia.org/wiki/Content-addressable_storage

</references>
