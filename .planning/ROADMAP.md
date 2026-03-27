# Roadmap: Cesar

## Milestones

- ✅ **v1.0 Package & CLI** - Phase 1 (shipped 2026-01-23)
- ✅ **v2.0 API** - Phases 2-5 (shipped 2026-01-23)
- ✅ **v2.1 YouTube Transcription** - Phases 6-8 (shipped 2026-02-01)
- ✅ **v2.2 Speaker Identification** - Phases 9-13 (shipped 2026-02-01)
- ✅ **v2.3 WhisperX Migration** - Phases 14-16 (shipped 2026-02-02)
- 🚧 **v2.4 Idempotent Processing** - Phases 17-19 (in progress)

## Phases

<details>
<summary>✅ v1.0 Package & CLI (Phase 1) - SHIPPED 2026-01-23</summary>

### Phase 1: Package & CLI
**Goal**: Pipx-installable CLI tool with `cesar transcribe` command
**Plans**: 3 plans

Plans:
- [x] 01-01: Package structure and build system
- [x] 01-02: CLI subcommand conversion
- [x] 01-03: Installation verification

</details>

<details>
<summary>✅ v2.0 API (Phases 2-5) - SHIPPED 2026-01-23</summary>

### Phase 2: SQLite Job Persistence
**Goal**: Async job queue with SQLite storage
**Plans**: 2 plans

Plans:
- [x] 02-01: Database schema and repository
- [x] 02-02: Job models and validation

### Phase 3: Background Worker
**Goal**: Process transcription jobs asynchronously
**Plans**: 2 plans

Plans:
- [x] 03-01: Worker implementation
- [x] 03-02: Job recovery on crash

### Phase 4: HTTP API Layer
**Goal**: REST endpoints with OpenAPI docs
**Plans**: 2 plans

Plans:
- [x] 04-01: Core endpoints (health, jobs)
- [x] 04-02: Transcription endpoints (file, URL)

### Phase 5: Server Command
**Goal**: `cesar serve` CLI command
**Plans**: 1 plan

Plans:
- [x] 05-01: Serve command implementation

</details>

<details>
<summary>✅ v2.1 YouTube Transcription (Phases 6-8) - SHIPPED 2026-02-01</summary>

### Phase 6: YouTube Foundation
**Goal**: yt-dlp integration for audio extraction
**Plans**: 2 plans

Plans:
- [x] 06-01: YouTube handler module
- [x] 06-02: Error handling and validation

### Phase 7: CLI/API Integration
**Goal**: YouTube URL support in both interfaces
**Plans**: 2 plans

Plans:
- [x] 07-01: CLI YouTube support
- [x] 07-02: API YouTube support

### Phase 8: Documentation
**Goal**: Complete YouTube usage documentation
**Plans**: 1 plan

Plans:
- [x] 08-01: README updates and examples

</details>

<details>
<summary>✅ v2.2 Speaker Identification (Phases 9-13) - SHIPPED 2026-02-01</summary>

### Phase 9: Configuration System
**Goal**: TOML config file support
**Plans**: 2 plans

Plans:
- [x] 09-01: Config loading and validation
- [x] 09-02: XDG directory support

### Phase 10: Diarization Foundation
**Goal**: Speaker identification via pyannote.audio
**Plans**: 2 plans

Plans:
- [x] 10-01: Pyannote integration
- [x] 10-02: Timestamp alignment

### Phase 11: Markdown Output
**Goal**: Speaker labels in formatted transcripts
**Plans**: 2 plans

Plans:
- [x] 11-01: Markdown formatter
- [x] 11-02: Extension correction (.txt to .md)

### Phase 12: CLI/API Diarization
**Goal**: --diarize flag and diarize parameter
**Plans**: 2 plans

Plans:
- [x] 12-01: CLI implementation
- [x] 12-02: API implementation

### Phase 13: Pipeline Orchestration
**Goal**: Unified transcription + diarization pipeline
**Plans**: 2 plans

Plans:
- [x] 13-01: Orchestrator with fallback support
- [x] 13-02: Error handling and testing

</details>

<details>
<summary>✅ v2.3 WhisperX Migration (Phases 14-16) - SHIPPED 2026-02-02</summary>

### Phase 14: WhisperX Foundation
**Goal**: Replace pyannote with WhisperX unified pipeline
**Plans**: 2 plans

Plans:
- [x] 14-01: WhisperX wrapper module
- [x] 14-02: Model management and lazy loading

### Phase 15: Orchestrator Simplification
**Goal**: Delete timestamp_aligner, use WhisperX alignment
**Plans**: 3 plans

Plans:
- [x] 15-01: Orchestrator refactor
- [x] 15-02: Backward compatibility testing
- [x] 15-03: Cleanup and code removal

### Phase 16: Interface Verification
**Goal**: Preserve all CLI/API interfaces unchanged
**Plans**: 3 plans

Plans:
- [x] 16-01: E2E CLI testing
- [x] 16-02: E2E API testing
- [x] 16-03: Test suite verification

</details>

### 🚧 v2.4 Idempotent Processing (In Progress)

**Milestone Goal:** Enable resumable, cacheable transcription pipelines where intermediate artifacts persist on failure and identical inputs skip reprocessing.

#### Phase 17: Cache Foundation
**Goal**: Content-addressable storage with atomic writes and XDG compliance
**Depends on**: Phase 16
**Requirements**: CACHE-01, CACHE-02
**Success Criteria** (what must be TRUE):
  1. Cache directory exists at ~/.cache/cesar/ (XDG-compliant)
  2. Cache writes are atomic (no partial files from crashes)
  3. YouTube audio downloads can be retrieved from cache by URL
  4. Cache survives application crashes without corruption
**Plans**: TBD

Plans:
- [ ] 17-01: TBD

#### Phase 18: Download Caching & Controls
**Goal**: YouTube downloads skip re-download, with time-step freshness and user controls
**Depends on**: Phase 17
**Requirements**: DLOAD-01, DLOAD-02, DLOAD-03, DLOAD-04, CACHE-03, CACHE-04
**Success Criteria** (what must be TRUE):
  1. Identical YouTube URL downloads only once, subsequent requests use cache
  2. Cache keys include time-step function (15-minute windows) for URL freshness
  3. Time-step interval is configurable via config.toml
  4. CLI --no-cache flag forces reprocessing (bypasses cache)
  5. API no_cache parameter forces reprocessing (bypasses cache)
**Plans**: TBD

Plans:
- [ ] 18-01: TBD

#### Phase 19: Disk Management
**Goal**: Cache has size limits with LRU eviction to prevent unbounded growth
**Depends on**: Phase 18
**Requirements**: DISK-01, DISK-02, DISK-03
**Success Criteria** (what must be TRUE):
  1. Cache respects 10GB default size limit
  2. Oldest cached entries are automatically evicted when limit exceeded (LRU)
  3. Cache size limit is configurable via config.toml
**Plans**: TBD

Plans:
- [ ] 19-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 17 → 18 → 19

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Package & CLI | v1.0 | 3/3 | Complete | 2026-01-23 |
| 2. SQLite Persistence | v2.0 | 2/2 | Complete | 2026-01-23 |
| 3. Background Worker | v2.0 | 2/2 | Complete | 2026-01-23 |
| 4. HTTP API Layer | v2.0 | 2/2 | Complete | 2026-01-23 |
| 5. Server Command | v2.0 | 1/1 | Complete | 2026-01-23 |
| 6. YouTube Foundation | v2.1 | 2/2 | Complete | 2026-02-01 |
| 7. CLI/API Integration | v2.1 | 2/2 | Complete | 2026-02-01 |
| 8. Documentation | v2.1 | 1/1 | Complete | 2026-02-01 |
| 9. Configuration System | v2.2 | 2/2 | Complete | 2026-02-01 |
| 10. Diarization Foundation | v2.2 | 2/2 | Complete | 2026-02-01 |
| 11. Markdown Output | v2.2 | 2/2 | Complete | 2026-02-01 |
| 12. CLI/API Diarization | v2.2 | 2/2 | Complete | 2026-02-01 |
| 13. Pipeline Orchestration | v2.2 | 2/2 | Complete | 2026-02-01 |
| 14. WhisperX Foundation | v2.3 | 2/2 | Complete | 2026-02-02 |
| 15. Orchestrator Simplification | v2.3 | 3/3 | Complete | 2026-02-02 |
| 16. Interface Verification | v2.3 | 3/3 | Complete | 2026-02-02 |
| 17. Cache Foundation | v2.4 | 0/? | Not started | - |
| 18. Download Caching & Controls | v2.4 | 0/? | Not started | - |
| 19. Disk Management | v2.4 | 0/? | Not started | - |
