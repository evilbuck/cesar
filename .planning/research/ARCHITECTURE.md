# Architecture Research: YouTube Integration

**Domain:** YouTube URL audio extraction for offline transcription
**Researched:** 2026-01-31
**Confidence:** HIGH (verified with yt-dlp official docs, existing cesar architecture)

## Executive Summary

The YouTube integration extends cesar's existing unified architecture by adding audio extraction from YouTube URLs before transcription. The key insight: **yt-dlp fits cleanly into the existing download flow** already established by POST /transcribe/url. No new components required—only extend the existing file_handler.py module.

Existing architecture already supports:
- CLI calls AudioTranscriber.transcribe_file() directly
- API has POST /transcribe/url that downloads from URL, then worker calls AudioTranscriber.transcribe_file()
- file_handler.py handles URL downloads with download_from_url()

YouTube integration requires:
- Detect YouTube URLs in file_handler.py
- Route YouTube URLs to yt-dlp instead of httpx
- Extract audio to temp file (same interface as download_from_url())
- Rest of flow unchanged (worker processes, AudioTranscriber transcribes)

## Integration Points

### 1. file_handler.py (MODIFY)

**Current responsibility:** Download audio files from generic URLs using httpx

**New responsibility:** Route YouTube URLs to yt-dlp for audio extraction, generic URLs to httpx

**Integration point:**
```python
async def download_from_url(url: str) -> str:
    # NEW: Detect YouTube URL
    if is_youtube_url(url):
        return await download_youtube_audio(url)

    # EXISTING: Generic URL download
    # ... existing httpx code ...
```

### 2. cli.py (MODIFY)

**Current responsibility:** Accept file paths for transcription

**New responsibility:** Also accept YouTube URLs, download audio before transcribing

**Integration point:**
```python
@cli.command(name="transcribe")
@click.argument('input_file', ...)
def transcribe(input_file, ...):
    # NEW: Detect if input_file is YouTube URL
    if is_youtube_url(input_file):
        temp_audio_path = download_youtube_audio_sync(input_file)
        input_file = temp_audio_path

    # EXISTING: transcriber.transcribe_file(input_file, ...)
```

### 3. AudioTranscriber (UNCHANGED)

**Current responsibility:** Transcribe local audio files

**No changes required:** YouTube audio is downloaded to temp file first, then transcribed as normal local file

### 4. BackgroundWorker (UNCHANGED)

**Current responsibility:** Call AudioTranscriber.transcribe_file() with job.audio_path

**No changes required:** file_handler.py already downloads to temp file, worker processes it the same way

### 5. POST /transcribe/url (UNCHANGED)

**Current responsibility:** Download from URL, create job

**No changes required:** file_handler.download_from_url() handles YouTube detection internally

## New Components

### youtube_handler.py (NEW MODULE)

**Purpose:** yt-dlp integration for YouTube audio extraction

**Location:** cesar/api/youtube_handler.py (or cesar/youtube_handler.py if shared by CLI and API)

**Responsibilities:**
- Detect YouTube URLs (youtube.com, youtu.be, m.youtube.com)
- Configure yt-dlp for audio-only download
- Extract audio to temporary file
- Handle yt-dlp errors and timeouts
- Provide sync and async interfaces

**Key functions:**

```python
def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube video URL."""
    # Pattern match youtube.com/watch?v=, youtu.be/, etc.

async def download_youtube_audio(url: str, output_dir: Optional[str] = None) -> str:
    """Download YouTube audio to temp file. Returns path.

    Uses yt-dlp in asyncio.to_thread() to avoid blocking.
    """

def download_youtube_audio_sync(url: str, output_dir: Optional[str] = None) -> str:
    """Synchronous version for CLI use."""
    # Direct yt-dlp call, blocks until complete

def _run_yt_dlp(url: str, output_path: str) -> None:
    """Internal: Configure and run yt-dlp."""
    # YoutubeDL configuration
    # FFmpeg post-processing for audio extraction
```

**yt-dlp configuration:**
```python
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': output_path,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '0',  # Best quality
    }],
    'quiet': True,  # Suppress console output
    'no_warnings': True,
    'extract_flat': False,
}
```

## Data Flow

### YouTube URL → Transcript (CLI)

```
1. User runs: cesar transcribe https://youtube.com/watch?v=abc

2. cli.py detects YouTube URL
   ├─> is_youtube_url(input_file) → True
   └─> download_youtube_audio_sync(url)
       ├─> Create temp file with .mp3 extension
       ├─> Configure yt-dlp options
       ├─> YoutubeDL().download([url])
       ├─> FFmpeg extracts audio to temp.mp3
       └─> Return temp file path

3. cli.py calls AudioTranscriber.transcribe_file(temp.mp3, output.txt)
   └─> Existing flow unchanged

4. Cleanup temp file after transcription
```

### YouTube URL → Transcript (API)

```
1. Client: POST /transcribe/url {"url": "https://youtube.com/watch?v=abc"}

2. server.py calls file_handler.download_from_url(url)
   ├─> is_youtube_url(url) → True
   └─> download_youtube_audio(url)
       ├─> Run in asyncio.to_thread() (non-blocking)
       ├─> Same yt-dlp logic as CLI
       └─> Return temp file path

3. server.py creates Job(audio_path=temp.mp3, ...)
   └─> Returns 202 Accepted

4. BackgroundWorker picks up job
   └─> Calls AudioTranscriber.transcribe_file(temp.mp3, ...)
   └─> Existing flow unchanged

5. Cleanup temp file after job completes (existing file_handler logic)
```

### Component Communication Diagram

```
┌─────────────┐
│ User/Client │
└──────┬──────┘
       │
       │ YouTube URL
       v
┌──────────────────┐      ┌────────────────────┐
│ cli.py           │      │ server.py          │
│ (CLI interface)  │      │ (API interface)    │
└────────┬─────────┘      └─────────┬──────────┘
         │                          │
         │ Both detect YouTube URL  │
         │                          │
         v                          v
┌────────────────────────────────────────────────┐
│ youtube_handler.py                             │
│ ┌────────────────────────────────────────────┐ │
│ │ is_youtube_url()                           │ │
│ │ download_youtube_audio_sync() [for CLI]   │ │
│ │ download_youtube_audio() [for API async]  │ │
│ └────────────────┬───────────────────────────┘ │
│                  │                              │
│                  v                              │
│         ┌────────────────┐                      │
│         │ yt-dlp library │                      │
│         └────────┬───────┘                      │
│                  │                              │
│                  v                              │
│         ┌────────────────┐                      │
│         │ FFmpeg process │                      │
│         └────────┬───────┘                      │
└──────────────────┼────────────────────────────┘
                   │
                   │ Temp audio file (.mp3)
                   v
         ┌──────────────────┐
         │ AudioTranscriber │
         │ (existing, no    │
         │  changes)        │
         └──────────────────┘
```

## Suggested Build Order

### Phase 1: Core YouTube Download Module
**Component:** youtube_handler.py
**Rationale:** Build and test yt-dlp integration in isolation before touching existing code

**Tasks:**
1. Create youtube_handler.py module
2. Implement is_youtube_url() with pattern matching
3. Implement download_youtube_audio_sync() with yt-dlp
4. Test with real YouTube URLs
5. Add error handling (network failures, invalid URLs, age-restricted videos)
6. Write unit tests with mocked yt-dlp

**Validation:** Can download YouTube audio to temp file from Python REPL

---

### Phase 2: CLI Integration
**Component:** cli.py modifications
**Rationale:** CLI is simpler (synchronous), validate flow before async API

**Tasks:**
1. Import youtube_handler in cli.py
2. Add YouTube URL detection in transcribe() command
3. Download audio before validation if YouTube URL
4. Update input_file variable to point to temp file
5. Add cleanup of temp file after transcription
6. Update help text to mention YouTube URL support
7. Test with YouTube URLs in CLI

**Validation:** `cesar transcribe <youtube-url> -o output.txt` works end-to-end

---

### Phase 3: API Integration
**Component:** file_handler.py modifications
**Rationale:** Extend existing download logic with YouTube support

**Tasks:**
1. Import youtube_handler in file_handler.py
2. Add async wrapper for yt-dlp (asyncio.to_thread)
3. Modify download_from_url() to route YouTube URLs
4. Test with POST /transcribe/url and YouTube URLs
5. Verify worker processes YouTube jobs correctly
6. Update API documentation

**Validation:** POST /transcribe/url with YouTube URL creates job that completes successfully

---

### Phase 4: Error Handling & Edge Cases
**Component:** All modified components
**Rationale:** Handle failure modes after happy path works

**Tasks:**
1. Handle age-restricted videos (may require cookies/authentication)
2. Handle private/deleted videos
3. Handle network timeouts during download
4. Handle yt-dlp extraction failures
5. Add progress feedback during download (optional)
6. Update error messages for clarity

**Validation:** Error cases return clear messages, don't crash

---

### Phase 5: Testing & Documentation
**Component:** Tests and user docs
**Rationale:** Ensure reliability and usability

**Tasks:**
1. Write unit tests for youtube_handler
2. Write integration tests for CLI YouTube support
3. Write integration tests for API YouTube support
4. Update README.md with YouTube examples
5. Update docs/architecture.md if needed
6. Add yt-dlp to requirements.txt

**Validation:** All tests pass, documentation accurate

## Technical Decisions

### yt-dlp Configuration Choices

**Format selection:** `'format': 'bestaudio/best'`
- Downloads best audio-only stream if available
- Falls back to best overall quality if no audio-only stream
- Avoids downloading video unnecessarily

**Audio extraction:** FFmpegExtractAudio post-processor
- Extracts audio from video container if needed
- Converts to MP3 for consistency
- Quality '0' = best available

**Output template:** Use tempfile.mkstemp() for controlled temp paths
- Avoids yt-dlp's default naming (includes video title, can have special chars)
- Consistent with existing file_handler.py pattern
- Easy cleanup

### Async vs Sync

**CLI:** Use synchronous download_youtube_audio_sync()
- CLI already blocks for transcription, blocking for download is acceptable
- Simpler implementation, no event loop required

**API:** Use async download_youtube_audio() via asyncio.to_thread()
- Prevents blocking FastAPI event loop
- Consistent with existing async patterns
- yt-dlp download can take 10-60 seconds for long videos

### Error Handling Strategy

**Network failures:** Wrap in try/except, raise HTTPException with 408 timeout or 400 bad request
**Invalid URLs:** Validate before calling yt-dlp, return 400
**Age-restricted:** May fail during download, return 403 with clear message
**Private/deleted:** Return 404 with clear message

### Temp File Management

**Creation:** Use tempfile.mkstemp(suffix='.mp3') for security
**Cleanup:**
- CLI: Delete immediately after transcription completes
- API: Existing worker cleanup logic handles it (temp files deleted after job completes)

**Location:** System temp directory (tempfile module default)

## Architecture Patterns to Follow

### 1. Minimal Surface Area Changes

**Pattern:** Extend file_handler.py, don't refactor existing code
**Rationale:** v2.0 API architecture is stable, minimize risk

### 2. Unified CLI/API Architecture

**Pattern:** Both CLI and API call the same AudioTranscriber.transcribe_file()
**Rationale:** Already established in v2.0, maintain consistency

### 3. Async-Aware but Optional

**Pattern:** Provide both sync and async interfaces in youtube_handler.py
**Rationale:** CLI needs sync, API needs async, don't force async everywhere

### 4. Fail Fast with Clear Errors

**Pattern:** Validate YouTube URLs before starting download
**Rationale:** Better UX, consistent with existing input validation

### 5. Leverage Existing Temp File Patterns

**Pattern:** Use same tempfile approach as file_handler.py
**Rationale:** Consistent cleanup, same security properties

## Integration Risks

### Risk 1: yt-dlp Version Compatibility
**Impact:** YouTube changes API, yt-dlp breaks
**Mitigation:** Pin yt-dlp version in requirements.txt, update periodically
**Detection:** Integration tests with real YouTube URLs

### Risk 2: FFmpeg Dependency
**Impact:** yt-dlp requires FFmpeg for audio extraction, not always installed
**Mitigation:** Document FFmpeg requirement, detect and error early
**Detection:** Check for FFmpeg in PATH before calling yt-dlp

### Risk 3: Long Download Times
**Impact:** Large videos take minutes to download, may hit timeouts
**Mitigation:** Document expected behavior, consider adding download progress
**Detection:** Test with long videos (>1 hour)

### Risk 4: JavaScript Runtime Requirement
**Impact:** yt-dlp now requires external JS runtime (Deno) for some YouTube features
**Mitigation:** Document requirement, test without JS runtime to see if still works for basic cases
**Detection:** Test with various YouTube URLs

## Open Questions for Implementation

1. **Should we support playlists?** No for v2.1 (single URLs only), defer to future
2. **Should we support Vimeo/other platforms?** No for v2.1 (YouTube only), defer to future
3. **Should we cache downloaded audio?** No for v2.1 (download each time), defer to future
4. **Should we show download progress?** Nice to have for v2.1, not blocking
5. **How to handle age-restricted videos?** Document as limitation for v2.1
6. **Should FFmpeg be bundled?** No, document as system requirement (already required for transcriber.get_audio_duration())

---

*Researched: 2026-01-31*

## Sources

- [GitHub - yt-dlp/yt-dlp: A feature-rich command-line audio/video downloader](https://github.com/yt-dlp/yt-dlp)
- [Downloading and Converting YouTube Videos to MP3 using yt-dlp in Python - DEV Community](https://dev.to/_ken0x/downloading-and-converting-youtube-videos-to-mp3-using-yt-dlp-in-python-20c5)
- [yt-dlp · PyPI](https://pypi.org/project/yt-dlp/)
- Cesar existing architecture documentation (/home/buckleyrobinson/projects/cesar/docs/architecture.md)
- Cesar codebase analysis (cli.py, transcriber.py, api/server.py, api/worker.py, api/file_handler.py)
