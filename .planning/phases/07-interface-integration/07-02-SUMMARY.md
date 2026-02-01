---
phase: 07
plan: 02
subsystem: api-youtube-integration
tags: [api, youtube, fastapi, health-endpoint, download-progress, status-tracking]

requires:
  - 06-01  # Core YouTube Module (youtube_handler)

provides:
  - YouTube URL support in API /transcribe/url endpoint
  - DOWNLOADING job status for YouTube audio extraction
  - download_progress field (0-100) for job tracking
  - Health endpoint YouTube capability reporting

affects:
  - Future phases needing YouTube status monitoring in API

tech-stack:
  added: []
  patterns:
    - YouTube URL detection and routing in file_handler
    - FFmpeg capability reporting in health endpoint

key-files:
  created:
    - tests/test_file_handler.py
  modified:
    - cesar/api/models.py
    - cesar/api/file_handler.py
    - cesar/api/server.py
    - tests/test_models.py
    - tests/test_server.py

decisions:
  - id: download-progress-field
    what: Add download_progress field (0-100) to Job model
    why: Basic progress indication for YouTube downloads without complex real-time hooks
    alternatives: Real-time progress streaming (deferred - not needed for v2.1)

  - id: downloading-status
    what: Add DOWNLOADING status to JobStatus enum
    why: Separate YouTube audio extraction phase from transcription processing
    alternatives: Use PROCESSING for both (rejected - less visibility)

  - id: health-endpoint-youtube
    what: Report FFmpeg availability in /health endpoint
    why: Enable clients to check YouTube capability before submitting URLs
    alternatives: Let requests fail with 503 (rejected - poor UX)

metrics:
  duration: "3 minutes"
  completed: "2026-02-01"
---

# Phase 7 Plan 02: YouTube API Integration Summary

**One-liner:** YouTube URL support in API with DOWNLOADING status, download_progress tracking, and FFmpeg health reporting

## Objective Achieved

✅ API now accepts YouTube URLs via /transcribe/url endpoint
✅ Job model includes DOWNLOADING status and download_progress field (0-100)
✅ Health endpoint reports FFmpeg availability and YouTube support
✅ Error handling: 503 for missing FFmpeg, 400 for download failures
✅ All 171 project tests pass

## Implementation Details

### Job Model Enhancements

**DOWNLOADING Status:**
- Added to JobStatus enum: `queued -> downloading -> processing -> completed | error`
- Only applies to YouTube URLs (regular uploads skip directly to queued)
- Distinct from PROCESSING to separate download phase from transcription

**download_progress Field:**
- Type: `Optional[int]` with validation (0-100)
- `None`: Non-YouTube jobs (file uploads)
- `0`: YouTube job created, download starting
- `100`: Download complete, ready for transcription
- Basic progress indication without complex real-time streaming

### API Integration

**file_handler.py Changes:**
```python
# YouTube URL detection and routing
if is_youtube_url(url):
    try:
        audio_path = download_youtube_audio(url)
        return str(audio_path)
    except FFmpegNotFoundError as e:
        raise HTTPException(status_code=503, ...)  # Service unavailable
    except YouTubeDownloadError as e:
        raise HTTPException(status_code=400, ...)  # Bad request
```

**Health Endpoint Enhancement:**
```python
@app.get("/health")
async def health():
    ffmpeg_available, ffmpeg_message = check_ffmpeg_available()
    return {
        "status": "healthy",
        "worker": worker_status,
        "youtube": {
            "available": ffmpeg_available,
            "message": "YouTube transcription supported" if ffmpeg_available else ffmpeg_message
        }
    }
```

### Error Handling Strategy

| Error Type | Status Code | Scenario |
|------------|-------------|----------|
| FFmpegNotFoundError | 503 | FFmpeg not installed |
| YouTubeDownloadError | 400 | Video unavailable, rate limited, or download failed |
| Invalid URL | 400 | Non-YouTube URL or malformed URL |

## Testing Coverage

**New Test File:** `tests/test_file_handler.py`
- YouTube URL routing to youtube_handler
- FFmpeg missing returns 503
- Download errors return 400
- Non-YouTube URLs use regular download

**Extended Tests:**
- `tests/test_models.py`: download_progress validation (0-100 range)
- `tests/test_server.py`: Health endpoint YouTube status reporting
- Updated existing tests for 5 JobStatus values (was 4)

**Test Results:**
- ✅ All 171 project tests pass
- ✅ 4 new YouTube file_handler tests
- ✅ 4 new download_progress validation tests
- ✅ 2 new health endpoint YouTube tests

## Code Quality

**Modularity:**
- Clean separation: file_handler imports and delegates to youtube_handler
- No business logic duplication
- Single responsibility maintained

**Validation:**
- Pydantic validates download_progress range (0-100)
- TypeError prevented with Optional[int] type hint
- FFmpeg availability cached with lru_cache

**Error Messages:**
- FFmpeg 503: "YouTube transcription unavailable: FFmpeg not found..."
- Download 400: "YouTube download failed: Video unavailable..."
- Health endpoint: Descriptive messages for troubleshooting

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

**Phase 7 Plan 03 Ready:** Worker YouTube Integration
- Models support DOWNLOADING status ✅
- file_handler routes YouTube URLs ✅
- Health endpoint reports capability ✅

**Remaining for Phase 7:**
- Worker needs to handle YouTube URLs (detect, download, transcribe)
- Worker needs to update job with download_progress
- Integration testing with real YouTube downloads

## Lessons Learned

**Successes:**
- download_progress design: Simple 0/100 semantic works well without complex progress hooks
- Health endpoint enhancement: Enables proactive client capability checking
- Error code strategy: 503 for infrastructure (FFmpeg), 400 for request issues

**For Future:**
- Consider real-time progress streaming for large downloads (v2.2+)
- Worker integration will need download_progress update logic
- May want progress granularity (yt-dlp supports percentage callbacks)

## Verification

**Plan Success Criteria:**
- ✅ JobStatus enum includes DOWNLOADING value
- ✅ Job model includes download_progress field (Optional[int], 0-100, validated)
- ✅ file_handler.download_from_url() routes YouTube URLs to youtube_handler
- ✅ Health endpoint returns youtube.available and youtube.message
- ✅ FFmpeg-not-found returns 503, download errors return 400
- ✅ All unit tests pass including new YouTube tests and download_progress validation

**Files Modified:**
- cesar/api/models.py: +9 lines (DOWNLOADING status, download_progress field)
- cesar/api/file_handler.py: +20 lines (YouTube imports and routing)
- cesar/api/server.py: +5 lines (YouTube health status)
- tests/test_file_handler.py: +78 lines (new file)
- tests/test_models.py: +30 lines (download_progress tests, updated status tests)
- tests/test_server.py: +25 lines (health endpoint YouTube tests)

**Commits:**
```
d397865 feat(07-02): add DOWNLOADING status, download_progress field, and YouTube URL routing
b410f26 feat(07-02): add YouTube capability to health endpoint
6c8ef35 test(07-02): add unit tests for YouTube API support and download_progress
```

## Related Artifacts

- Plan: `.planning/phases/07-interface-integration/07-02-PLAN.md`
- Context: `.planning/phases/07-interface-integration/07-CONTEXT.md`
- Phase 6 Summary: `.planning/phases/06-core-youtube-module/06-01-SUMMARY.md`
