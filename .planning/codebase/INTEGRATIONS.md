# External Integrations

**Analysis Date:** 2026-01-23

## APIs & External Services

**Hugging Face Hub:**
- Purpose: Download Whisper models on first use
- SDK/Client: `huggingface-hub` package
- Auth: None required (public models)
- Behavior: Auto-downloads to `~/.cache/huggingface/hub/`
- Network: Required only on first model download, then fully offline

**No other external APIs** - This is an offline-first tool.

## Data Storage

**Databases:**
- None

**File Storage:**
- Local filesystem only
- Input: Audio files (mp3, wav, m4a, ogg, flac, aac, wma)
- Output: Text files (user-specified path)

**Model Cache:**
- Location: `~/.cache/huggingface/hub/`
- Size: 39MB (tiny) to 2.9GB (large)
- Generated: Yes (downloaded automatically)
- Committed: No

**Caching:**
- Whisper models cached locally after first download
- No application-level caching

## Authentication & Identity

**Auth Provider:**
- None (CLI tool with no authentication)

## Monitoring & Observability

**Error Tracking:**
- None (errors printed to stderr)

**Logs:**
- Console output via Rich library
- No persistent logging
- Debug via `--verbose` flag

## CI/CD & Deployment

**Hosting:**
- Not applicable (local CLI tool)

**CI Pipeline:**
- None configured
- pre-commit hooks available for local development

## Environment Configuration

**Required env vars:**
- None (all configuration via CLI arguments)

**Auto-configured at runtime:**
- `OMP_NUM_THREADS` - Set by `device_detection.py`
- `MKL_NUM_THREADS` - Set by `device_detection.py`
- `NUMEXPR_NUM_THREADS` - Set by `device_detection.py`

**Secrets location:**
- None required

## System Dependencies

**Required External Tools:**
- `ffprobe` (part of ffmpeg) - Used for audio duration detection
  - Called via subprocess in `transcriber.py:get_audio_duration()`
  - Install: `brew install ffmpeg` (macOS) or `pacman -S ffmpeg` (Arch)

**Optional External Tools:**
- `nvidia-smi` - GPU detection fallback when torch unavailable
- `nvcc` - CUDA version detection
- `sysctl` - Apple Silicon detection on macOS

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Third-Party Model Providers

**OpenAI Whisper (via CTranslate2):**
- Model variants: tiny, base, small, medium, large
- License: MIT
- Source: Hugging Face model hub
- Conversion: CTranslate2 format for fast inference

## Network Requirements

**Initial Setup:**
- Internet required to download Whisper models (one-time)

**Normal Operation:**
- Fully offline after model download
- No network calls during transcription

---

*Integration audit: 2026-01-23*
