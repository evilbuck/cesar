# Phase 12: CLI Integration - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose speaker diarization to CLI users via flags and integrate with existing transcription workflow. The orchestration layer (Phase 11) already works — this phase adds CLI interface and user experience polish.

</domain>

<decisions>
## Implementation Decisions

### Flag design
- Diarization enabled by default (`--diarize` is true by default)
- Use `--no-diarize` to disable (Click boolean flag pattern)
- Long flag only — no short `-d` form
- Speaker count controls via config file only, not CLI flags
- HuggingFace token via config file or `HF_TOKEN` env var only, no CLI flag

### Output file handling
- Auto `.md` extension for diarized output
- If user specifies `.txt` with diarize on: warn and change to `.md`
- Plain transcription (`--no-diarize`) respects user's `-o` extension exactly
- If `-o` omitted: auto-generate filename from input (e.g., `audio.mp3` → `audio.md`)

### Progress display
- Sequential progress bars: Transcription → Identifying speakers → Formatting output
- Diarization bar labeled "Identifying speakers"
- Show formatting step as brief third phase
- Quiet mode (`-q`) suppresses all progress including diarization

### Output summary
- Detailed breakdown: speaker count, segment count, duration
- Always show processing time: Transcription Xs, Diarization Xs, Total Xm Xs
- Verbose mode (`-v`) adds per-speaker stats: Speaker 1: 4:23 (35%), etc.
- Fallback behavior: if diarization fails, save plain transcript with warning

### Claude's Discretion
- Exact wording of warning messages
- Progress bar styling/colors
- Time formatting (seconds vs minutes:seconds threshold)

</decisions>

<specifics>
## Specific Ideas

- Summary format like: "3 speakers, 47 segments, 12:34 duration. Saved to transcript.md"
- Fallback warning like: "Diarization failed, saved plain text"
- Per-speaker verbose output like: "Speaker 1: 4:23 (35%), Speaker 2: 5:11 (42%)"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-cli-integration*
*Context gathered: 2026-02-01*
