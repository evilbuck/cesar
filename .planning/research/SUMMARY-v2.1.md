# Research Summary: v2.1 YouTube Integration

**Project:** Cesar
**Milestone:** v2.1 YouTube Transcription
**Researched:** 2026-01-31
**Confidence:** HIGH

## Executive Summary

YouTube integration is straightforward. yt-dlp (bundled as Python dependency) handles audio extraction, feeding into existing AudioTranscriber. Minimal architecture changes: extend file_handler.py to detect YouTube URLs and route to yt-dlp. FFmpeg is required (system dependency, already documented for ffprobe).

**Key finding:** The existing unified architecture supports YouTube integration cleanly — no refactoring needed.

## Stack Additions

| Component | Version | Purpose |
|-----------|---------|---------|
| **yt-dlp** | `>=2026.1.29` | YouTube audio extraction |
| **FFmpeg** | System binary | Audio format conversion (already required) |

**Installation:**
```toml
# pyproject.toml
dependencies = [
    # ... existing ...
    "yt-dlp>=2026.1.29",
]
```

## Table Stakes Features (v2.1)

| Feature | Complexity |
|---------|------------|
| YouTube URL acceptance (CLI + API) | Low |
| Audio extraction with best quality | Low |
| Progress feedback during download | Medium |
| Clear error messages (invalid URLs, private videos) | Medium |
| Temp file cleanup | Low |

## Differentiators (Defer to v2.2)

- SRT/VTT output formats (timestamps)
- Batch processing (playlists)
- Audio quality selection
- Downloaded audio caching

## Architecture Integration

**Data flow:**
```
YouTube URL → is_youtube_url() → download_youtube_audio() → temp.mp3 → AudioTranscriber.transcribe_file()
```

**Modified components:**
1. `cli.py` — Detect YouTube URL, download before transcription
2. `file_handler.py` — Route YouTube URLs to yt-dlp

**New component:**
- `youtube_handler.py` — yt-dlp integration (sync + async interfaces)

**Unchanged:**
- AudioTranscriber
- BackgroundWorker
- Job persistence

## Critical Pitfalls

| Pitfall | Prevention |
|---------|------------|
| **P1: Temp file leakage** | Cleanup in finally blocks, isolated temp directory |
| **P2: FFmpeg missing** | Check on startup, block YouTube jobs if missing |
| **P3: Rate limiting** | Catch 403/429, return clear error |
| **P4: Exception handling** | Catch all yt-dlp exceptions, log to job |
| **P5: Offline confusion** | Document YouTube requires internet |

## Suggested Phase Structure

| Phase | Focus | Deliverable |
|-------|-------|-------------|
| **6** | Core YouTube Module | youtube_handler.py with yt-dlp integration |
| **7** | CLI + API Integration | YouTube URLs work end-to-end |
| **8** | Error Handling & Docs | Edge cases, README update |

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Audio format | m4a (better quality/size, faster-whisper handles it) |
| CLI command | Accept URLs in existing `transcribe` command |
| Playlists | No — single URLs only for v2.1 |
| Caching | No — download each time for v2.1 |

## Research Files

| File | Content |
|------|---------|
| STACK-YOUTUBE.md | yt-dlp integration details, configuration |
| ARCHITECTURE.md | Integration points, data flow, build order |
| FEATURES.md | Feature categorization (v2.1/research/) |
| PITFALLS-YOUTUBE.md | 14 pitfalls with prevention strategies |

---
*Research complete — Ready for requirements definition*
