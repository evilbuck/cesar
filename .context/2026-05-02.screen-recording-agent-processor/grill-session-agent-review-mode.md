---
date: 2026-05-02
domains: [design, architecture]
topics: [cesar, agent-review, screenshots, transcription, video-processing]
subject: 2026-05-02.screen-recording-agent-processor
artifacts: [plan-agent-review-mode.md, plan-agent-review-mode-phases.md]
related: []
priority: high
status: active
---

# Grill Session: Agent Review Mode

## Session Metadata

- **Total questions**: 20
- **Threshold**: 20 (default, hit exactly)
- **Phasing recommended**: true (plan exceeds step count and file spread thresholds)
- **Decision domains**: 3 identified
  1. Input/Output contract (Q1, 2, 3, 11, 12, 13, 16, 17)
  2. Screenshot pipeline (Q4, 5, 7, 8, 9, 14, 18, 19)
  3. Transcript pipeline (Q6, 10, 15, 20)

## Question Types

| Type | Count |
|------|-------|
| Interface/abstraction | 4 |
| Output format | 5 |
| Trigger mechanism | 2 |
| Data schema | 2 |
| Fallback behavior | 1 |
| Parameter/default | 6 |

## Key Decisions

### Primary Unit
**Media Input** — not "video" or "audio" to keep consistent language

### Execution Modes
Two distinct modes via `--mode` flag:
- `transcription` (default) — existing behavior
- `agent-review` — screenshot capture + sidecar generation

### Screenshot Triggers
All three capture screenshot:
1. Time-based sampling (default 30s interval)
2. Speech cue detection (configurable word list)
3. Scene change detection (FFmpeg scdet, threshold 0.3)

### Output Structure
```
{output_name}.md           # Markdown with transcript + image refs
{output_name}.sidecar.json # Full metadata
{output_name}/images/       # Screenshots
```

### Screenshot Naming
Timestamp-based: `{name}_{HH-MM-SS}.png`

### Screenshot-Segment Association
Range-based: screenshot belongs to all segments overlapping its timestamp

### Speech Cues
Case-insensitive default list:
"this", "here", "that", "look at", "notice", "pay attention", "see how", "issue", "problem", "bug", "wrong", "broken"

### Scope
- Local files only (no YouTube/URL in v1)
- FFmpeg handles format detection
- Graceful fallback if scene detection unavailable

## Break Points Identified

Natural phase boundaries at each domain cluster. See `plan-agent-review-mode-phases.md` for full phasing.

## Resolved Conflicts

None — no terminology conflicts with existing codebase (no domain docs existed)

## Deferred Decisions

None — all 20 questions resolved in session
