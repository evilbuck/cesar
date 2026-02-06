# Domain Pitfalls: Adding Caching to Multi-Stage Processing Pipelines

**Domain:** Offline audio transcription with multi-stage processing (download → transcode → transcribe → diarize)
**Researched:** 2026-02-02
**Confidence:** HIGH (verified with production systems: ffmpeg, yt-dlp, pip, WhisperX)

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or major production issues.

### Pitfall 1: Cache Corruption from Partial Writes

**What goes wrong:** System crashes during cache write leave partial/corrupted files. On next run, cache appears to exist (key matches) but contains invalid data, causing silent failures or cascading errors downstream.

**Why it happens:**
- Direct file writes are not atomic on most filesystems
- Python's `open().write()` doesn't guarantee atomicity
- Network interruptions during yt-dlp downloads
- OOM kills during transcription

**Real-world evidence:**
- yt-dlp leaves `.part` files on failure that can cause resume issues [GitHub Issue #7669](https://github.com/yt-dlp/yt-dlp/issues/7669)
- pip cache corruption documented as requiring full purge [FasterCapital: PIP Cache](https://fastercapital.com/content/PIP-Cache--Understanding-and-Managing-Package-Caching-in-Python.html)
- ffmpeg pipelines use separate temp files to avoid this [Ben Boyter: Cache Eviction](https://boyter.org/posts/media-clipping-using-ffmpeg-with-cache-eviction-2-random-for-disk-caching-at-scale/)

**Consequences:**
- Silent data corruption (transcription uses partial audio)
- Cascading failures (corrupted transcription fed to diarization)
- User confusion (same input produces different outputs)
- Cache poisoning (bad data persists until manual purge)

**Prevention:**
1. **Write-to-temp-then-rename pattern:**
   ```python
   temp_path = cache_path.with_suffix('.tmp')
   write_data(temp_path)
   temp_path.replace(cache_path)  # Atomic on POSIX
   ```

2. **Validate before caching:**
   - Check file size > 0
   - Verify audio file with ffprobe before caching
   - For transcriptions, validate JSON structure

3. **Cleanup on startup:**
   - Delete all `.tmp` files on startup
   - Validate existing cache entries or mark as suspect

4. **Add cache metadata:**
   ```python
   cache_entry = {
       'data_path': 'audio.m4a',
       'checksum': hashlib.sha256(data).hexdigest(),
       'size': len(data),
       'complete': True  # Only set after atomic rename
   }
   ```

**Detection:**
- Monitor for zero-byte cache files
- Check for orphaned `.tmp` files
- Log cache hit/miss ratio (sudden drops indicate corruption)
- Validate cache entry integrity on read

**Phase implications:**
- Phase 1 (cache implementation) MUST include atomic writes
- Phase 2 (resume from failure) depends on cache integrity
- Testing phase should include kill-signal tests

---

### Pitfall 2: Cache Invalidation Failures (Stale URL Content)

**What goes wrong:** YouTube video is updated/replaced but cache still returns old transcription. User expects fresh content but gets stale results because cache key doesn't account for content changes.

**Why it happens:**
- URL-based cache keys (hash of URL) don't detect content changes
- HTTP Last-Modified/ETag not checked
- Time-based TTL too long or missing
- "Cache forever" assumption for immutable content that isn't actually immutable

**Real-world evidence:**
- Cache invalidation famously called "one of two hard problems in computer science" [Redis: Cache Invalidation](https://redis.io/glossary/cache-invalidation/)
- Cascading cache invalidation problems in production systems [Philip Walton: Cascading Cache Invalidation](https://philipwalton.com/articles/cascading-cache-invalidation/)
- Multiple modern strategies needed (time-based, event-driven, version-based) [GeeksforGeeks: Cache Invalidation](https://www.geeksforgeeks.org/system-design/cache-invalidation-and-the-methods-to-invalidate-cache/)

**Consequences:**
- Stale transcriptions for updated videos
- User confusion ("I changed the video, why is transcription the same?")
- Compliance issues (transcribing deleted/private content from cache)
- Incorrect diarization if speakers change in updated video

**Prevention:**

1. **For URLs, use HTTP conditional requests:**
   ```python
   # Store ETag/Last-Modified in cache metadata
   headers = {'If-None-Match': cached_etag}
   response = requests.head(url, headers=headers)
   if response.status_code == 304:  # Not Modified
       return cached_data
   ```

2. **Time-step function for freshness:**
   ```python
   # Include time bucket in cache key for URLs
   def get_time_bucket(url, bucket_hours=24):
       timestamp = int(time.time())
       bucket = timestamp // (bucket_hours * 3600)
       return hashlib.sha256(f"{url}:{bucket}".encode()).hexdigest()
   ```

3. **YouTube-specific: Use video metadata:**
   - Store upload date, view count, duration in cache metadata
   - Check if video still exists before returning cache
   - Detect "This video is private/deleted" and invalidate cache

4. **Make TTL configurable:**
   - Default: 24 hours for URLs
   - Local files: Cache forever (content-hash based)
   - Add `--max-cache-age` flag for user control

**Detection:**
- Log cache age on hit
- Add `--cache-info` to show cached entry timestamp
- Monitor for deleted YouTube videos returning cached results

**Phase implications:**
- Phase 1: Implement basic TTL for URL caches
- Phase 2: Add HTTP conditional request support
- Phase 3: YouTube-specific metadata validation

---

### Pitfall 3: Concurrent Access Race Conditions

**What goes wrong:** Two API requests for same URL run simultaneously. Both check cache (miss), both start download, both write to same cache key. Result: corrupted cache, wasted resources, potential deadlock.

**Why it happens:**
- No locking mechanism for cache writes
- Async job processing without coordination
- Multiple API instances sharing cache directory
- Background worker and API handler accessing same files

**Real-world evidence:**
- pip concurrent install failures due to race conditions [GitHub Issue #9470](https://github.com/pypa/pip/issues/9470)
- File locking critical for shared resources [Medium: Avoiding File Conflicts](https://medium.com/@aman.deep291098/avoiding-file-conflicts-in-multithreaded-python-programs-34f2888f4521)
- Python's filelock library recommended for reliability [DEV: Importance of Filelock](https://dev.to/noyonict/importance-of-filelock-and-how-to-use-that-in-python-15o4)

**Consequences:**
- Corrupted cache files (two processes writing simultaneously)
- Duplicate downloads (wasting bandwidth, CPU)
- Deadlocks (two processes waiting for each other's lock)
- Resource exhaustion (N duplicate transcriptions of same file)

**Prevention:**

1. **Use file-based locking:**
   ```python
   from filelock import FileLock

   lock_path = cache_path.with_suffix('.lock')
   with FileLock(lock_path, timeout=10):
       if not cache_path.exists():
           download_and_cache(url, cache_path)
   ```

2. **In-memory deduplication for single-process:**
   ```python
   # Track in-progress operations
   in_progress = {}  # {cache_key: asyncio.Event}

   async def get_or_download(url, cache_key):
       if cache_key in in_progress:
           await in_progress[cache_key].wait()
           return read_cache(cache_key)

       event = asyncio.Event()
       in_progress[cache_key] = event
       try:
           data = await download(url)
           write_cache(cache_key, data)
       finally:
           event.set()
           del in_progress[cache_key]
   ```

3. **Cache directory structure to reduce contention:**
   ```
   ~/.cache/cesar/
     downloads/{hash[:2]}/{hash}/audio.m4a
     transcriptions/{hash[:2]}/{hash}/transcript.json
   ```

4. **Always use try-finally for lock cleanup:**
   ```python
   lock = FileLock(lock_path)
   acquired = lock.acquire(timeout=10)
   try:
       # ... cache operations ...
   finally:
       if acquired:
           lock.release()
   ```

**Detection:**
- Monitor for `.lock` files older than expected timeout
- Log duplicate downloads (same URL, overlapping timestamps)
- Check for cache files modified simultaneously (within same second)

**Phase implications:**
- Phase 1: Single-process in-memory deduplication
- Phase 2: File-based locking for multi-instance support
- Testing: Simulate concurrent requests in integration tests

---

### Pitfall 4: Disk Space Exhaustion

**What goes wrong:** Cache grows unbounded until disk fills. System crashes or becomes unusable. Users don't realize cache exists or how to manage it.

**Why it happens:**
- No size limits on cache
- No eviction policy (LRU, random, etc.)
- Large media files (videos can be GB+)
- Multiple pipeline stages (download + transcode = 2x storage)
- No visibility into cache size

**Real-world evidence:**
- ffmpeg production uses "2-random" eviction when disk full [Ben Boyter: Cache Eviction](https://boyter.org/posts/media-clipping-using-ffmpeg-with-cache-eviction-2-random-for-disk-caching-at-scale/)
- pip cache requires manual purging, can fill disk [GeeksforGeeks: pip Clear Cache](https://www.greasyguide.com/linux/pip-clear-cache/)
- ML engineers need regular cleanup guidelines [Medium: Free Up Disk Space](https://medium.com/codenlp/free-up-your-disk-space-regularly-guideline-for-an-ml-engineer-c1a9eb94439b)

**Consequences:**
- System crashes (out of disk space during transcription)
- Failed downloads (no space for temp files)
- Other applications affected (shared filesystem)
- User frustration (hidden cache, no management tools)

**Prevention:**

1. **Implement size-based eviction:**
   ```python
   MAX_CACHE_SIZE = 10 * 1024**3  # 10GB default

   def enforce_cache_limit(cache_dir):
       total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
       if total_size > MAX_CACHE_SIZE:
           # LRU eviction: sort by access time, delete oldest
           files = sorted(cache_dir.rglob('*'), key=lambda f: f.stat().st_atime)
           for f in files:
               if total_size <= MAX_CACHE_SIZE * 0.9:  # 90% threshold
                   break
               total_size -= f.stat().st_size
               f.unlink()
   ```

2. **Add cache management commands:**
   ```bash
   cesar cache info     # Show size, entry count, oldest entry
   cesar cache clear    # Clear all cache
   cesar cache clean    # Remove entries older than N days
   cesar cache limit 5G # Set size limit
   ```

3. **Cleanup temp files aggressively:**
   - Delete downloaded audio after transcription (unless `--keep-audio`)
   - Delete intermediate files (transcoded audio if different from original)
   - Run cleanup on startup (remove orphaned .tmp files)

4. **Warn users proactively:**
   ```
   Cache size: 8.2GB of 10GB limit (82%)
   Consider running `cesar cache clean --days 30` to free space
   ```

**Detection:**
- Log cache size on every write
- Alert when cache exceeds 80% of limit
- Monitor filesystem free space before downloads

**Phase implications:**
- Phase 1: Basic size tracking and warnings
- Phase 2: Automatic eviction (LRU)
- Phase 3: User-facing cache management commands

---

### Pitfall 5: Hash Collision in Cache Keys

**What goes wrong:** Two different inputs hash to same cache key. System returns transcription of File A when user requests File B. Silent data corruption that's hard to detect.

**Why it happens:**
- Weak hash function (MD5 has known collision vulnerabilities)
- Truncated hashes (first 8 chars of hash for filename)
- Hash of metadata instead of content
- Birthday paradox (more likely than intuition suggests)

**Real-world evidence:**
- MD5 collision hazards in cache key filenames [GitHub Advisory GHSA-9j3m-fr7q-jxfw](https://github.com/advisories/GHSA-9j3m-fr7q-jxfw)
- Recommendation: Use SHA-256 instead of MD5 [StartupDefense: Hash Collision Attacks](https://www.startupdefense.io/cyberattacks/hash-collision-attack)
- farmHash recommended for non-cryptographic caching [OpenGenus: Collision Resolution](https://iq.opengenus.org/different-collision-resolution-techniques-in-hashing/)

**Consequences:**
- Wrong transcription returned (User A gets User B's transcript)
- Impossible to debug (appears as logic error, not cache issue)
- Compliance violations (content mixing across users)
- Loss of trust in tool

**Prevention:**

1. **Use strong hash functions:**
   ```python
   # For content hashing (files)
   def content_hash(file_path):
       hasher = hashlib.sha256()
       with open(file_path, 'rb') as f:
           for chunk in iter(lambda: f.read(8192), b''):
               hasher.update(chunk)
       return hasher.hexdigest()

   # For URLs (no collision risk, just uniqueness)
   def url_hash(url):
       return hashlib.sha256(url.encode()).hexdigest()
   ```

2. **Don't truncate hashes:**
   - Use full SHA-256 hash (64 hex chars) in cache key
   - If filesystem limits, use subdirectories: `{hash[:2]}/{hash[2:]}`

3. **Include input type in cache key:**
   ```python
   # Different namespaces for different input types
   cache_key = f"{input_type}:{hash_value}"
   # local_file:abc123...
   # url:def456...
   # youtube:ghi789...
   ```

4. **Validate cache metadata:**
   ```python
   cache_metadata = {
       'cache_key': full_hash,
       'input_source': url,  # Original source for verification
       'input_type': 'youtube',
       'created_at': timestamp,
       'checksum': content_checksum  # Verify against this
   }
   ```

**Detection:**
- Log both cache key and source on cache hit
- Allow user to inspect cache entry source with `--cache-info`
- Add collision counter (would be astronomically rare with SHA-256)

**Phase implications:**
- Phase 1: Use SHA-256 for all cache keys
- Never implement: MD5, truncated hashes, or metadata-only hashing

---

## Moderate Pitfalls

Mistakes that cause delays or technical debt but are recoverable.

### Pitfall 6: Cache Stampede (Thundering Herd)

**What goes wrong:** Popular YouTube video requested by multiple users. First request starts download/transcription. 99 more requests arrive before completion. All 100 requests start duplicate transcriptions because cache miss happened before first completed.

**Why it happens:**
- No coordination between concurrent requests
- Cache-or-compute logic doesn't track in-progress work
- No "waiting for result" state
- High-latency operations (downloading, transcription)

**Real-world evidence:**
- Cache stampede is coordination problem, not caching problem [Medium: Cache Stampede](https://medium.com/@sonal.sadafal/cache-stampede-the-thundering-herd-problem-d31d579d93fd)
- Before slow query completes, hundreds of requests fire duplicate queries [HowTech: Thundering Herd](https://howtech.substack.com/p/thundering-herd-problem-cache-stampede)
- Distributed locking with Redis recommended for prevention [TheTechPlatform: Cache Stampede Prevention](https://www.thetechplatform.com/post/how-to-prevent-cache-stampede-thundering-herd-problems)

**Prevention:**

1. **In-process request coalescing:**
   ```python
   pending_tasks = {}  # {cache_key: asyncio.Task}

   async def get_or_create(cache_key, compute_fn):
       if cache_key in pending_tasks:
           return await pending_tasks[cache_key]

       task = asyncio.create_task(compute_fn())
       pending_tasks[cache_key] = task
       try:
           result = await task
           return result
       finally:
           del pending_tasks[cache_key]
   ```

2. **Probabilistic early expiration:**
   - Instead of hard TTL, compute probability of refresh
   - Reduces simultaneous expiration of popular items

3. **Status tracking in cache metadata:**
   ```python
   cache_status = {
       'COMPUTING': 'In progress, wait and retry',
       'COMPLETE': 'Ready to use',
       'FAILED': 'Computation failed, can retry'
   }
   ```

**Detection:**
- Monitor duplicate transcriptions (same URL, overlapping time)
- Log cache contention (multiple waiters for same key)

**Phase implications:**
- Phase 1: In-process request coalescing for API
- Not needed for CLI (single request at a time)

---

### Pitfall 7: Cold Start Performance Degradation

**What goes wrong:** After cache clear or first run, performance is terrible. Users experience slow responses and wonder if caching helps at all. First-request penalty is unacceptable for interactive use.

**Why it happens:**
- No cache warming strategy
- All requests start cold after deployment
- Batch operations clear then refill cache (worst case)
- No preloading of common models or data

**Real-world evidence:**
- Cache warming preloads known popular items before traffic [IOriver: Cache Warming](https://www.ioriver.io/terms/cache-warming)
- Cold start in serverless/autoscaling environments needs warming [GeeksforGeeks: Cold and Warm Cache](https://www.geeksforgeeks.org/system-design/cold-and-warm-cache-in-system-design/)
- Write-through caching eliminates cold start for new data [Scalable Thread: Cache Warming](https://newsletter.scalablethread.com/p/how-to-optimize-performance-with)

**Prevention:**

1. **Lazy warming on write:**
   - When user requests transcription, cache result immediately
   - Don't wait for expiration to cache

2. **Progressive cache building:**
   - Don't clear entire cache, just oldest entries
   - Graceful degradation vs. cliff edge

3. **Model preloading:**
   ```python
   # Load Whisper model on first request, keep in memory
   # Don't reload on every transcription
   ```

4. **Status visibility:**
   ```
   Cache status: COLD (0 entries)
   First requests will be slower as cache builds
   ```

**Detection:**
- Track cache hit rate over time
- Log cold start events
- Measure first-request latency vs. cached-request latency

**Phase implications:**
- Phase 1: Model preloading (already exists)
- Phase 2: Progressive cache building with LRU eviction
- Not critical: Explicit cache warming (overkill for CLI tool)

---

### Pitfall 8: Incomplete Cache Metadata

**What goes wrong:** Cache entry exists but doesn't record what options were used. User requests transcription with `--diarize`, gets cached result without diarization. Or cached entry doesn't record model size, language, or other parameters.

**Why it happens:**
- Cache key only includes input hash, not processing options
- Assumes one-size-fits-all caching
- Forgets that same input + different options = different output

**Prevention:**

1. **Include options in cache key:**
   ```python
   def cache_key(input_hash, options):
       options_hash = hashlib.sha256(
           json.dumps(options, sort_keys=True).encode()
       ).hexdigest()
       return f"{input_hash}:{options_hash[:8]}"
   ```

2. **Store full context in metadata:**
   ```python
   cache_metadata = {
       'input_source': url,
       'model': 'base',
       'diarize': True,
       'language': 'en',
       'start_time': 0,
       'end_time': 120,
       'whisperx_version': '3.1.1',
       'created_at': timestamp
   }
   ```

3. **Validate options match:**
   - On cache hit, verify cached options match requested options
   - If mismatch, treat as cache miss

**Detection:**
- User reports unexpected output
- `--cache-info` shows mismatched options

**Phase implications:**
- Phase 1: Include all processing options in cache key
- Critical for: --diarize, --model, --start-time, --end-time
- Not needed for: --output (output path doesn't affect transcription)

---

### Pitfall 9: Testing Without Failure Injection

**What goes wrong:** Caching works perfectly in happy-path tests. Production fails immediately due to disk full, process killed, or network interrupted during cache write.

**Why it happens:**
- Unit tests don't simulate crashes
- Integration tests assume infinite resources
- No chaos engineering or failure injection
- "It worked on my machine" syndrome

**Prevention:**

1. **Test cache corruption scenarios:**
   ```python
   def test_partial_write_recovery():
       # Simulate crash during write
       cache_path.write_text("partial")  # No atomic rename

       # Next request should detect and handle
       result = transcribe_with_cache(url)
       assert result.cache_status == "MISS"  # Corrupted cache ignored
       assert cache_path.stat().st_size > 100  # Valid cache now
   ```

2. **Test concurrent access:**
   ```python
   async def test_concurrent_requests():
       tasks = [transcribe_with_cache(url) for _ in range(10)]
       results = await asyncio.gather(*tasks)
       # All should succeed, only one should download
       assert sum(r.cache_status == "MISS" for r in results) == 1
   ```

3. **Test disk space exhaustion:**
   ```python
   def test_cache_eviction_on_full_disk():
       # Fill cache to limit
       for i in range(100):
           cache_large_file(f"file_{i}")

       # Add one more should trigger eviction
       cache_large_file("new_file")
       assert cache_size() <= MAX_CACHE_SIZE
   ```

4. **Use kill signals in tests:**
   ```python
   def test_crash_during_download():
       proc = subprocess.Popen(["cesar", "transcribe", url])
       time.sleep(5)  # Let download start
       proc.kill()  # Simulate crash

       # Restart should cleanup and succeed
       result = subprocess.run(["cesar", "transcribe", url], check=True)
   ```

**Phase implications:**
- Testing phase MUST include failure injection
- Add chaos tests before declaring cache ready for production

---

## Minor Pitfalls

Mistakes that cause annoyance but are easily fixed.

### Pitfall 10: Poor Cache Observability

**What goes wrong:** User doesn't know cache exists, how big it is, or how to manage it. Support requests: "Why is transcription instant now?" or "Where did 10GB go?"

**Prevention:**

1. **Add visibility commands:**
   ```bash
   cesar cache info
   # Cache location: ~/.cache/cesar
   # Total size: 2.3GB (23% of 10GB limit)
   # Entries: 42 (18 downloads, 24 transcriptions)
   # Oldest: 2026-01-15 (18 days ago)
   # Hit rate: 68% (42 hits, 20 misses)

   cesar cache ls
   # abc123  2026-02-01  150MB  https://youtube.com/watch?v=xyz
   # def456  2026-02-02  220MB  /path/to/audio.mp3
   ```

2. **Log cache operations:**
   ```
   [CACHE MISS] youtube:abc123 (downloading)
   [CACHE HIT] youtube:abc123 (saved 45s)
   ```

3. **Document cache location in README**

**Phase implications:**
- Phase 2: Add basic cache info command
- Phase 3: Advanced cache inspection tools

---

### Pitfall 11: Forgetting --no-cache Override

**What goes wrong:** User knows content changed but cache returns stale data. No way to force reprocessing. Workaround requires manual cache deletion.

**Prevention:**

1. **Add --no-cache flag:**
   ```bash
   cesar transcribe video.mp4 --no-cache  # Skip cache read, force reprocess
   ```

2. **Add --refresh flag (check then update):**
   ```bash
   cesar transcribe <url> --refresh  # Check if updated, recache if changed
   ```

**Phase implications:**
- Phase 1: Implement --no-cache flag
- Phase 2: Implement --refresh flag with HTTP conditional requests

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Cache key design | Hash collisions (Pitfall 5) | Use SHA-256, full hashes, include input type |
| Cache write implementation | Partial writes (Pitfall 1) | Atomic write-to-temp-then-rename pattern |
| URL caching | Stale content (Pitfall 2) | Time-step function, HTTP conditional requests |
| API concurrent requests | Race conditions (Pitfall 3) | File locking, in-memory deduplication |
| Cache eviction | Disk space exhaustion (Pitfall 4) | Size limits, LRU eviction, cleanup commands |
| Testing | Missing failure scenarios (Pitfall 9) | Chaos tests, kill signals, disk full simulation |
| Cache metadata | Incomplete context (Pitfall 8) | Include all options in cache key and metadata |
| User experience | Poor observability (Pitfall 10) | Cache info commands, logs, documentation |
| Multi-stage pipeline | Stampede on popular URLs (Pitfall 6) | Request coalescing for API |
| First-run experience | Cold start degradation (Pitfall 7) | Progressive building, don't clear entire cache |
| User control | No cache bypass (Pitfall 11) | --no-cache and --refresh flags |

---

## Research Sources

**Confidence levels:**
- HIGH: Verified with Context7 or official documentation
- MEDIUM: Multiple credible sources agree
- LOW: Single source or unverified

| Finding | Confidence | Source |
|---------|------------|--------|
| Atomic writes prevent corruption | HIGH | [LWN: Atomic Writes](https://lwn.net/Articles/789600/), [MariaDB: Atomic Write Support](https://mariadb.com/kb/en/atomic-write-support/) |
| Cache invalidation strategies | HIGH | [Redis: Cache Invalidation](https://redis.io/glossary/cache-invalidation/), [GeeksforGeeks: Cache Invalidation](https://www.geeksforgeeks.org/system-design/cache-invalidation-and-the-methods-to-invalidate-cache/) |
| File locking for concurrency | HIGH | [Medium: File Conflicts](https://medium.com/@aman.deep291098/avoiding-file-conflicts-in-multithreaded-python-programs-34f2888f4521), [DEV: Filelock](https://dev.to/noyonict/importance-of-filelock-and-how-to-use-that-in-python-15o4) |
| Disk space management patterns | MEDIUM | [Ben Boyter: ffmpeg Caching](https://boyter.org/posts/media-clipping-using-ffmpeg-with-cache-eviction-2-random-for-disk-caching-at-scale/) |
| SHA-256 over MD5 for cache keys | HIGH | [GitHub Advisory GHSA-9j3m-fr7q-jxfw](https://github.com/advisories/GHSA-9j3m-fr7q-jxfw) |
| Cache stampede prevention | MEDIUM | [Medium: Cache Stampede](https://medium.com/@sonal.sadafal/cache-stampede-the-thundering-herd-problem-d31d579d93fd), [HowTech: Thundering Herd](https://howtech.substack.com/p/thundering-herd-problem-cache-stampede) |
| HTTP conditional requests | HIGH | [MDN: Conditional Requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Conditional_requests), [Zuplo: ETags](https://zuplo.com/learning-center/optimizing-rest-apis-with-conditional-requests-and-etags) |
| Cache warming strategies | MEDIUM | [IOriver: Cache Warming](https://www.ioriver.io/terms/cache-warming), [GeeksforGeeks: Cold/Warm Cache](https://www.geeksforgeeks.org/system-design/cold-and-warm-cache-in-system-design/) |
| yt-dlp partial download issues | MEDIUM | [GitHub Issue #7669](https://github.com/yt-dlp/yt-dlp/issues/7669), [GitHub Issue #5463](https://github.com/yt-dlp/yt-dlp/issues/5463) |
| pip cache corruption | MEDIUM | [FasterCapital: PIP Cache](https://fastercapital.com/content/PIP-Cache--Understanding-and-Managing-Package-Caching-in-Python.html) |

---

## Recommended Reading for Implementation

Before implementing cache:

1. **Atomic file operations:** [LWN: A way to do atomic writes](https://lwn.net/Articles/789600/)
2. **Cache invalidation strategies:** [Daily.dev: Cache Invalidation vs Expiration](https://daily.dev/blog/cache-invalidation-vs-expiration-best-practices)
3. **Python file locking:** [DEV: Importance of Filelock](https://dev.to/noyonict/importance-of-filelock-and-how-to-use-that-in-python-15o4)
4. **Production cache eviction:** [Ben Boyter: Cache Eviction 2-Random](https://boyter.org/posts/media-clipping-using-ffmpeg-with-cache-eviction-2-random-for-disk-caching-at-scale/)

---

*Last updated: 2026-02-02*
*Researcher: Claude (GSD Project Researcher)*
