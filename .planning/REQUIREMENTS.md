# Requirements: Cesar v2.0 API

**Defined:** 2026-01-23
**Core Value:** Transcribe audio to text anywhere, offline, with a single command or API call

## v2.0 Requirements

Requirements for the API milestone. Each maps to roadmap phases.

### API Endpoints

- [ ] **API-01**: POST /transcribe accepts file upload (multipart/form-data)
- [ ] **API-02**: POST /transcribe accepts URL reference (JSON body)
- [ ] **API-03**: POST /transcribe returns 202 Accepted with job_id
- [ ] **API-04**: GET /jobs/{id} returns job status and results
- [ ] **API-05**: GET /jobs returns list of all jobs
- [ ] **API-06**: GET /health returns server health status

### Job Lifecycle

- [ ] **JOB-01**: Jobs persisted to SQLite database
- [ ] **JOB-02**: Jobs have four states: queued, processing, completed, error
- [ ] **JOB-03**: Jobs include timestamps (created_at, started_at, completed_at)
- [ ] **JOB-04**: Failed jobs include error message
- [ ] **JOB-05**: Multiple jobs can be queued
- [ ] **JOB-06**: Jobs process sequentially (one at a time)
- [ ] **JOB-07**: Jobs survive server restart (SQLite persistence)

### Results

- [ ] **RES-01**: Completed jobs include transcribed text
- [ ] **RES-02**: Completed jobs include detected language

### Server

- [ ] **SRV-01**: `cesar serve` command starts HTTP server
- [ ] **SRV-02**: `cesar serve --port` option configures port
- [ ] **SRV-03**: OpenAPI/Swagger docs available at /docs

## v2.1+ Requirements

Deferred to future releases. Tracked but not in current roadmap.

### API Enhancements

- **API-10**: POST /transcribe accepts model selection parameter
- **API-11**: POST /transcribe accepts language specification parameter
- **API-12**: DELETE /jobs/{id} cancels pending or deletes completed job

### Results Enhancements

- **RES-10**: Completed jobs include word-level timestamps
- **RES-11**: Jobs show progress percentage during processing

### Notifications

- **NOT-01**: Optional webhook callback URL on job completion
- **NOT-02**: Webhook retry with exponential backoff

### Server Enhancements

- **SRV-10**: `cesar serve --host` option configures bind address

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Authentication/API keys | Internal service, not needed |
| Rate limiting | Internal service, not needed |
| Real-time streaming | Different architecture, defer to future |
| Speaker diarization | Complex feature, defer to v3+ |
| CLI refactor to service layer | Defer to v3.0, ship API first |
| Windows support | Focus on Mac/Linux first |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | Phase 4 | Pending |
| API-02 | Phase 4 | Pending |
| API-03 | Phase 4 | Pending |
| API-04 | Phase 4 | Pending |
| API-05 | Phase 4 | Pending |
| API-06 | Phase 4 | Pending |
| JOB-01 | Phase 2 | Complete |
| JOB-02 | Phase 2 | Complete |
| JOB-03 | Phase 2 | Complete |
| JOB-04 | Phase 2 | Complete |
| JOB-05 | Phase 3 | Complete |
| JOB-06 | Phase 3 | Complete |
| JOB-07 | Phase 2 | Complete |
| RES-01 | Phase 2 | Complete |
| RES-02 | Phase 2 | Complete |
| SRV-01 | Phase 5 | Pending |
| SRV-02 | Phase 5 | Pending |
| SRV-03 | Phase 4 | Pending |

**Coverage:**
- v2.0 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-01-23*
*Last updated: 2026-01-23 after Phase 3 completion*
