# Phase 5: CLI Integration - Context

**Gathered:** 2026-01-23
**Status:** Ready for planning

<domain>
## Phase Boundary

CLI command to start the HTTP API server. `cesar serve` starts the server with configurable host, port, and worker options. Server lifecycle management (startup, shutdown, signals) is handled here. Authentication, rate limiting, or additional endpoints belong in other phases.

</domain>

<decisions>
## Implementation Decisions

### Startup output
- Minimal startup message: just print the listening URL (e.g., "Listening on http://127.0.0.1:5000")
- No docs URL in startup message — users can discover /docs themselves
- Log all requests by default using uvicorn's built-in formatting
- No ASCII art or banner

### Flag design
- `--port` / `-p`: Port to bind to (default: 5000)
- `--host` / `-h`: Host to bind to (default: 127.0.0.1)
- `--reload`: Enable auto-reload for development (uses uvicorn --reload)
- `--workers`: Number of uvicorn workers (default: 1)
- Both short and long flags for port and host

### Shutdown behavior
- Graceful shutdown on Ctrl+C with "Shutting down..." message
- 30 second timeout waiting for in-flight requests
- Second Ctrl+C forces immediate shutdown
- In-progress transcription jobs: cancel and re-queue (mark as pending for next startup)

### Daemon mode
- No built-in daemon flag — follow standard FastAPI/uvicorn conventions
- Users manage background running via systemd, nohup, etc.
- Single worker by default, --workers flag available for production scaling
- Fixed log level (info) — no --log-level flag

### Claude's Discretion
- Exact uvicorn configuration options
- How to implement job re-queuing on shutdown
- Signal handling implementation details

</decisions>

<specifics>
## Specific Ideas

- "Do whatever is normal for serving FastAPI applications" — follow uvicorn conventions
- Familiar CLI feel like other Python web servers

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-cli-integration*
*Context gathered: 2026-01-23*
