# Roadmap: Cesar v2.0 API

## Overview

This milestone adds an HTTP API layer to Cesar, enabling programmatic transcription access via async job queue. Starting from the existing CLI (v1.0), we build foundation data models, a background worker for sequential job processing, HTTP endpoints with FastAPI, and CLI integration. The result is `cesar serve` launching a server with full OpenAPI docs.

## Milestones

- v1.0 Package & CLI (shipped 2026-01-23)
- **v2.0 API** - Phases 2-5 (in progress)

## Phases

**Phase Numbering:**
- Phases 2-5 for v2.0 (phase 1 was v1.0)
- Decimal phases (e.g., 2.1) reserved for urgent insertions

- [ ] **Phase 2: Foundation** - Job models and SQLite repository
- [ ] **Phase 3: Background Worker** - Sequential job processor
- [ ] **Phase 4: HTTP API** - FastAPI endpoints and file handling
- [ ] **Phase 5: CLI Integration** - cesar serve command

## Phase Details

### Phase 2: Foundation
**Goal**: Job data can be persisted and retrieved from SQLite
**Depends on**: Phase 1 (v1.0 CLI - complete)
**Requirements**: JOB-01, JOB-02, JOB-03, JOB-04, JOB-07, RES-01, RES-02
**Success Criteria** (what must be TRUE):
  1. Job can be created with pending state and persisted to SQLite
  2. Job state transitions (queued -> processing -> completed/error) are recorded
  3. Job timestamps (created_at, started_at, completed_at) are tracked
  4. Failed jobs store error message
  5. Jobs survive server restart (data persists in SQLite file)
**Plans**: 2 plans in 2 waves

Plans:
- [ ] 02-01-PLAN.md - Job model and JobStatus enum with Pydantic v2
- [ ] 02-02-PLAN.md - SQLite schema and JobRepository with async CRUD

### Phase 3: Background Worker
**Goal**: Jobs are processed sequentially in the background
**Depends on**: Phase 2
**Requirements**: JOB-05, JOB-06
**Success Criteria** (what must be TRUE):
  1. Multiple jobs can be queued while one is processing
  2. Jobs process one at a time in order received
  3. Worker picks up pending jobs automatically
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: HTTP API
**Goal**: Full REST API for transcription jobs with OpenAPI docs
**Depends on**: Phase 3
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06, SRV-03
**Success Criteria** (what must be TRUE):
  1. POST /transcribe with file upload creates job and returns 202 with job_id
  2. POST /transcribe with URL reference creates job and returns 202 with job_id
  3. GET /jobs/{id} returns job status, and results when complete
  4. GET /jobs returns list of all jobs
  5. GET /health returns server health status
  6. OpenAPI/Swagger docs available at /docs
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: CLI Integration
**Goal**: Server can be started via cesar serve command
**Depends on**: Phase 4
**Requirements**: SRV-01, SRV-02
**Success Criteria** (what must be TRUE):
  1. `cesar serve` starts HTTP server on default port
  2. `cesar serve --port 8080` starts server on specified port
  3. `cesar serve --help` shows available options
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 2. Foundation | 0/2 | Ready | - |
| 3. Background Worker | 0/? | Not started | - |
| 4. HTTP API | 0/? | Not started | - |
| 5. CLI Integration | 0/? | Not started | - |
