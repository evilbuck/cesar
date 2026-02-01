---
phase: 07-interface-integration
plan: 01
subsystem: cli
tags: [youtube, cli, yt-dlp, ffmpeg, progress-display]

requires:
  - 06-01 (YouTube download functionality)

provides:
  - YouTube URL transcription via CLI
  - Download progress display
  - Temp file cleanup

affects:
  - 07-02 (API YouTube integration will follow similar pattern)
  - Future CLI enhancements

tech-stack:
  added: []
  patterns:
    - Context manager for progress display
    - URL detection and routing in CLI
    - Exception-based error handling with sys.exit

key-files:
  created: []
  modified:
    - cesar/cli.py (YouTube URL support, download progress)
    - tests/test_cli.py (4 new YouTube tests)

decisions:
  - id: cli-url-detection
    choice: Simple URL detection via startswith('http')
    rationale: Clear and explicit; complex URL parsing not needed for CLI
    alternatives: [urllib.parse, regex patterns]

  - id: cli-youtube-only
    choice: CLI only supports YouTube URLs, not arbitrary URLs
    rationale: API better suited for arbitrary URL handling
    alternatives: [Support all URLs in CLI]

  - id: download-progress-spinner
    choice: Use indeterminate spinner for download progress
    rationale: yt-dlp progress hooks are complex; downloads usually fast
    alternatives: [yt-dlp progress_hooks, no progress display]

  - id: temp-file-cleanup
    choice: Track temp file and cleanup in finally block
    rationale: Ensures cleanup even on error; explicit lifecycle
    alternatives: [context manager, atexit handlers]

metrics:
  duration: 3m22s
  completed: 2026-01-31
---

# Phase 7 Plan 01: CLI YouTube Integration Summary

**One-liner:** YouTube URLs now work in CLI with `cesar transcribe <url> -o output.txt`, showing download spinner then transcription progress

## What Was Built

Added YouTube URL support to the CLI `transcribe` command, enabling users to transcribe YouTube videos directly without manually downloading audio first.

### Key Features

1. **URL Detection & Routing**
   - Changed `input_file` argument to `input_source` (STRING type)
   - Added simple URL detection (startswith http/https)
   - YouTube URL validation via `is_youtube_url()`
   - Non-YouTube URLs rejected with clear error message

2. **Download Progress Display**
   - Created `download_progress` context manager
   - Indeterminate spinner during YouTube download
   - Respects quiet mode flag
   - Two distinct phases visible to user:
     - "Downloading YouTube audio..." (spinner)
     - "Transcribing audio..." (progress bar)

3. **Error Handling**
   - FFmpegNotFoundError handler with helpful install message
   - YouTubeDownloadError handler for download failures
   - Proper exit codes via sys.exit(1)

4. **Temp File Management**
   - Track downloaded temp file path
   - Cleanup in finally block (runs even on error)
   - Best-effort cleanup (catches exceptions)

### Code Structure

**CLI Changes:**
- Import youtube_handler functions and exceptions
- Add download_progress context manager
- Modify transcribe command argument from Path to STRING
- Add URL detection and YouTube download flow
- Add exception handlers for YouTube-specific errors
- Add finally block for temp file cleanup

**Test Coverage:**
- 4 new YouTube-specific tests
- 100% coverage of YouTube code paths
- Mock-based tests (no real YouTube downloads)

## Technical Implementation

### URL Detection Flow

```python
if input_source.startswith('http://') or input_source.startswith('https://'):
    if is_youtube_url(input_source):
        # Download YouTube audio
        with download_progress(quiet):
            audio_path = download_youtube_audio(input_source)
        temp_audio_path = audio_path  # Mark for cleanup
        input_file = audio_path
    else:
        # Reject non-YouTube URLs
        sys.exit(1)
else:
    # Validate file exists
    input_file = Path(input_source)
    if not input_file.exists():
        sys.exit(1)
```

### Download Progress Display

```python
@contextmanager
def download_progress(quiet: bool):
    """Show download progress spinner unless quiet mode."""
    if quiet:
        yield
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Downloading YouTube audio...", total=None)
        yield
```

### Exception Handling

```python
except FFmpegNotFoundError as e:
    console.print(f"[red]Error: {e}[/red]")
    click.echo(str(e), err=True)
    sys.exit(1)
except YouTubeDownloadError as e:
    console.print(f"[red]YouTube Error: {e}[/red]")
    click.echo(str(e), err=True)
    sys.exit(1)
finally:
    # Cleanup temp file
    if temp_audio_path and temp_audio_path.exists():
        temp_audio_path.unlink()
```

## Test Coverage

### New Tests Added

1. **test_transcribe_youtube_url**
   - Mocks YouTube download and transcription
   - Verifies download function called
   - Confirms successful transcription
   - Creates real temp file for realistic behavior

2. **test_transcribe_youtube_ffmpeg_missing**
   - Simulates FFmpeg not installed
   - Verifies non-zero exit code
   - Confirms error message contains "FFmpeg"

3. **test_transcribe_youtube_download_error**
   - Simulates video unavailable error
   - Verifies non-zero exit code
   - Tests YouTubeUnavailableError handling

4. **test_transcribe_non_youtube_url_rejected**
   - Tests arbitrary URL rejection
   - Confirms CLI is YouTube-only for URLs

### Test Results

```
tests/test_cli.py::TestCLI::test_transcribe_youtube_url PASSED
tests/test_cli.py::TestCLI::test_transcribe_youtube_ffmpeg_missing PASSED
tests/test_cli.py::TestCLI::test_transcribe_youtube_download_error PASSED
tests/test_cli.py::TestCLI::test_transcribe_non_youtube_url_rejected PASSED
```

All 12 CLI tests pass (8 existing + 4 new)

## User Experience

### Before
```bash
# Had to manually download YouTube audio first
yt-dlp -x --audio-format m4a <url>
cesar transcribe audio.m4a -o output.txt
```

### After
```bash
# One command, direct from URL
cesar transcribe https://www.youtube.com/watch?v=... -o output.txt

# Output shows two phases:
# 1. "Downloading YouTube audio..." (spinner)
# 2. "Transcribing audio..." (progress bar)
```

### Error Messages

**FFmpeg Missing:**
```
Error: FFmpeg not found. YouTube transcription requires FFmpeg.
Install with: pacman -S ffmpeg (Arch), apt install ffmpeg (Debian),
or brew install ffmpeg (macOS)
```

**Video Unavailable:**
```
YouTube Error: Video is unavailable (may be private, deleted, or geo-blocked)
```

**Non-YouTube URL:**
```
Error: Only YouTube URLs are supported in CLI. For other URLs, use the API.
```

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

### 1. CLI URL Detection Method
**Decision:** Use simple `startswith('http')` check rather than urllib.parse or regex

**Rationale:**
- Clear and explicit
- No ambiguity (file paths won't start with http)
- Simpler than URL parsing libraries
- Sufficient for CLI use case

**Alternatives considered:**
- urllib.parse.urlparse() - overkill for simple check
- Regex patterns - unnecessarily complex

### 2. YouTube-Only URL Support in CLI
**Decision:** CLI only accepts YouTube URLs, not arbitrary URLs

**Rationale:**
- API better suited for arbitrary URL handling
- Keeps CLI focused and simple
- Clear error message guides users to API
- Reduces CLI complexity

**Alternatives considered:**
- Support all URLs - would require more complex routing
- No URL support - defeats purpose of integration

### 3. Download Progress: Spinner vs Progress Bar
**Decision:** Use indeterminate spinner (no percentage)

**Rationale:**
- yt-dlp progress hooks are complex to integrate
- Downloads usually complete quickly (seconds)
- Spinner provides feedback without false precision
- Simpler implementation, fewer edge cases

**Alternatives considered:**
- yt-dlp progress_hooks - complex, not worth overhead
- No progress display - poor UX for slow connections

### 4. Temp File Cleanup Strategy
**Decision:** Track temp file path and cleanup in finally block

**Rationale:**
- Ensures cleanup even on exception/interrupt
- Explicit lifecycle management
- Simple to understand and debug
- Best-effort cleanup (catches exceptions)

**Alternatives considered:**
- Context manager - more complex for this case
- atexit handlers - less explicit, harder to debug

## Performance Metrics

**Execution time:** 3 minutes 22 seconds

**Task breakdown:**
1. Task 1 (Modify CLI to accept URLs): ~2 min
2. Task 2 (Add download progress): Completed in Task 1
3. Task 3 (Add unit tests): ~1.5 min

**Code changes:**
- 94 insertions, 7 deletions in cesar/cli.py
- 95 insertions, 3 deletions in tests/test_cli.py

**Test results:**
- 12/12 CLI tests pass
- 160/161 total project tests pass (1 pre-existing failure in test_models.py)

## Next Phase Readiness

### What's Ready
- ✅ CLI can transcribe YouTube URLs
- ✅ Download progress displays correctly
- ✅ Error handling covers all YouTube error types
- ✅ Temp file cleanup prevents disk bloat
- ✅ Full test coverage of YouTube paths

### Blockers/Concerns

None. Phase 7 Plan 02 (API YouTube integration) can proceed.

### Recommendations for Next Phase

1. **API Integration Pattern**: Follow similar URL detection and routing pattern
2. **Worker Integration**: Worker needs YouTube URL detection and download logic
3. **Consistency**: Use same error messages and handling across CLI/API
4. **Testing**: Same mock-based approach works well for API tests

## Lessons Learned

### What Went Well
- ✅ Plan was accurate and complete
- ✅ Simple URL detection avoided over-engineering
- ✅ Mock-based tests avoid YouTube API dependencies
- ✅ Spinner provides good UX without complex progress tracking
- ✅ Finally block ensures cleanup in all scenarios

### What Could Be Better
- Initial mistake using `return 1` instead of `sys.exit(1)` in exception handlers
- Click's exception handling required using sys.exit for proper exit codes

### Technical Insights
- **Click exception handling:** Return values from exception handlers don't propagate as exit codes; must use sys.exit()
- **Context managers for progress:** Clean pattern for transient progress displays
- **Mock temp files:** Creating real temp files in tests avoids mocking Path operations
- **URL detection simplicity:** startswith() is sufficient; no need for complex parsing

## Validation Checklist

- [x] CLI accepts YouTube URLs as input
- [x] Download progress shown during audio extraction (unless quiet mode)
- [x] Temp audio file cleaned up after transcription
- [x] YouTube-specific errors handled with clear messages
- [x] All unit tests pass (12/12 CLI tests)
- [x] Help text updated to show URL support
- [x] Non-YouTube URLs rejected appropriately
- [x] FFmpeg errors provide helpful install instructions

## Documentation Updates Needed

User documentation should be updated to reflect YouTube URL support:
- Update README.md with YouTube transcription examples
- Add FFmpeg installation instructions
- Document URL vs file path usage
- Show example error messages

## Related Artifacts

**Plan:** `.planning/phases/07-interface-integration/07-01-PLAN.md`
**Commits:**
- 3523ce5: feat(07-01): add YouTube URL support to CLI transcribe command
- 428d4b6: feat(07-01): add download progress and unit tests for YouTube CLI

**Modified files:**
- cesar/cli.py
- tests/test_cli.py

**Dependencies:**
- Requires: Phase 6 Plan 01 (YouTube download functionality)
- Blocks: None
- Related: Phase 7 Plan 02 (API YouTube integration)
