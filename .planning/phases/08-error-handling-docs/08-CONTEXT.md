# Phase 8: Error Handling & Documentation - Context

**Gathered:** 2026-01-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver clear, actionable error messages for YouTube-related failures and user documentation with examples. Covers: invalid URLs, private/unavailable videos, network failures, rate limiting, and README updates with YouTube usage.

</domain>

<decisions>
## Implementation Decisions

### Error message style
- Balanced tone: brief technical info + plain English explanation
- Include actionable suggestions only when user can actually do something (e.g., retry for network issues, not for private videos)
- Show video ID in error messages (not full URL) for identification without clutter
- Verbose mode (-v) shows cleaned-up underlying cause without raw stack traces

### Error categorization
- Specific error types: invalid URL, private video, age-restricted, network timeout, rate limited, etc.
- Age-restricted videos get their own clear error message
- CLI exit codes: simple 0=success, 1=any error (message has details)
- API errors: HTTP status code + `error_type` field in response (e.g., `{"error_type": "invalid_youtube_url", "message": "..."}`)

### Documentation scope
- API documentation primary, CLI brief mention
- Quick start example at top, then detailed examples with options
- No troubleshooting section — error messages are self-explanatory
- yt-dlp dependency: installation command + note about FFmpeg requirement

### Retry/recovery guidance
- Suggest retry only for network errors (timeouts, connection failures)
- Rate limiting (403/429): explain it's YouTube throttling, suggest trying later
- No external links in error messages — keep them self-contained
- FFmpeg missing: state it's not found, no install hints

### Claude's Discretion
- Exact error message wording
- Which yt-dlp exceptions map to which error types
- README structure and formatting
- Order of examples in documentation

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

*Phase: 08-error-handling-docs*
*Context gathered: 2026-01-31*
