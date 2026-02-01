# Phase 11: Orchestration & Formatting - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Coordinate transcription with diarization and format speaker-labeled output. This phase bridges existing transcription capability (Phases 1-8) with diarization capability (Phase 10) to produce formatted, speaker-labeled transcripts. CLI and API integration happen in separate phases (12-13).

</domain>

<decisions>
## Implementation Decisions

### Transcript Format Structure
- Use Markdown section headers for speaker labels (### Speaker 1)
- Place timestamps on separate line below each speaker header
- Preserve segment breaks from diarization (don't merge consecutive same-speaker segments)
- Use .md file extension for speaker-labeled transcripts
- Timestamp format: [MM:SS.d - MM:SS.d] (matches Phase 10 decisecond precision)

### Orchestration Flow
- Run sequentially: transcribe first, then diarize, then merge and format
- Only save final output by default (.md file with speaker labels)
- Add debug flag (--keep-intermediate or similar) to save intermediate files for debugging
- Fall back to plain transcript if diarization fails but transcription succeeds
- Orchestrator handles unified progress reporting across all three steps (transcribe, diarize, format)

### Speaker Segment Presentation
- Configurable minimum segment duration threshold (default likely 1s, can be adjusted)
- Show overlapping speech as "Multiple speakers" section with timestamp
- Consecutive same-speaker segments show new timestamp only (no extra blank lines)
- Include metadata header at top: speakers detected, duration, creation date

### Claude's Discretion
- Exact default for minimum segment duration threshold
- Specific progress percentage allocation across steps
- Exact metadata header format and fields
- Intermediate file naming conventions when debug flag enabled

</decisions>

<specifics>
## Specific Ideas

**Format example:**
```markdown
# Transcript

**Speakers:** 3 detected
**Duration:** 12:34
**Created:** 2026-02-01

---

### Speaker 1
[00:00.0 - 00:15.3]
First segment text here.
[00:15.5 - 00:28.7]
Second segment after brief pause.

### Speaker 2
[00:28.9 - 00:45.2]
Different speaker text.

### Multiple speakers
[00:45.2 - 00:48.1]
Overlapping speech content.
```

**Fallback behavior:** If diarization fails (model error, timeout, etc.), save plain .txt transcript without speaker labels. User still gets transcription value even if speaker identification didn't work.

**Progress reporting:** Unified progress bar showing: "Transcribing (0-60%)... Diarizing (60-90%)... Formatting (90-100%)..." or similar breakdown.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-orchestration-&-formatting*
*Context gathered: 2026-02-01*
