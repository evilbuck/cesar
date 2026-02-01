# Stack Research: YouTube Integration

**Project:** Cesar - Offline Audio Transcription CLI/API
**Focus:** YouTube audio extraction with yt-dlp
**Researched:** 2026-01-31

---

## Executive Summary

YouTube integration requires adding **yt-dlp** as the primary dependency and **ffmpeg** as a system dependency. The integration is straightforward: yt-dlp downloads audio, existing faster-whisper transcribes it. No architectural changes needed - the async worker pattern already supports blocking I/O operations via `asyncio.to_thread()`.

**Key finding:** Use ThreadPoolExecutor for yt-dlp downloads (network I/O bound), not ProcessPoolExecutor (pickle errors with YoutubeDL objects).

---

## Recommended Stack

### Core Addition: yt-dlp

| Component | Version | Purpose | Rationale |
|-----------|---------|---------|-----------|
| **yt-dlp** | `>=2026.1.29` | YouTube audio extraction | Latest stable (released 2026-01-29). Active maintenance with frequent updates for platform changes. Requires Python 3.10+ which matches project requirement. |

**Installation:**
```bash
pip install "yt-dlp[default]"
```

The `[default]` extras include recommended optional dependencies:
- `certifi` - SSL certificate validation
- `brotli`/`brotlicffi` - Compression support
- `websockets` - Live stream support
- `requests` - Alternative HTTP client

**Why yt-dlp over alternatives:**
- Fork of youtube-dl with active development (youtube-dl is slower to update)
- Built-in audio extraction support via ffmpeg integration
- Supports 1800+ sites beyond YouTube
- Python 3.10+ native (matches project's >=3.10 requirement)
- No breaking changes to API surface - stable embedding interface

### System Dependency: ffmpeg

| Component | Installation | Purpose | Rationale |
|-----------|-------------|---------|-----------|
| **ffmpeg** | System binary | Audio format conversion and extraction | Required by yt-dlp for merging audio streams and converting to usable formats. NOT a Python package - must be installed as system binary. |

**Important:** yt-dlp requires the **ffmpeg binary**, NOT the Python package `ffmpeg-python`. The Python wrapper is insufficient.

**Platform installation:**
```bash
# Linux (Arch)
pacman -S ffmpeg

# Linux (Debian/Ubuntu)
apt install ffmpeg

# macOS
brew install ffmpeg

# Verification
ffmpeg -version
```

**Why ffmpeg is required:**
- YouTube streams video/audio separately; ffmpeg merges them
- Converts downloaded streams to standard audio formats (mp3, m4a, wav)
- yt-dlp cannot function for most use cases without it
- faster-whisper already handles multiple audio formats, so any ffmpeg output works

### Optional: aria2c (Performance Enhancement)

| Component | Installation | Purpose | When to Use |
|-----------|-------------|---------|-------------|
| **aria2c** | System binary (optional) | Parallel segment downloading | For users with slow download speeds or unstable connections. Can improve download speed 2-6x via concurrent fragments. |

**Not recommended for MVP** - adds complexity for marginal gain in typical scenarios. Consider for future optimization milestone.

---

## Integration Points

### 1. Existing Async Worker Pattern (Perfect Fit)

**Current pattern** (from `cesar/api/worker.py`):
```python
# Run transcription in thread pool (blocking operation)
result = await asyncio.to_thread(
    self._run_transcription,
    job.audio_path,
    job.model_size
)
```

**YouTube integration uses same pattern:**
```python
# Download YouTube audio in thread pool (blocking I/O operation)
audio_path = await asyncio.to_thread(
    self._download_youtube_audio,
    youtube_url
)
```

**Why this works:**
- yt-dlp's `YoutubeDL.download()` is synchronous/blocking
- Network I/O bound (not CPU bound)
- `asyncio.to_thread()` already used for faster-whisper (also blocking)
- ThreadPoolExecutor ideal for I/O-bound tasks
- No process pool needed (avoids pickle errors with YoutubeDL objects)

### 2. Database Schema Extension

Existing `Job` model needs URL source support:

**Current:**
```python
audio_path: str  # File path only
```

**Extended:**
```python
audio_path: Optional[str]  # File path (if uploaded)
source_url: Optional[str]   # YouTube URL (if URL-based)
```

**Validation:** Either `audio_path` OR `source_url` must be provided, not both.

### 3. Temporary File Management

**Pattern:**
```python
# Download to temporary location
temp_audio = tempfile.NamedTemporaryFile(suffix='.m4a', delete=False)
ydl_opts = {
    'outtmpl': temp_audio.name,
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
    }],
}

# Download with yt-dlp
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([youtube_url])

# Transcribe (existing flow)
transcriber.transcribe_file(temp_audio.name, output_path)

# Cleanup
Path(temp_audio.name).unlink()
```

**Storage consideration:** Downloaded audio stored temporarily, not persisted. Transcription text is persisted (existing behavior).

### 4. API Endpoint Addition

**New endpoint:**
```
POST /api/v1/transcribe/youtube
{
    "url": "https://youtube.com/watch?v=...",
    "model_size": "base"
}
```

**Reuses existing:**
- Job queue system
- Background worker
- Status polling (`GET /api/v1/jobs/{job_id}`)
- Result retrieval (`GET /api/v1/jobs/{job_id}/text`)

### 5. CLI Extension

**New command:**
```bash
cesar transcribe-youtube <url> -o output.txt --model base
```

OR

**Flag on existing command:**
```bash
cesar transcribe --url <youtube_url> -o output.txt --model base
```

**Validation:** File path and URL are mutually exclusive.

---

## Python API Usage Pattern

### Basic yt-dlp Embedding

```python
import yt_dlp

def download_audio(youtube_url: str, output_path: str) -> dict:
    """Download audio from YouTube URL.

    Returns:
        dict with 'title', 'duration', 'uploader', etc.
    """
    ydl_opts = {
        'outtmpl': output_path,
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        'quiet': True,  # Suppress console output
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        return {
            'title': info.get('title'),
            'duration': info.get('duration'),
            'uploader': info.get('uploader'),
        }
```

### Key Options for Audio-Only Extraction

| Option | Value | Purpose |
|--------|-------|---------|
| `format` | `'bestaudio/best'` | Select highest quality audio stream |
| `postprocessors` | `[{'key': 'FFmpegExtractAudio', ...}]` | Extract audio using ffmpeg |
| `preferredcodec` | `'m4a'` or `'mp3'` | Output format (m4a recommended - better quality/size) |
| `preferredquality` | `'192'` or `'0'` | Bitrate (0 = best available) |
| `outtmpl` | Path string | Output file path template |
| `quiet` | `True` | Suppress console output |

### Progress Tracking (Optional Enhancement)

```python
def progress_hook(d):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', 'N/A')
        print(f"Download progress: {percent}")
    elif d['status'] == 'finished':
        print("Download complete, processing...")

ydl_opts['progress_hooks'] = [progress_hook]
```

---

## What NOT to Add

### 1. DO NOT: ProcessPoolExecutor for yt-dlp

**Why not:**
- YoutubeDL objects contain non-picklable file handles (`_io.TextIOWrapper`)
- ProcessPoolExecutor serializes arguments via pickle
- Results in `TypeError: cannot pickle '_io.TextIOWrapper' object`

**Use instead:** ThreadPoolExecutor (already via `asyncio.to_thread()`)

**Source:** [GitHub Issue #9487](https://github.com/yt-dlp/yt-dlp/issues/9487) documents this limitation.

### 2. DO NOT: ffmpeg-python package

**Why not:**
- yt-dlp requires the **ffmpeg binary executable**, not Python wrapper
- Installing `pip install ffmpeg-python` does NOT satisfy yt-dlp's requirement
- Adds unnecessary dependency that doesn't solve the problem

**Use instead:** System-installed ffmpeg binary (document in README)

### 3. DO NOT: Async wrapper libraries (async-yt-dlp, yt_dlp_async)

**Why not:**
- Third-party wrappers with unknown maintenance status
- yt-dlp's core is synchronous - async wrappers just wrap in executors
- Project already has robust async pattern with `asyncio.to_thread()`
- Adds dependency without benefit

**Use instead:** Direct yt-dlp with existing `asyncio.to_thread()` pattern

### 4. DO NOT: aria2c in initial milestone

**Why not:**
- Optimization, not core functionality
- Requires additional system dependency
- Complicates error handling (aria2c failures)
- Marginal benefit for typical use cases

**Consider later:** As performance optimization milestone after core YouTube functionality proven.

### 5. DO NOT: yt-dlp-ejs dependency

**Why not:**
- Only required for "full YouTube support" with JavaScript execution
- Needs JavaScript runtime (Deno, Node.js, Bun, QuickJS)
- Most audio downloads work without it
- Adds significant complexity

**Monitor:** If users report YouTube download failures, revisit. Otherwise, defer.

---

## Dependencies Summary

### Python Dependencies (Add to pyproject.toml)

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "yt-dlp>=2026.1.29",  # YouTube audio extraction
]
```

**Version rationale:**
- `>=2026.1.29` - Latest stable as of 2026-01-31
- yt-dlp uses calendar versioning (YYYY.MM.DD)
- Frequent releases (multiple per month) to adapt to platform changes
- No semver - breaking changes rare, mostly platform adaptation

### System Dependencies (Document in README)

**Required:**
- ffmpeg (binary) - Audio extraction and format conversion

**Optional:**
- aria2c (binary) - Download performance enhancement (deferred)

### Installation Documentation Template

```markdown
## System Requirements

### ffmpeg (Required)

YouTube transcription requires ffmpeg for audio extraction.

**Linux (Arch):**
```bash
sudo pacman -S ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Verification:**
```bash
ffmpeg -version
```

### Python Dependencies

All Python dependencies install automatically:
```bash
pip install -e .
```
```

---

## Transitive Dependencies

### yt-dlp Pulls In:

Based on `[default]` extras installation:

| Dependency | Purpose | Conflict Risk |
|------------|---------|---------------|
| `certifi` | SSL certificates | **Already in project** (v2025.4.26) - No conflict |
| `brotli` or `brotlicffi` | Compression support | New - No conflict expected |
| `websockets` | Live stream support | New - No conflict expected |
| `requests` | Alternative HTTP client | **Already in project** (v2.32.4) - No conflict |

**Assessment:** No dependency conflicts expected. yt-dlp's dependencies align with project's existing stack.

---

## Error Handling Considerations

### Common Failure Modes

| Error | Cause | Handling |
|-------|-------|----------|
| `ERROR: Unable to download webpage` | Invalid URL or video unavailable | Validate URL pattern, catch and return user-friendly error |
| `ERROR: ffmpeg not found` | ffmpeg not installed | Check for ffmpeg binary at startup, fail fast with setup instructions |
| `ERROR: Unsupported URL` | Non-YouTube URL passed | Validate URL domain, return supported platforms list |
| `ERROR: Video unavailable` | Private/deleted/geo-blocked | Catch, return clear error to user |

### Validation Strategy

**Pre-flight checks:**
1. URL format validation (regex)
2. ffmpeg binary detection (`shutil.which('ffmpeg')`)
3. Supported domain check (youtube.com, youtu.be)

**Download-time handling:**
1. Wrap `ydl.download()` in try/except
2. Map yt-dlp exceptions to HTTP status codes
3. Clean up partial downloads on error

---

## Testing Strategy

### Unit Tests

**Mock yt-dlp:**
```python
from unittest.mock import patch, MagicMock

@patch('yt_dlp.YoutubeDL')
def test_download_youtube_audio(mock_ydl_class):
    mock_ydl = MagicMock()
    mock_ydl_class.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {'title': 'Test Video'}

    # Test download logic
    result = download_audio('https://youtube.com/watch?v=test')
    assert result['title'] == 'Test Video'
```

### Integration Tests

**Requires real ffmpeg:**
```python
import pytest
import shutil

@pytest.mark.skipif(
    shutil.which('ffmpeg') is None,
    reason="ffmpeg not installed"
)
def test_youtube_download_integration():
    # Test with actual yt-dlp download (use stable test video)
    url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" (first YouTube video)
    # ... actual download test
```

### Test Fixtures

**Use stable, short YouTube videos:**
- First YouTube video (11 seconds)
- Creative Commons licensed content
- Public domain material

**Avoid:**
- Copyrighted content
- Videos that may be removed
- Long videos (slow tests)

---

## Configuration Options

### yt-dlp Options to Expose (Future)

| Option | CLI Flag | Purpose | Priority |
|--------|----------|---------|----------|
| Audio format | `--audio-format m4a/mp3/wav` | Output format preference | MVP |
| Quality | `--audio-quality 192/256/320` | Bitrate control | Post-MVP |
| Subtitles | `--download-subtitles` | Get existing transcription | Post-MVP |
| Playlist support | `--playlist` | Batch processing | Future |

**MVP scope:** Auto-detect best audio format, use yt-dlp defaults.

---

## Performance Characteristics

### Download Speed

**Expected:** 1-5 MB/s for typical YouTube audio streams
**Duration:** 5-30 seconds for most videos (depends on length and connection)

**Comparison to transcription:**
- Download: Seconds to ~1 minute
- Transcription: Minutes (depends on audio length, model size)
- Bottleneck: Transcription, not download

**Implication:** No need for aria2c optimization in MVP. Transcription time dominates.

### Resource Usage

**Memory:**
- yt-dlp: Minimal (<100 MB during download)
- Temporary audio file: 1-10 MB per minute of audio
- faster-whisper: 1-8 GB (existing, unchanged)

**Disk:**
- Temporary audio files: Auto-cleanup after transcription
- No persistent storage of YouTube audio (only transcription text)

**Network:**
- Outbound only (download)
- No persistent connections
- Typical usage: 1-10 MB per video (audio-only)

---

## Compatibility Matrix

| Component | Version | Python 3.10 | Python 3.11 | Python 3.12 |
|-----------|---------|-------------|-------------|-------------|
| yt-dlp | 2026.1.29 | ✅ CPython | ✅ CPython, PyPy | ✅ CPython |
| faster-whisper | 1.1.1 | ✅ | ✅ | ✅ |
| FastAPI | 0.109.0+ | ✅ | ✅ | ✅ |

**Assessment:** Full compatibility across supported Python versions (3.10+).

---

## Security Considerations

### URL Validation

**Risk:** Arbitrary URL execution could access internal resources or file:// URLs
**Mitigation:**
- Whitelist allowed domains (youtube.com, youtu.be)
- Reject file://, localhost, internal IP ranges
- Use yt-dlp's built-in URL validation

### ffmpeg Binary Detection

**Risk:** Shell injection if ffmpeg path not validated
**Mitigation:**
- Use `shutil.which('ffmpeg')` for path detection
- No shell=True in subprocess calls
- yt-dlp handles ffmpeg invocation (trusted library)

### Temporary File Cleanup

**Risk:** Disk exhaustion from failed cleanups
**Mitigation:**
- Use context managers for temp files
- Cleanup in finally blocks
- Monitor temp directory size (future)

---

## Rollout Strategy

### Phase 1: Core Integration (This Milestone)

1. Add `yt-dlp>=2026.1.29` to pyproject.toml
2. Document ffmpeg system requirement
3. Implement URL download in worker
4. Add YouTube API endpoint
5. Add CLI command
6. Unit tests with mocked yt-dlp
7. Integration tests with ffmpeg check

### Phase 2: Polish (Future)

1. Progress tracking UI
2. Audio format/quality options
3. Subtitle download
4. Playlist support

### Phase 3: Optimization (Future)

1. aria2c integration
2. Concurrent downloads
3. Download caching

---

## Confidence Assessment

| Area | Confidence | Evidence |
|------|------------|----------|
| **yt-dlp version** | HIGH | Official PyPI page verified, latest stable 2026.1.29 |
| **ffmpeg requirement** | HIGH | Official yt-dlp documentation states explicitly |
| **Async integration** | HIGH | Existing pattern proven, ThreadPoolExecutor documented best practice |
| **Dependency conflicts** | HIGH | All transitive dependencies already in project or new |
| **Python compatibility** | HIGH | yt-dlp 3.10+ matches project's >=3.10 requirement |
| **ProcessPool limitation** | HIGH | GitHub issue #9487 documents pickle error |
| **Performance expectations** | MEDIUM | Based on community reports, not official benchmarks |
| **aria2c benefit** | MEDIUM | Community reports vary (2-6x), depends on connection |

---

## Open Questions for Implementation

1. **Audio format preference:** Default to m4a (better quality/size) or mp3 (universal compatibility)?
   - **Recommendation:** m4a - faster-whisper handles both, m4a is more efficient

2. **Job table extension:** Add `source_url` column or separate `youtube_jobs` table?
   - **Recommendation:** Single column - simpler, same processing flow

3. **CLI command structure:** New subcommand or flag on existing?
   - **Recommendation:** New subcommand - clearer UX, easier to extend

4. **Progress tracking:** Expose yt-dlp progress hooks in MVP?
   - **Recommendation:** Defer to post-MVP - focus on core functionality first

5. **Playlist support:** Should first MVP support playlist URLs?
   - **Recommendation:** No - defer to future milestone, adds complexity

---

## Sources

Research confidence verified with authoritative sources:

- [yt-dlp PyPI Official](https://pypi.org/project/yt-dlp/) - Version, requirements, installation
- [yt-dlp GitHub Official](https://github.com/yt-dlp/yt-dlp) - Documentation, dependencies, API usage
- [yt-dlp Installation Wiki](https://github.com/yt-dlp/yt-dlp/wiki/Installation) - Installation instructions, extras
- [GitHub Issue #9487](https://github.com/yt-dlp/yt-dlp/issues/9487) - ProcessPoolExecutor pickle errors
- [DEV Community - yt-dlp MP3 Tutorial](https://dev.to/_ken0x/downloading-and-converting-youtube-videos-to-mp3-using-yt-dlp-in-python-20c5) - Python API examples
- [ThreadPoolExecutor vs ProcessPoolExecutor Comparison](https://superfastpython.com/threadpoolexecutor-vs-processpoolexecutor/) - Executor best practices
- [How to Use YT-DLP Guide (2026)](https://www.rapidseedbox.com/blog/yt-dlp-complete-guide) - Current best practices

---

**Research Complete - Ready for Roadmap Creation**
