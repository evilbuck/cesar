# Technology Stack

**Analysis Date:** 2026-01-23

## Languages

**Primary:**
- Python 3.14.0 - All application code

**Secondary:**
- None

## Runtime

**Environment:**
- Python 3.14 (latest via mise)
- Virtual environment in `venv/`

**Package Manager:**
- pip
- Lockfile: `requirements.txt` present (67 dependencies pinned)

**Version Management:**
- mise (config: `mise.toml`) - Set to `python = "latest"`

## Frameworks

**Core:**
- faster-whisper 1.1.1 - Speech-to-text transcription engine (CTranslate2-based)
- Click 8.2.1 - CLI argument parsing and command structure
- Rich 14.0.0 - Terminal output formatting, progress bars, colored text

**ML/AI:**
- ctranslate2 4.6.3 - Fast inference engine for transformer models
- torch 2.7.1 - PyTorch for device detection and CUDA/MPS support
- onnxruntime 1.22.0 - ONNX model inference support
- huggingface-hub 0.33.0 - Model downloading and caching

**Testing:**
- pytest 8.4.0 - Test runner
- pytest-asyncio 1.0.0 - Async test support

**Code Quality:**
- black 25.1.0 - Code formatter
- ruff 0.11.13 - Linter
- mypy 1.16.0 - Type checker
- isort 6.0.1 - Import sorter
- pre-commit 4.2.0 - Git hooks

**Build/Dev:**
- None (pure Python, no build step required)

## Key Dependencies

**Critical:**
- faster-whisper 1.1.1 - Core transcription engine; wraps CTranslate2 for Whisper models
- torch 2.7.1 - Required for device detection (CUDA/MPS availability checks)
- av 14.4.0 - Audio/video processing (PyAV)

**Infrastructure:**
- huggingface-hub 0.33.0 - Model downloads to `~/.cache/huggingface/hub/`
- tokenizers 0.21.1 - Text tokenization for Whisper
- numpy 2.3.0 - Numerical arrays for audio processing

**UI/Output:**
- rich 14.0.0 - Progress bars, spinners, colored console output
- click 8.2.1 - CLI framework with validation

## Configuration

**Environment:**
- No `.env` file required (offline-first design)
- Runtime environment variables set programmatically in `device_detection.py`:
  - `OMP_NUM_THREADS` - OpenMP thread count
  - `MKL_NUM_THREADS` - Intel MKL threads
  - `NUMEXPR_NUM_THREADS` - NumExpr threads

**Build:**
- No build configuration (Python script-based)
- `mise.toml` - Python version pinning

**Model Caching:**
- Models auto-download to `~/.cache/huggingface/hub/` on first use
- No additional configuration required

## Platform Requirements

**Development:**
- Python 3.14+ (or compatible version)
- pip for dependency installation
- ffprobe (from ffmpeg) - Required for audio duration detection
- ~2-4GB RAM minimum (varies by model size)

**Production:**
- Same as development (CLI tool, not server-based)
- Supports: macOS (Intel/Apple Silicon), Linux (x86_64), Windows

**Hardware Acceleration:**
- CUDA (NVIDIA GPU) - Detected via torch/nvidia-smi
- MPS (Apple Metal) - Detected via torch.backends.mps
- CPU fallback with multi-threading (auto-detected cores)

## Supported Model Sizes

| Model | RAM Required | Relative Speed |
|-------|-------------|----------------|
| tiny | ~1GB | 20x real-time |
| base | ~1GB | 15x real-time |
| small | ~2GB | 10x real-time |
| medium | ~5GB | 6x real-time |
| large | ~10GB | 4x real-time |

---

*Stack analysis: 2026-01-23*
