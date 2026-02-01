# Cesar

## What This Is

An offline audio transcription tool with CLI and HTTP API interfaces that supports YouTube video transcription. Install via `pipx install .` for the CLI (`cesar transcribe`) or run `cesar serve` to start the API server with OpenAPI docs. Accepts local files, URLs, or YouTube links. Works completely offline after initial model download.

## Core Value

Transcribe audio to text anywhere, offline, with a single command or API call — no cloud services, no API keys, no ongoing costs.

## Current State

**Shipped:** v2.1 YouTube Transcription (2026-02-01)
- YouTube URL transcription via CLI and API
- Download progress tracking with DOWNLOADING status
- Granular error handling for YouTube-specific failures
- 38 new files, 211 tests passing

**Previous:** v2.0 API (2026-01-23)
- HTTP API with async job queue via `cesar serve`
- 6 REST endpoints: health, jobs list/get, transcribe (file upload + URL)
- SQLite persistence with job recovery on crash

**Tech stack:** Python 3.10+, Click, Rich, faster-whisper, setuptools, FastAPI, Pydantic v2, aiosqlite, uvicorn, yt-dlp

## Current Milestone: v2.2 Speaker Identification

**Goal:** Add speaker diarization to transcripts with configurable defaults

**Target features:**
- Speaker identification (diarization) for audio transcripts
- Markdown output format with inline speaker labels
- Configuration system for CLI and API defaults
- Works across all input sources (files, URLs, YouTube)
- Offline-first with downloadable models

## Requirements

### Validated

- ✓ Transcribe audio files (mp3, wav, m4a) to text — existing
- ✓ Automatic device detection and optimization (CPU/CUDA/MPS) — existing
- ✓ Multiple Whisper model sizes (tiny/base/small/medium/large) — existing
- ✓ Progress display with Rich formatting — existing
- ✓ Time-limited transcription (--start-time, --end-time, --max-duration) — existing
- ✓ Verbose and quiet output modes — existing
- ✓ Streaming segments for memory efficiency — existing
- ✓ Install via `pipx install .` — v1.0
- ✓ Global `cesar` command available after install — v1.0
- ✓ Subcommand structure: `cesar transcribe <file>` — v1.0
- ✓ `cesar --version` shows correct version — v1.0
- ✓ `cesar --help` shows available commands — v1.0
- ✓ `cesar transcribe --help` shows options — v1.0
- ✓ SQLite-based job queue with persistence — v2.0
- ✓ POST /transcribe endpoint (file upload) — v2.0
- ✓ POST /transcribe/url endpoint (URL reference) — v2.0
- ✓ GET /jobs/{id} for status and results — v2.0
- ✓ GET /jobs for job listing with status filter — v2.0
- ✓ GET /health for server status — v2.0
- ✓ Sequential job processing (queue and process) — v2.0
- ✓ OpenAPI/Swagger docs at /docs — v2.0
- ✓ `cesar serve` command with --port option — v2.0
- ✓ `cesar serve --help` shows server options — v2.0
- ✓ Job recovery on crash (re-queue orphaned jobs) — v2.0
- ✓ CLI accepts YouTube URLs for transcription — v2.1
- ✓ API accepts YouTube URLs via POST /transcribe/url — v2.1
- ✓ yt-dlp bundled as Python dependency — v2.1
- ✓ Audio extracted from YouTube video before transcription — v2.1
- ✓ Progress feedback during download (DOWNLOADING status, spinner) — v2.1
- ✓ YouTube error handling (private, age-restricted, geo-blocked, rate-limited) — v2.1
- ✓ FFmpeg validation with helpful error messages — v2.1
- ✓ Health endpoint reports YouTube capability — v2.1
- ✓ YouTube documentation in README — v2.1

### Active

- [ ] Speaker identification (diarization) in transcripts
- [ ] Markdown output with speaker labels and timestamps
- [ ] CLI configuration file support (~/.config/cesar/config.toml)
- [ ] API local configuration file support
- [ ] Configurable default for speaker identification
- [ ] Speaker ID works with all input sources (files, URLs, YouTube)
- [ ] Offline speaker identification models

### Out of Scope

- AI summarization — deferred to future milestone
- Refactor CLI to use service layer — already done (AudioTranscriber shared by CLI and API)
- Authentication/API keys — internal service, not needed
- Rate limiting — internal service, not needed
- `cesar models` command — add later if needed
- `cesar config` command — using config files instead
- CI/CD install validation — manual testing sufficient
- Windows support — focus on Mac/Linux first
- Webhook callbacks — deferred to future milestone
- Model selection parameter for API — deferred to v2.2+
- Language specification parameter — deferred to v2.2+
- Non-YouTube platforms (Vimeo, etc.) — YouTube only for now
- Playlist auto-expansion — unclear user intent, complexity
- Live stream transcription — requires streaming architecture

## Constraints

- **Offline-first**: Must work without internet after initial setup
- **Cross-platform**: macOS (Intel + Apple Silicon) and Linux x86_64
- **pipx compatible**: Standard Python packaging, no exotic build requirements
- **ffprobe dependency**: Required external tool for audio duration detection
- **No external services**: SQLite for persistence, no Redis/Postgres required

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| pipx over pip install | Isolated environment, clean global command | ✓ Good |
| Subcommand structure (cesar transcribe) | Enables future commands without breaking changes | ✓ Good |
| setuptools build backend | Standard, well-supported, works with pipx | ✓ Good |
| Single-source versioning via importlib.metadata | No duplicate version definitions | ✓ Good |
| click.Group for CLI | Supports subcommands, extensible | ✓ Good |
| Prompt before model download | Models are 150MB+, user should consent | — Pending |
| FastAPI for HTTP API | Modern, async, automatic OpenAPI docs | ✓ Good |
| SQLite for job persistence | No external dependencies, fits offline-first | ✓ Good |
| Async job queue | Transcription is slow, don't block requests | ✓ Good |
| Defer CLI refactor | Ship API first, unify architecture later | ✓ Good |
| Pydantic v2 models | Validation, serialization, ConfigDict pattern | ✓ Good |
| WAL mode with busy_timeout | Concurrent access, lock contention handling | ✓ Good |
| Lifespan context manager | Modern FastAPI pattern (on_event deprecated) | ✓ Good |
| Separate file/URL endpoints | Different content types need different handling | ✓ Good |
| Job recovery on startup | Re-queue orphaned jobs from crashes | ✓ Good |
| Import string for uvicorn | Required for reload support | ✓ Good |
| yt-dlp for YouTube downloads | Only viable option, youtube-dl unmaintained | ✓ Good |
| m4a format for YouTube audio | Smaller than wav, compatible with faster-whisper | ✓ Good |
| UUID-based temp filenames | Collision-free concurrent downloads | ✓ Good |
| DOWNLOADING status for YouTube jobs | Separate download from transcription phase | ✓ Good |
| download_progress field (0-100) | Basic progress without complex real-time hooks | ✓ Good |
| Health endpoint reports FFmpeg | Enable client capability checking | ✓ Good |
| Class-level error_type on exceptions | Enables API structured error responses | ✓ Good |
| Video ID in error messages | Identification without URL clutter | ✓ Good |

---
*Last updated: 2026-02-01 after starting v2.2 Speaker Identification milestone*
