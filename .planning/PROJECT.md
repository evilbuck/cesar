# Cesar

## What This Is

An offline audio transcription CLI tool using faster-whisper. Install via `pipx install .` and run `cesar transcribe <file> -o <output>`. Works completely offline after initial model download.

## Core Value

Transcribe audio to text anywhere, offline, with a single command — no cloud services, no API keys, no ongoing costs.

## Current State

**Shipped:** v1.0 Package & CLI (2026-01-23)
- Pipx-installable package with `cesar` command
- `cesar transcribe` subcommand for audio transcription
- 982 LOC Python, 35 tests passing

**Tech stack:** Python 3.10+, Click, Rich, faster-whisper, setuptools

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

- [ ] Prompt before downloading models on first run
- [ ] Show model size estimate in download prompt
- [ ] Clear error message if ffprobe/ffmpeg not installed
- [ ] Platform-specific ffmpeg install suggestion (brew/apt)
- [ ] Works on macOS (Intel and Apple Silicon)
- [ ] Works on Linux x86_64

### Out of Scope

- AI summarization — deferred to future milestone (configurable providers planned)
- `cesar models` command — add later if needed
- `cesar config` command — add later if needed
- CI/CD install validation — manual testing sufficient
- Windows support — focus on Mac/Linux first

## Constraints

- **Offline-first**: Must work without internet after initial setup
- **Cross-platform**: macOS (Intel + Apple Silicon) and Linux x86_64
- **pipx compatible**: Standard Python packaging, no exotic build requirements
- **ffprobe dependency**: Required external tool for audio duration detection

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| pipx over pip install | Isolated environment, clean global command | ✓ Good |
| Subcommand structure (cesar transcribe) | Enables future commands without breaking changes | ✓ Good |
| setuptools build backend | Standard, well-supported, works with pipx | ✓ Good |
| Single-source versioning via importlib.metadata | No duplicate version definitions | ✓ Good |
| click.Group for CLI | Supports subcommands, extensible | ✓ Good |
| Prompt before model download | Models are 150MB+, user should consent | — Pending |

---
*Last updated: 2026-01-23 after v1.0 milestone*
