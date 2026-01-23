# Phase 4: HTTP API - Context

**Gathered:** 2026-01-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Full REST API for transcription jobs with OpenAPI docs. POST /transcribe creates jobs (file upload or URL), GET /jobs/{id} returns status and results, GET /jobs lists all jobs, GET /health reports server status. Worker integration handled here.

</domain>

<decisions>
## Implementation Decisions

### File Handling
- Support both file upload (multipart/form-data) and URL reference (JSON body)
- Uploaded files stored in system temp directory, cleaned up after job completion
- 100 MB file size limit for uploads
- Server fetches remote files from http(s):// URLs before transcribing

### Response Design
- Full job object returned inline (job_id, status, text, language, timestamps)
- 202 response includes complete job object, not just job_id
- Error format: `{"error": "message", "detail": "..."}` with appropriate HTTP status codes
- Job list supports optional status filter: GET /jobs?status=queued

### API Conventions
- POST /transcribe for creating transcription jobs (matches CLI command)
- No API prefix — simple paths: /transcribe, /jobs, /jobs/{id}, /health
- URL-based requests use application/json: `{"url": "...", "model": "base"}`
- Basic health check: `{"status": "healthy"}` plus worker status

### Worker Lifecycle
- Worker starts automatically with server via FastAPI lifespan events
- Graceful shutdown: wait for current job to complete before stopping
- Health check includes worker status: `{"status": "healthy", "worker": "running"}`
- Server fails to start if worker fails to start — fail fast

### Claude's Discretion
- Exact temp file naming and cleanup timing
- URL download timeout and retry logic
- File type validation approach
- OpenAPI schema details and descriptions

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard FastAPI patterns and conventions.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-http-api*
*Context gathered: 2026-01-23*
