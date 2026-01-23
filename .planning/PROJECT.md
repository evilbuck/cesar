# Cesar

## What This Is

An offline audio transcription tool with CLI and HTTP API interfaces. Install via `pipx install .` for the CLI (`cesar transcribe`) or run `cesar serve` to start the API server with OpenAPI docs. Works completely offline after initial model download.

## Core Value

Transcribe audio to text anywhere, offline, with a single command or API call — no cloud services, no API keys, no ongoing costs.

## Current Milestone: v2.0 API

**Goal:** Add HTTP API layer with async job queue for programmatic transcription access.

**Target features:**
- Service layer for transcription orchestration
- FastAPI-based HTTP API with OpenAPI/Swagger docs
- Async job queue with SQLite persistence
- File upload and URL reference support
- Polling and optional webhook callbacks
- `cesar serve` command to start server

## Current State

**Shipped:** v1.0 Package & CLI (2026-01-23)
- Pipx-installable package with `cesar` command
- `cesar transcribe` subcommand for audio transcription
- 982 LOC Python, 35 tests passing

**Tech stack:** Python 3.10+, Click, Rich, faster-whisper, setuptools, FastAPI (v2.0)

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

### Active

- [ ] TranscriptionService class for job orchestration
- [ ] SQLite-based job queue with persistence
- [ ] POST /transcribe endpoint (file upload)
- [ ] POST /transcribe endpoint (URL reference)
- [ ] GET /jobs/{id} for status and results
- [ ] Optional webhook callback on completion
- [ ] Multiple concurrent jobs (queue and process)
- [ ] OpenAPI/Swagger docs at /docs
- [ ] `cesar serve` command with --port option
- [ ] `cesar serve --help` shows server options

### Out of Scope

- AI summarization — deferred to future milestone
- Refactor CLI to use service layer — future milestone (v3.0)
- Authentication/API keys — internal service, not needed
- Rate limiting — internal service, not needed
- `cesar models` command — add later if needed
- `cesar config` command — add later if needed
- CI/CD install validation — manual testing sufficient
- Windows support — focus on Mac/Linux first

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
| FastAPI for HTTP API | Modern, async, automatic OpenAPI docs | — Pending |
| SQLite for job persistence | No external dependencies, fits offline-first | — Pending |
| Async job queue | Transcription is slow, don't block requests | — Pending |
| Defer CLI refactor | Ship API first, unify architecture later | — Pending |

---
*Last updated: 2026-01-23 after starting v2.0 milestone*
