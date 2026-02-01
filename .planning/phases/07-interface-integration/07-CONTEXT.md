# Phase 7: Interface Integration - Context

**Gathered:** 2026-01-31
**Status:** Ready for planning

<domain>
## Phase Boundary

CLI and API interfaces accept YouTube URLs with progress feedback. Users can run `cesar transcribe <youtube-url>` or POST to `/transcribe/url` with a YouTube URL. Progress is displayed during download phase. Health endpoint reports YouTube capability.

</domain>

<decisions>
## Implementation Decisions

### URL detection behavior
- Automatic detection: check if URL is YouTube first, fall back to generic URL download
- Accept all YouTube URL formats: youtube.com/watch, youtu.be, youtube.com/shorts, etc.
- Fail fast: if YouTube handler fails, report error immediately (no fallback to generic)
- Single videos only: reject playlist URLs with clear error message

### Progress feedback
- CLI shows Rich progress bar with percentage and ETA during download
- Separate phases: display "Downloading..." then "Transcribing..." as distinct steps
- API adds new `downloading` status value distinct from `processing`
- Quiet mode (-q) suppresses all progress including download

### Claude's Discretion
- Exact progress bar styling and layout
- How to extract video title for display (if at all)
- Health endpoint detail level for YouTube capability
- CLI output format (whether to include video metadata)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-interface-integration*
*Context gathered: 2026-01-31*
