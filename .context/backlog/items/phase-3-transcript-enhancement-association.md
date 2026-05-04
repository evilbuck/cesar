---
title: Phase 3 - Transcript Enhancement & Association
status: pending
priority: high
created: 2026-05-02
updated: 2026-05-02
completed: null
related:
  - .context/2026-05-02.screen-recording-agent-processor/plan-agent-review-mode-phases.md
---

# Phase 3: Transcript Enhancement & Association

Enhance transcriber to emit segments, associate screenshots with transcript segments.

## Files
- `cesar/transcriber.py` (extend)
- `cesar/association.py`

## Acceptance Criteria
- Transcriber returns segments with: id, start, end, speaker, text
- Segment IDs sequential (seg_001, seg_002, etc.)
- Range-based association (screenshot → overlapping segments)
- Association includes trigger type
- Tests pass
