# Phase 13: API Integration - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose speaker identification via API endpoints with job queue support. Users can enable diarization for file uploads, URL audio, and YouTube videos through the existing FastAPI endpoints. Job status includes diarization progress, and completed jobs return speaker count and labeled transcripts.

</domain>

<decisions>
## Implementation Decisions

### Request Parameters
- Diarization defaults to enabled (matches CLI behavior)
- Speaker counts use separate fields: `min_speakers` and `max_speakers` as optional integers
- Validate speaker counts at request time — return 400 Bad Request immediately if min > max or values invalid
- Allow `diarize` parameter as object: `diarize: {enabled: true, min_speakers: 2, max_speakers: 5}` or boolean shorthand `diarize: true`

### Response Structure
- Speaker count nested in result: `result: {transcript: "...", speaker_count: 3}`
- Include explicit `result.diarized: true/false` flag — useful when fallback occurs
- Claude's discretion: whether to use single transcript field (markdown when diarized) or separate fields

### Progress Reporting
- Phase breakdown in job status: `progress: {overall: 75, phase: "diarizing", phase_progress: 50}`
- Technical phase names: `downloading`, `transcribing`, `diarizing`, `formatting`
- No estimated time remaining — progress percentage only
- Polling only (GET /jobs/{id}) — no SSE or webhooks

### Error Handling
- Partial failure status when diarization fails but transcription succeeds
  - Job status becomes 'partial'
  - Transcript available in result
  - `diarization_error` field explains what failed
- Specific error codes for HF token issues: `hf_token_required`, `hf_token_invalid`
- HF token from config/env only — not accepted as request parameter
- Retry endpoint: POST /jobs/{id}/retry to re-run failed diarization

### Claude's Discretion
- Structured segments array (`result.segments`) — whether to include raw segment data alongside formatted text
- Exact Pydantic model structure for diarize parameter (bool vs object union type)
- Error message wording and HTTP status codes for validation errors

</decisions>

<specifics>
## Specific Ideas

- Diarize parameter as object allows future extensibility (could add `speaker_labels`, `overlap_handling` etc.)
- Partial failure status lets consumers decide whether to use plain transcript or surface error to end users
- Technical phase names are API-appropriate — human-friendly names can be mapped by clients

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-api-integration*
*Context gathered: 2026-02-01*
