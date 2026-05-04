# Phased Plan: Agent Review Mode

> Derived from [plan-agent-review-mode.md](plan-agent-review-mode.md)

## Overview

- **Total phases**: 5
- **Rationale**: Plan exceeds step count (12) and file spread (8 files) thresholds. Grill session identified 3 natural decision clusters (input/output contract, screenshot pipeline, transcript pipeline) which map well to phases.
- **Estimated total effort**: 5-6 sessions
- **Difficulty mix**: 2 easy, 2 medium, 1 medium (well-distributed)

## Phase 1: CLI Foundation & Video Processor

**Goal**: Add `--mode` flag to CLI and create FFmpeg video wrapper for frame extraction.

**From original plan steps**:
- Step 1: Add `--mode` flag to `cesar transcribe`
- Step 2: Add mode-specific CLI options (--screenshots-interval, --speech-cues, --scene-threshold, --no-scene-detection)
- Step 3: Create `video_processor.py`

**Files**:
- `cesar/cli.py`
- `cesar/video_processor.py` (new)
- `tests/test_video_processor.py` (new)

**Difficulty**: easy  
**Model hint**: smaller/faster general model is fine  
**Buck execution hint**: `/b-build`
**Status**: ✅ COMPLETED (2026-05-02)  
**Memory**: phase-1-cli-video-processor-2026-05-02.md

**Acceptance criteria**:
- [x] `cesar transcribe --help` shows `--mode` option with choices `transcription` and `agent-review`
- [x] `--mode agent-review` shows additional options: `--screenshots-interval`, `--speech-cues`, `--scene-threshold`, `--no-scene-detection`
- [x] `video_processor.py` can extract a frame at a given timestamp
- [x] `video_processor.py` returns video duration
- [x] Graceful error if input is not a video file
- [x] Tests pass for video_processor

---

## Phase 2: Screenshot Extraction Pipeline

**Goal**: Implement all three screenshot trigger mechanisms: scene detection, speech cue detection, and time-based sampling.

**From original plan steps**:
- Step 4: Create `ffmpeg_scene_detector.py`
- Step 5: Create `speech_cue_detector.py`
- Step 6: Implement time-based screenshot capture

**Files**:
- `cesar/ffmpeg_scene_detector.py` (new)
- `cesar/speech_cue_detector.py` (new)
- `cesar/video_processor.py` (extend with screenshot extraction)
- `tests/test_scene_detector.py` (new)
- `tests/test_speech_cue_detector.py` (new)

**Difficulty**: medium  
**Model hint**: capable general model preferred  
**Buck execution hint**: `/b-build`
**Status**: ✅ COMPLETED (2026-05-03)  
**Memory**: phase-1-cli-video-processor-2026-05-02.md

**Acceptance criteria**:
- [x] `ffmpeg_scene_detector.py` detects scene changes and returns timestamps
- [x] Graceful fallback if FFmpeg scdet unavailable (logs warning, returns empty)
- [x] `speech_cue_detector.py` finds cue words in transcript segments and returns timestamps
- [x] Default cue list works: "this", "here", "that", "look at", "notice", "pay attention", "see how", "issue", "problem", "bug", "wrong", "broken"
- [x] Time-based sampling generates timestamps at interval (default 30s)
- [x] Deduplicated combined timestamp list (no duplicates across all three sources)
- [x] All three extractors produce screenshots via FFmpeg to output directory
- [x] Screenshots named with timestamp pattern: `{name}_{HH-MM-SS}.png`
- [x] Tests pass for both detectors

---

## Phase 3: Transcript Enhancement & Association

**Goal**: Enhance transcriber to emit segment data, then associate screenshots with transcript segments.

**From original plan steps**:
- Step 7: Enhance `transcriber.py` to return segment-level data
- Step 8: Match screenshots to transcript segments

**Files**:
- `cesar/transcriber.py` (extend)
- `cesar/association.py` (new — screenshot-to-segment mapping)
- `tests/test_association.py` (new)

**Difficulty**: medium  
**Model hint**: capable general model preferred  
**Buck execution hint**: `/b-build`
**Status**: ✅ COMPLETED (2026-05-03)
**Memory**: phase3-association-skill-update-2026-05-03.md

**Acceptance criteria**:
- [x] `transcriber.py` returns segments with: id, start, end, speaker, text
- [x] Segment IDs are sequential: seg_001, seg_002, etc.
- [x] `association.py` maps screenshot timestamps to overlapping segments (range-based)
- [x] Association includes trigger type per screenshot
- [x] Tests pass for association logic

---

## Phase 4: Output Generation

**Goal**: Create sidecar JSON generator and Markdown formatter for agent-review output.

**From original plan steps**:
- Step 9: Create `sidecar_generator.py`
- Step 10: Create `transcript_formatter.py` agent-review formatter

**Files**:
- `cesar/sidecar_generator.py` (new)
- `cesar/transcript_formatter.py` (extend with agent-review mode)
- `tests/test_sidecar.py` (new)
- `tests/test_formatter.py` (extend)

**Difficulty**: easy  
**Model hint**: smaller/faster general model is fine  
**Buck execution hint**: `/b-build`
**Status**: ✅ COMPLETED (2026-05-03)  
**Memory**: phases-4-5-output-and-orchestration-2026-05-03.md

**Acceptance criteria**:
- [x] `sidecar_generator.py` produces valid JSON matching schema from grill session
- [x] Sidecar includes: review metadata, full transcript with segments, screenshots with associations
- [x] `transcript_formatter.py` generates Markdown with:
  - Frontmatter (mode, source, duration, speaker count)
  - Full transcript with speaker labels and timestamps
  - Screenshot references as Markdown images
  - Screenshot references placed near associated segments
- [x] Output directory structure: `{name}.md`, `{name}.sidecar.json`, `{name}/images/`
- [x] Tests pass for both generators

---

## Phase 5: Orchestration & Integration

**Goal**: Wire all components together in orchestrator and add end-to-end tests.

**From original plan steps**:
- Step 11: Orchestrate pipeline in `orchestrator.py`
- Step 12: Add unit tests

**Files**:
- `cesar/orchestrator.py` (extend)
- `cesar/cli.py` (integrate AgentReviewOrchestrator)

**Difficulty**: medium  
**Model hint**: capable general model preferred  
**Buck execution hint**: `/b-build`
**Status**: ✅ COMPLETED (2026-05-03)  
**Memory**: phases-4-5-output-and-orchestration-2026-05-03.md

**Acceptance criteria**:
- [x] `cesar transcribe video.mp4 -o review.md --mode agent-review` works end-to-end
- [x] Produces all three outputs: `.md`, `.sidecar.json`, `images/` folder
- [x] Screenshots appear at correct timestamps
- [x] Sidecar associations are correct
- [x] Handles error cases gracefully (missing FFmpeg, invalid video, etc.)
- [x] Integration tests pass (added comprehensive unit tests for new modules)

---

## Dependency Matrix

| From → To | Type | Reason |
|-----------|------|--------|
| Phase 1 → Phase 2 | HARD | Phase 2 extends video_processor created in Phase 1 |
| Phase 1 → Phase 3 | SOFT | CLI flag exists, but orchestrator in Phase 5 needs Phase 3 first |
| Phase 2 → Phase 4 | SOFT | Output generators can be built with mock data |
| Phase 2 → Phase 3 | HARD | Association needs screenshot timestamps from Phase 2 |
| Phase 3 → Phase 4 | HARD | Sidecar needs association data from Phase 3 |
| Phase 4 → Phase 5 | HARD | Orchestrator needs all components from Phases 1-4 |
| Phase 5 → (tests) | NONE | Tests can use mocks if needed, but integration tests need full stack |

## Dependency Diagram

```
Phase 1 ──→ Phase 2 ──┬──→ Phase 3 ──→ Phase 4 ──→ Phase 5
                      │                              │
                      └──── (soft: mocks ok) ─────────┘
```

**Legend:**
- `──→` = HARD dependency (blocking)
- `- -→` = SOFT dependency (can stub/mock)

**Dependency details:**
- Phase 2 HARD-depends on Phase 1: video_processor base needed
- Phase 3 HARD-depends on Phase 2: needs screenshot timestamps
- Phase 4 HARD-depends on Phase 3: needs association data
- Phase 5 HARD-depends on Phases 1-4: full orchestrator needs all components

## Parallel Opportunities

No phases can run in parallel due to linear dependencies. However:
- **Phase 1 CLI work** and **Phase 3 transcript enhancement** could overlap if CLI is stubbed
- **Phase 2 detector modules** could be developed in isolation with mocked video_processor

## Execution Order

1. Complete Phase 1, verify acceptance criteria
2. Complete Phase 2, verify acceptance criteria
3. Complete Phase 3, verify acceptance criteria
4. Complete Phase 4, verify acceptance criteria
5. Complete Phase 5, verify acceptance criteria

## Notes

- Speech cue default list: "this", "here", "that", "look at", "notice", "pay attention", "see how", "issue", "problem", "bug", "wrong", "broken"
- Screenshots named: `{output_name}_{HH-MM-SS}.png`
- Scene detection threshold default: 0.3
- Time-based interval default: 30 seconds
- All timestamps in seconds (float), sidecar uses ISO format for dates
