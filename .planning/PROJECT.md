# Cesar

## What This Is

An offline audio transcription CLI tool using faster-whisper. Transcribes audio files completely offline after initial model download, with automatic hardware optimization for CPU, CUDA, and Apple Metal. Being packaged for easy installation via pipx.

## Core Value

Transcribe audio to text anywhere, offline, with a single command — no cloud services, no API keys, no ongoing costs.

## Requirements

### Validated

- ✓ Transcribe audio files (mp3, wav, m4a) to text — existing
- ✓ Automatic device detection and optimization (CPU/CUDA/MPS) — existing
- ✓ Multiple Whisper model sizes (tiny/base/small/medium/large) — existing
- ✓ Progress display with Rich formatting — existing
- ✓ Time-limited transcription (--start-time, --end-time, --max-duration) — existing
- ✓ Verbose and quiet output modes — existing
- ✓ Streaming segments for memory efficiency — existing

### Active

- [ ] Install via `pipx install git+<repo-url>`
- [ ] Global `cesar` command available after install
- [ ] Subcommand structure: `cesar transcribe <file>`
- [ ] Prompt before downloading models on first run
- [ ] Works on macOS and Linux

### Out of Scope

- AI summarization — deferred to future milestone (configurable providers planned)
- `cesar models` command — add later if needed
- `cesar config` command — add later if needed
- CI/CD install validation — defer, manual testing sufficient for now
- Windows support validation — focus on Mac/Linux first

## Context

**Existing codebase:**
- Modular architecture: CLI (cli.py) → Core (transcriber.py) → Device (device_detection.py)
- Click-based CLI with Rich progress bars
- Models auto-download to ~/.cache/huggingface/hub/
- Python 3.14, faster-whisper 1.1.1, comprehensive test suite
- Currently invoked as `python transcribe.py <file> -o <output>`

**Target state:**
- Proper Python package with pyproject.toml
- Entry point registered for `cesar` command
- Subcommand structure for future expansion (transcribe now, summarize later)

## Constraints

- **Offline-first**: Must work without internet after initial setup
- **Cross-platform**: macOS (Intel + Apple Silicon) and Linux x86_64
- **pipx compatible**: Standard Python packaging, no exotic build requirements
- **ffprobe dependency**: Required external tool for audio duration detection

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| pipx over pip install | Isolated environment, clean global command | — Pending |
| Subcommand structure (cesar transcribe) | Enables future commands without breaking changes | — Pending |
| Prompt before model download | Models are 150MB+, user should consent | — Pending |

---
*Last updated: 2026-01-23 after initialization*
