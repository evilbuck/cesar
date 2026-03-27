# Phase 15: Orchestrator Simplification - Context

**Gathered:** 2026-02-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace existing transcription+diarization pipeline with WhisperX unified approach. Delete old alignment code, update orchestrator to use WhisperX pipeline, maintain existing output format, preserve error handling contracts, and support fallback to plain transcription.

</domain>

<decisions>
## Implementation Decisions

### Migration approach
- Clean replacement — delete old code entirely, WhisperX is the only path
- Claude decides which files to delete (timestamp_aligner.py confirmed, diarizer.py if WhisperX replaces it)
- Public API can simplify if it makes code cleaner — no need to preserve exact signatures
- No concerns about permanent deletion — git history preserves old code if ever needed

### Formatter compatibility
- Formatter should adapt to accept WhisperX segment structure directly (not orchestrator transforming)
- Minor output format improvements OK if WhisperX enables better presentation
- More granular speaker turns if WhisperX boundaries are tighter and accurate

### Error mapping
- Generic error messages — don't expose "WhisperX" in user-facing errors
- Wrap all diarization failures in DiarizationError with cause attached
- Explicit partial success messaging: "Transcription succeeded, diarization failed: [reason]" before fallback

### Claude's Discretion
- Whether to delete diarizer.py based on what WhisperX replaces
- Word-level vs segment-level timestamps based on output complexity
- Transcription error handling — maintain current contract or wrap for consistency
- Specific granularity threshold for speaker turns

</decisions>

<specifics>
## Specific Ideas

- User wants clear communication when diarization fails but transcription succeeded
- User is comfortable with format improvements, not locked to exact current output
- Clean deletion preferred over deprecation folders or migration notes

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-orchestrator-simplification*
*Context gathered: 2026-02-02*
