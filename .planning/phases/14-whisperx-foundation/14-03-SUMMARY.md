---
phase: 14
plan: 03
subsystem: whisperx-testing
tags: [whisperx, unit-tests, testing, mocking]

dependency-graph:
  requires: ["14-02"]
  provides: ["whisperx-wrapper-tests"]
  affects: ["15-01", "16-01"]

tech-stack:
  added: []
  patterns: ["unittest mocking", "whisperx mock pipeline"]

key-files:
  created:
    - tests/test_whisperx_wrapper.py
  modified: []

decisions:
  - key: "extensive-mocking"
    choice: "Mock all whisperx calls for fast CI"
    reason: "Tests run without requiring actual whisperx models"

metrics:
  duration: "2min"
  completed: "2026-02-02"
---

# Phase 14 Plan 03: Unit Tests for WhisperXPipeline Summary

**One-liner:** 43 unit tests covering WhisperXPipeline with mocked whisperx for fast CI execution

## What Was Done

Created comprehensive unit tests for the WhisperXPipeline module in `tests/test_whisperx_wrapper.py`.

### Test Categories Implemented

1. **WhisperXSegment Tests (2 tests)**
   - Segment creation with all fields
   - Segment equality comparison

2. **Initialization Tests (9 tests)**
   - Default values (model=large-v2, batch_size=16)
   - Custom model name and batch size
   - Token from provided value
   - Token from HF_TOKEN environment variable
   - Token from cached file (~/.cache/huggingface/token)
   - Token is None when not found
   - Provided token takes priority

3. **Device Resolution Tests (5 tests)**
   - Explicit cpu device passes through
   - Explicit cuda device passes through
   - Auto selects cuda when available
   - Auto selects cpu when cuda unavailable
   - Auto selects cpu when torch import fails

4. **Compute Type Resolution Tests (5 tests)**
   - Explicit float32/float16/int8 pass through
   - Auto selects float16 for cuda
   - Auto selects int8 for cpu

5. **Lazy Loading Tests (5 tests)**
   - Models are None after init
   - Whisper model loaded only once
   - Align model reloads on language change
   - Align model not reloaded for same language
   - Diarize model loaded only once

6. **Transcription Pipeline Tests (7 tests)**
   - Successful transcribe_and_diarize with mocked whisperx
   - Multiple speakers detected
   - min/max_speakers passed to diarization
   - Default speaker range used (1-5)
   - Progress callback is called during pipeline
   - Segment with missing speaker gets UNKNOWN label
   - Empty text handled

7. **Error Handling Tests (6 tests)**
   - AuthenticationError on 401
   - AuthenticationError on Unauthorized message
   - AuthenticationError on access denied
   - DiarizationError on generic failure
   - DiarizationError when whisperx not installed
   - Load whisper model raises on import error

8. **Segment Conversion Tests (4 tests)**
   - Convert basic segments
   - Strips whitespace from text
   - Convert empty segments list
   - Calculates duration from audio length

## Commits

| Hash | Description |
|------|-------------|
| d5daaef | test(14-03): add unit tests for WhisperXPipeline |

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

```
tests/test_whisperx_wrapper.py: 43 passed in 0.83s
```

All 43 tests pass. Tests use extensive mocking to avoid requiring actual whisperx models.

## Key Patterns Used

1. **Mock whisperx module**: Used `patch.dict('sys.modules', {'whisperx': mock_whisperx})` to inject mocked whisperx
2. **Mock audio array**: Used `MagicMock` with `__len__` to simulate numpy audio arrays
3. **Token caching tests**: Used `patch.object(Path, 'exists')` and `patch.object(Path, 'read_text')` for file system mocking
4. **Environment variable tests**: Used `@patch.dict(os.environ, {...})` for env var testing

## Next Phase Readiness

Ready for Phase 15 (Orchestrator Simplification):
- WhisperXPipeline module is fully tested
- Tests verify the interface contract for integration
- Error handling is confirmed working
