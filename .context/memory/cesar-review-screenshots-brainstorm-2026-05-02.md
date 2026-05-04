---
date: 2026-05-02
domains: [planning, tooling, docs]
topics: [cesar, screenshots, transcription, video-review, brainstorm]
subject: 2026-05-02.screen-recording-agent-processor
artifacts: [brainstorm-screen-recording-agent.md]
related: []
priority: medium
status: active
---

# Session: 2026-05-02 - Cesar review screenshots brainstorm

## Context
- User wants Cesar to support turning narrated screen recordings into agent-readable change requests.
- Brainstorm converged on making this a Cesar feature instead of a separate tool.

## Decisions Made
- Prefer this to live in Cesar core.
- Preferred output is Markdown with local image references.
- Do not burn timestamps into screenshots.
- Prefer metadata-based screenshot/transcript association, with room for future time ranges.
- Likely UX is a new `--screenshots` flag on `cesar transcribe`.

## Implementation Notes
- Brainstorm saved under subject folder `2026-05-02.screen-recording-agent-processor`.
- Key unresolved design question is the metadata/artifact model connecting transcript sections to screenshots.

## Next Steps
- [ ] Convert brainstorm into a concrete plan in the Cesar repo.
- [ ] Decide initial metadata format and whether to emit a machine-readable sidecar.
- [ ] Decide first-version heuristics for screenshot capture.
