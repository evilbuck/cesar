---
date: 2026-05-03
domains: [debugging, bugfix, testing]
topics: [agent-review, progress-callbacks, orchestrator, scene-detection, ffmpeg]
subject: 2026-05-02.screen-recording-agent-processor
artifacts: [plan-agent-review-mode.md]
related: [phases-4-5-output-and-orchestration-2026-05-03.md, ffmpeg-format-validation-2026-05-03.md]
priority: high
status: completed
---

# Session: 2026-05-03 - Agent Review Progress Callback Fix

## Context
- User reproduced `cesar transcribe ... --mode agent-review --quiet` against a real MP4 and saw callback signature errors:
  - `lambda() takes 1 positional argument but 2 were given`
  - fallback then `lambda() takes 1 positional argument but 3 were given`
- The agent-review feature had only unit-level phase completion and needed real-video integration validation.

## Root Cause
- `AgentReviewOrchestrator.orchestrate()` passed a percentage-only callback into `_transcribe()`.
- `_transcribe()` forwarded that callback directly into two lower-level APIs with different signatures:
  - `WhisperXPipeline.transcribe_and_diarize(... progress_callback)` calls `(phase, pct)`.
  - `AudioTranscriber.transcribe_to_segments(... progress_callback)` calls `(pct, segment_count, elapsed_time)`.
- When WhisperX failed and fallback ran, both callback signature mismatches surfaced.

## Fix
- Added explicit progress adapter functions in `cesar/orchestrator.py`:
  - `pipeline_progress(_phase, pct)` forwards only `pct`.
  - `transcriber_progress(pct, _segment_count, _elapsed_time)` forwards only `pct`.
- Added regression tests covering pipeline progress, fallback progress, and transcriber progress.
- During real command verification, also fixed `FFmpegSceneDetector` scdet invocation:
  - Cesar exposes threshold as `0.0-1.0`.
  - FFmpeg `scdet` expects `0-100` and `threshold=...`, not `s=...`.

## Verification
- Regression first reproduced the user's callback errors:
  - `python -m pytest tests/test_orchestrator.py::TestAgentReviewOrchestratorProgress -q` failed before the fix.
- After fix:
  - `python -m pytest tests/test_orchestrator.py::TestAgentReviewOrchestratorProgress tests/test_scene_detector.py -q` → 33 passed.
  - `python -m pytest tests/test_orchestrator.py tests/test_cli.py::TestTranscriptionModes tests/test_validation.py tests/test_video_processor.py tests/test_scene_detector.py tests/test_speech_cue_detector.py tests/test_association.py tests/test_sidecar.py tests/test_formatter.py -q` → 158 passed.
  - Original real command completed and wrote Markdown, sidecar JSON, and images under `~/Videos/screenrecording-2026-05-02_16-17-46*`.
  - Full suite: `python -m pytest tests/ -q` → 560 passed, 9 failed; failures match pre-existing skill install duplicate and serve/uvicorn mock issues noted in prior memory, not this fix.

## Notes
- Real command still warns that installed `whisperx` lacks `DiarizationPipeline`, then correctly falls back to plain transcription. This is separate from the fixed callback crash.
