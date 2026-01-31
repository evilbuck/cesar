# Roadmap: Cesar

## Milestones

- ✅ **v1.0 Package & CLI** - Phases 1 (shipped 2026-01-23)
- ✅ **v2.0 API** - Phases 2-5 (shipped 2026-01-23)
- 🚧 **v2.1 YouTube Transcription** - Phases 6-8 (in progress)

## Phases

<details>
<summary>✅ v1.0 Package & CLI (Phase 1) - SHIPPED 2026-01-23</summary>

### Phase 1: Package & CLI
**Goal**: Pipx-installable CLI tool with cesar transcribe command
**Plans**: 3 plans

Plans:
- [x] 01-01: Package structure and entry point
- [x] 01-02: CLI migration to click.Group
- [x] 01-03: Testing and documentation

</details>

<details>
<summary>✅ v2.0 API (Phases 2-5) - SHIPPED 2026-01-23</summary>

### Phase 2: Database Foundation
**Goal**: SQLite-based job persistence layer
**Plans**: 2 plans

Plans:
- [x] 02-01: Database models and repository
- [x] 02-02: Job persistence integration

### Phase 3: Background Worker
**Goal**: Async job processing with queue
**Plans**: 1 plan

Plans:
- [x] 03-01: Worker implementation and job recovery

### Phase 4: REST API
**Goal**: HTTP API with transcription endpoints
**Plans**: 2 plans

Plans:
- [x] 04-01: Core API endpoints
- [x] 04-02: File upload and URL download

### Phase 5: Server Command
**Goal**: cesar serve command with uvicorn
**Plans**: 2 plans

Plans:
- [x] 05-01: Server CLI and configuration
- [x] 05-02: Testing and documentation

</details>

### 🚧 v2.1 YouTube Transcription (In Progress)

**Milestone Goal:** Transcribe YouTube videos directly by URL without manual download

#### Phase 6: Core YouTube Module
**Goal**: YouTube audio extraction module with FFmpeg validation
**Depends on**: Phase 5 (v2.0 API shipped)
**Requirements**: YT-01, YT-02, YT-03, YT-04, SYS-01, SYS-02
**Success Criteria** (what must be TRUE):
  1. User can pass YouTube URL to youtube_handler.download_youtube_audio() and receive temp audio file path
  2. Best quality audio extracted from YouTube video using yt-dlp
  3. Temp audio files automatically cleaned up after successful transcription
  4. Temp audio files automatically cleaned up when download or transcription fails
  5. FFmpeg presence validated on startup before accepting YouTube jobs
**Plans**: 1 plan

Plans:
- [ ] 06-01-PLAN.md — Core youtube_handler module with FFmpeg validation, URL detection, and yt-dlp download

#### Phase 7: Interface Integration
**Goal**: CLI and API interfaces accept YouTube URLs with progress feedback
**Depends on**: Phase 6
**Requirements**: INT-01, INT-02, SYS-03, UX-01, UX-02
**Success Criteria** (what must be TRUE):
  1. User can run cesar transcribe <youtube-url> -o output.txt and get transcript
  2. User can POST /transcribe/url with YouTube URL and job processes successfully
  3. CLI displays download progress during YouTube audio extraction
  4. API job status endpoint reports download phase with progress percentage
  5. GET /health endpoint reports FFmpeg and YouTube support availability
**Plans**: TBD

Plans:
- [ ] 07-01: TBD

#### Phase 8: Error Handling & Documentation
**Goal**: Comprehensive error handling and user documentation
**Depends on**: Phase 7
**Requirements**: ERR-01, ERR-02, ERR-03, ERR-04
**Success Criteria** (what must be TRUE):
  1. Invalid YouTube URLs return clear error message explaining URL format
  2. Private or unavailable videos return clear error message indicating access issue
  3. Network failures during download return clear error message suggesting retry
  4. YouTube rate limiting (403/429) returns clear error message with explanation
  5. README.md includes YouTube transcription examples and yt-dlp dependency notes
**Plans**: TBD

Plans:
- [ ] 08-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 6 -> 7 -> 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Package & CLI | v1.0 | 3/3 | Complete | 2026-01-23 |
| 2. Database Foundation | v2.0 | 2/2 | Complete | 2026-01-23 |
| 3. Background Worker | v2.0 | 1/1 | Complete | 2026-01-23 |
| 4. REST API | v2.0 | 2/2 | Complete | 2026-01-23 |
| 5. Server Command | v2.0 | 2/2 | Complete | 2026-01-23 |
| 6. Core YouTube Module | v2.1 | 0/1 | Planned | - |
| 7. Interface Integration | v2.1 | 0/TBD | Not started | - |
| 8. Error Handling & Docs | v2.1 | 0/TBD | Not started | - |
