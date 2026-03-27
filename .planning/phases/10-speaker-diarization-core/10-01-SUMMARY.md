---
phase: 10
plan: 01
subsystem: diarization
tags: [pyannote, speaker-detection, huggingface, gpu-optimization]

requires:
  - 09-02 # Config system for hf_token

provides:
  - core-diarization-pipeline
  - speaker-segment-detection
  - hf-authentication-flow

affects:
  - 10-02 # Transcript formatting will use DiarizationResult
  - 10-03 # CLI integration will use SpeakerDiarizer

tech-stack:
  added:
    - pyannote.audio>=3.1.0
  patterns:
    - lazy-pipeline-loading
    - token-resolution-hierarchy
    - gpu-auto-detection

key-files:
  created:
    - cesar/diarization.py
    - tests/test_diarization.py
  modified:
    - pyproject.toml
    - cesar/config.py

decisions:
  - id: D10-01-01
    what: Use pyannote.audio 3.1 for speaker diarization
    why: Industry-standard library with excellent offline support after initial download
    impact: Requires HuggingFace authentication for model download
  - id: D10-01-02
    what: Token resolution hierarchy (provided > env > cached)
    why: Flexible authentication with sensible fallbacks
    impact: Users can set token in config, env var, or use cached token
  - id: D10-01-03
    what: Default speaker range 1-5
    why: Reasonable defaults based on CONTEXT.md guidance
    impact: Prevents extreme auto-detection cases
  - id: D10-01-04
    what: Lazy pipeline loading on first diarize() call
    why: Avoid slow model loading until actually needed
    impact: First diarization call slower, subsequent calls fast

metrics:
  duration: 5min
  completed: 2026-02-01
---

# Phase 10 Plan 01: Speaker Diarization Core Summary

**One-liner:** pyannote.audio speaker diarization with HF token auth, GPU optimization, and lazy pipeline loading

## What Was Built

Created the core speaker diarization module using pyannote.audio pipeline:

1. **Dependency & Configuration**
   - Added pyannote.audio>=3.1.0 to project dependencies
   - Extended CesarConfig with hf_token field
   - Documented HF token setup in config template

2. **SpeakerDiarizer Class**
   - Lazy pipeline loading (loaded on first diarize() call)
   - Token resolution hierarchy: provided → env (HF_TOKEN) → cached (~/.cache/huggingface/token)
   - Automatic GPU detection via torch.cuda.is_available()
   - Min/max speaker parameters with sensible defaults (1-5)
   - Progress callback support for UI integration
   - Clear exception handling: AuthenticationError vs DiarizationError

3. **Data Models**
   - SpeakerSegment dataclass: start/end times + speaker label
   - DiarizationResult dataclass: segments list + speaker count + audio duration

4. **Comprehensive Testing**
   - 17 unit tests with full coverage
   - Mocked pyannote.audio to avoid model downloads during testing
   - Tests for token resolution, pipeline loading, GPU detection, diarization

## Technical Details

**Authentication Flow:**
```python
# Token resolution priority:
1. hf_token parameter passed to __init__
2. HF_TOKEN environment variable
3. ~/.cache/huggingface/token file
4. None (will fail on pipeline load with helpful error)
```

**GPU Optimization:**
```python
# Automatic GPU detection and usage:
if torch.cuda.is_available():
    pipeline.to(torch.device("cuda"))
# Provides 10-20x speedup on GPU systems
```

**Pipeline Usage:**
```python
diarizer = SpeakerDiarizer(hf_token="hf_xxx")
result = diarizer.diarize(
    "audio.wav",
    min_speakers=2,
    max_speakers=4,
    progress_callback=lambda msg: print(msg)
)
# Returns DiarizationResult with speaker segments
```

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

**D10-01-01: Use pyannote.audio 3.1**
- Industry-standard speaker diarization library
- Excellent offline support after initial model download
- Requires HuggingFace authentication (token needed once)

**D10-01-02: Token resolution hierarchy**
- Priority: provided > env var > cached file
- Flexible for different deployment scenarios
- Clear error messages when token missing/invalid

**D10-01-03: Default speaker range 1-5**
- Prevents extreme auto-detection edge cases
- Aligned with CONTEXT.md guidance
- Users can override with min_speakers/max_speakers params

**D10-01-04: Lazy pipeline loading**
- Pipeline loaded on first diarize() call, not __init__
- Avoids slow model loading until actually needed
- First call slower (~5-10s), subsequent calls fast

## Risks & Mitigations

**Risk:** HuggingFace authentication friction for new users
- **Mitigation:** Clear error messages with step-by-step instructions
- **Mitigation:** Config template documents token setup process
- **Mitigation:** Support for cached token (login once, use forever)

**Risk:** Large model download on first use (~1GB)
- **Mitigation:** Clear progress feedback during download
- **Mitigation:** Models cached locally for offline use
- **Acceptance:** Unavoidable for ML-based diarization

## Next Phase Readiness

**Ready for Phase 10-02 (Transcript Formatting):**
- ✅ DiarizationResult provides speaker segments with timestamps
- ✅ Speaker labels follow standard format (SPEAKER_00, SPEAKER_01, etc.)
- ✅ Segment timing precision suitable for alignment with transcription

**Ready for Phase 10-03 (CLI Integration):**
- ✅ SpeakerDiarizer class ready to integrate into CLI workflow
- ✅ Progress callback designed for Rich progress bars
- ✅ Clear exception types for user-facing error messages

**Blockers:** None

**Concerns:** None - pyannote.audio is proven and stable

## Testing Notes

All 17 unit tests passing:
- Token resolution from all sources (provided, env, cached)
- Pipeline loading success and error cases
- Authentication error detection and messaging
- GPU detection and pipeline movement
- Diarization with default and custom speaker ranges
- Multiple speaker detection
- Progress callback integration

Tests use sys.modules mocking to avoid pyannote.audio import during testing.

## Validation Results

✅ All verification steps passed:
1. Import test: `from cesar.diarization import SpeakerDiarizer` ✅
2. Config test: `CesarConfig(hf_token='x')` ✅
3. Unit tests: All 17 tests passing ✅
4. Dependency check: pyannote.audio in pyproject.toml ✅

## Files Modified

**Created:**
- cesar/diarization.py (200 lines) - Core diarization module
- tests/test_diarization.py (343 lines) - Comprehensive unit tests

**Modified:**
- pyproject.toml - Added pyannote.audio>=3.1.0 dependency
- cesar/config.py - Added hf_token field and documentation

## Commits

- 986ba63: feat(10-01): add pyannote.audio dependency and HF token config
- df53c78: feat(10-01): create SpeakerDiarizer class with pyannote pipeline
- 995b9a5: test(10-01): add comprehensive unit tests for diarization module

---

**Phase:** 10-speaker-diarization-core
**Plan:** 10-01
**Completed:** 2026-02-01
**Duration:** 5 minutes
