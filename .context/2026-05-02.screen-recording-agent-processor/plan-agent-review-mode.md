---
status: completed
date: 2026-05-02
updated: 2026-05-03
subject: 2026-05-02.screen-recording-agent-processor
---

# Plan: Agent Review Mode for Cesar

**Memory**: 
- phase-1-cli-video-processor-2026-05-02.md (Phases 1 & 2)
- phase3-association-skill-update-2026-05-03.md (Phase 3)
- phases-4-5-output-and-orchestration-2026-05-03.md (Phases 4 & 5)

## Goal

Add `--mode agent-review` capability to `cesar transcribe` that captures screenshots from screen recordings and produces an agent-readable review document with associated transcript segments.

## Context

- Previous work: Initial brainstorm in `brainstorm-screen-recording-agent.md`
- Grill session: 20 decisions resolved (see grill session)
- Scope: Local video files only, FFmpeg + Cesar CLI

## Scope

**In scope**:
- `--mode agent-review` flag for `cesar transcribe`
- Screenshot extraction via FFmpeg (time-based, speech cues, scene changes)
- Transcript-segment to screenshot association
- Markdown output with screenshot references
- JSON sidecar with full metadata
- Speech cue detection from transcript

**Out of scope**:
- YouTube/URL support (local files only)
- Summarization (full transcript only)
- Base64 image embedding
- Inline image flag

## Affected Files

- `cesar/cli.py` — Add `--mode` flag and agent-review sub-logic
- `cesar/transcriber.py` — Extend to return segments with timestamps for cue matching
- `cesar/transcript_formatter.py` — Add agent-review Markdown formatter
- `cesar/video_processor.py` — New file: FFmpeg screenshot extraction
- `cesar/speech_cue_detector.py` — New file: Detect cues in transcript
- `cesar/sidecar_generator.py` — New file: Generate JSON sidecar
- `cesar/ffmpeg_scene_detector.py` — New file: Scene change detection
- `tests/` — Unit tests for new modules

## Implementation Steps

### CLI Layer

1. **Add `--mode` flag to `cesar transcribe`**
   - Options: `transcription` (default), `agent-review`
   - Validate mode-specific requirements (e.g., agent-review requires video input)
   - Pass mode to transcriber/orchestrator

2. **Add mode-specific CLI options**
   - `--screenshots-interval` — Time between time-based screenshots (default: 30s)
   - `--speech-cues` — Comma-separated cue words (default list provided)
   - `--scene-threshold` — FFmpeg scene detection threshold (default: 0.3)
   - `--no-scene-detection` — Disable scene change detection

### Screenshot Extraction

3. **Create `video_processor.py`** — FFmpeg wrapper for video handling
   - Validate video file (exists, readable by FFmpeg)
   - Get video duration
   - Extract frames at specific timestamps
   - Check scene detection availability

4. **Create `ffmpeg_scene_detector.py`** — Scene change detection
   - Run FFmpeg with `scenetimescdet` filter
   - Parse scene change timestamps
   - Graceful fallback if scdet unavailable
   - Configurable threshold parameter

5. **Create `speech_cue_detector.py`** — Speech cue extraction
   - Take transcript segments with timestamps
   - Scan text for cue words (case-insensitive)
   - Return timestamps where cues found
   - Configurable cue list

6. **Implement time-based screenshot capture**
   - Generate timestamps at `--screenshots-interval` intervals
   - Deduplicate with scene-change and cue timestamps
   - Use FFmpeg to extract frames

### Transcript Processing

7. **Enhance `transcriber.py`** — Return segment-level data
   - Ensure segments include: id, start, end, speaker, text
   - Pass segments to orchestrator for cue matching

8. **Match screenshots to transcript segments**
   - For each screenshot timestamp, find overlapping segments
   - Build association map (screenshot → segments)

### Output Generation

9. **Create `sidecar_generator.py`** — JSON sidecar generation
   - Output schema: review metadata + transcript + screenshots + associations
   - Use timestamp-based filename pattern: `{name}_{HH-MM-SS}.png`
   - Include trigger type and segment IDs per screenshot

10. **Create `transcript_formatter.py` agent-review formatter**
    - Generate Markdown with:
      - Frontmatter: mode, source, duration, speaker count
      - Full transcript with timestamps
      - Screenshot references interleaved at relevant segments
      - Image links relative to Markdown location

11. **Orchestrate the pipeline in `orchestrator.py`**
    - Coordindate: transcription → cue detection → screenshot extraction → sidecar → Markdown
    - Handle output directory creation
    - Clean up on error

### Testing

12. **Add unit tests**
    - Test speech cue detection
    - Test screenshot timestamp generation
    - Test segment-to-screenshot association
    - Test sidecar schema generation
    - Test CLI flag parsing

## Verification

- [ ] `cesar transcribe review.mp4 -o review.md --mode agent-review` produces:
  - `review.md` with transcript and screenshot references
  - `review.sidecar.json` with full metadata
  - `review/images/` folder with screenshots
- [ ] Speech cues trigger screenshot capture
- [ ] Scene changes trigger screenshot capture
- [ ] Time-based sampling captures at intervals
- [ ] Screenshots associate with correct transcript segments
- [ ] Graceful fallback if FFmpeg scene detection unavailable
- [ ] Tests pass

## Notes

- Speech cue default list: "this", "here", "that", "look at", "notice", "pay attention", "see how", "issue", "problem", "bug", "wrong", "broken"
- Screenshots named: `{output_name}_{HH-MM-SS}.png`
- Sidecar always emitted when mode is agent-review
