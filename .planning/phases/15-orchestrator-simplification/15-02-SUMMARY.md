---
phase: 15-orchestrator-simplification
plan: 02
subsystem: integration
tags: [whisperx, cli, api, worker, integration]

# Dependency graph
requires:
  - phase: 15-01
    provides: Simplified orchestrator with WhisperXPipeline and transcriber fallback
provides:
  - CLI integration with WhisperXPipeline
  - API worker integration with WhisperXPipeline
  - User-facing interfaces using unified diarization pipeline
affects: [16-interface-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - WhisperXPipeline creation in CLI when diarize=True
    - WhisperXPipeline creation in worker when job.diarize=True
    - Pass both pipeline and transcriber to orchestrator for fallback

key-files:
  created: []
  modified:
    - cesar/cli.py
    - cesar/api/worker.py
  deleted: []

key-decisions:
  - "CLI passes model size to WhisperXPipeline constructor"
  - "Worker logs partial success message on AuthenticationError before fallback"
  - "Remove early hf_token_required check in worker (let pipeline handle token)"

patterns-established:
  - "CLI: Create WhisperXPipeline when diarize=True, pass to orchestrator with transcriber"
  - "Worker: Create WhisperXPipeline when job.diarize=True, pass to orchestrator with transcriber"
  - "AuthenticationError triggers fallback transcription, not hard failure"

# Metrics
duration: 2min
completed: 2026-02-02
---

# Phase 15 Plan 02: CLI and Worker Integration Summary

**Updated CLI and API worker to use WhisperXPipeline via simplified orchestrator, passing transcriber for fallback support**

## Task Commits

1. **Task 1: Update CLI to use WhisperXPipeline with fallback** - `21a4e38` (feat)
2. **Task 2: Update API worker to use WhisperXPipeline with fallback** - `ecc8258` (feat)

## Changes Made

### CLI (cesar/cli.py)

- **Import changes:**
  - Removed: `SpeakerDiarizer` from diarization
  - Added: `WhisperXPipeline` from whisperx_wrapper
  - Added: `AuthenticationError` from diarization

- **Diarization logic:**
  - Replaced `SpeakerDiarizer(hf_token=hf_token)` with `WhisperXPipeline(model_name=model, hf_token=hf_token)`
  - Updated orchestrator creation: `TranscriptionOrchestrator(pipeline=pipeline, transcriber=transcriber)`
  - Removed early token check warning (pipeline handles token resolution)

- **Error handling:**
  - Added `AuthenticationError` handler with user-friendly message
  - Added `DiarizationError` handler (for when orchestrator can't fall back)

### API Worker (cesar/api/worker.py)

- **Import changes:**
  - Removed: `SpeakerDiarizer` from diarization
  - Added: `WhisperXPipeline` from whisperx_wrapper

- **Diarization logic:**
  - Replaced `SpeakerDiarizer(hf_token=hf_token)` with `WhisperXPipeline(model_name=model_size, hf_token=hf_token)`
  - Updated orchestrator creation: `TranscriptionOrchestrator(pipeline=pipeline, transcriber=transcriber)`
  - Removed early `hf_token_required` return (let pipeline handle missing token)

- **Error handling:**
  - `AuthenticationError`: Falls back to plain transcription with `hf_token_invalid` error code
  - Orchestrator fallback: Returns `diarization_failed` error code
  - Added partial success log message before fallback

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

Ready for Phase 16 (Interface Verification):
- CLI uses WhisperXPipeline when `--diarize` enabled
- Worker uses WhisperXPipeline when `diarize=True` in job
- Both pass transcriber for fallback capability
- Error messages are user-friendly (no "WhisperX" exposed)
- SpeakerDiarizer completely removed from CLI and worker

## Key Files Modified

| File | Changes |
|------|---------|
| cesar/cli.py | WhisperXPipeline import, pipeline creation, orchestrator update, error handlers |
| cesar/api/worker.py | WhisperXPipeline import, pipeline creation, orchestrator update, fallback on auth error |
