# Roadmap: Cesar

## Milestones

- **v1.0 Package & CLI** - Phase 1 (shipped 2026-01-23)
- **v2.0 API** - Phases 2-5 (shipped 2026-01-23)
- **v2.1 YouTube Transcription** - Phases 6-8 (shipped 2026-02-01)
- **v2.2 Speaker Identification** - Phases 9-13 (shipped 2026-02-01)
- **v2.3 WhisperX Migration** - Phases 14-16 (shipped 2026-02-02)

## Phases

<details>
<summary>v1.0 Package & CLI (Phase 1) - SHIPPED 2026-01-23</summary>

### Phase 1: Package & CLI
**Goal**: Pipx-installable CLI tool with cesar transcribe command
**Plans**: 3 plans

Plans:
- [x] 01-01: Package structure and installation
- [x] 01-02: CLI subcommand migration
- [x] 01-03: Test migration and cleanup

</details>

<details>
<summary>v2.0 API (Phases 2-5) - SHIPPED 2026-01-23</summary>

### Phase 2: Database & Jobs
**Goal**: SQLite job persistence with async repository
**Plans**: 2 plans

Plans:
- [x] 02-01: Database schema and models
- [x] 02-02: Job repository implementation

### Phase 3: Background Worker
**Goal**: Async job processing with graceful shutdown
**Plans**: 1 plan

Plans:
- [x] 03-01: Background worker implementation

### Phase 4: API Core
**Goal**: FastAPI application with transcription endpoints
**Plans**: 2 plans

Plans:
- [x] 04-01: FastAPI setup and health endpoint
- [x] 04-02: Transcription endpoints (file upload + URL)

### Phase 5: CLI Integration
**Goal**: cesar serve command with API server
**Plans**: 2 plans

Plans:
- [x] 05-01: Server command implementation
- [x] 05-02: Documentation and testing

</details>

<details>
<summary>v2.1 YouTube Transcription (Phases 6-8) - SHIPPED 2026-02-01</summary>

### Phase 6: YouTube Download
**Goal**: Extract audio from YouTube videos with yt-dlp
**Plans**: 2 plans

Plans:
- [x] 06-01: YouTube handler with audio extraction
- [x] 06-02: Error handling and validation

### Phase 7: CLI & API Integration
**Goal**: YouTube URL support in CLI and API
**Plans**: 3 plans

Plans:
- [x] 07-01: CLI YouTube integration
- [x] 07-02: API YouTube integration
- [x] 07-03: Progress tracking and status updates

### Phase 8: Error Handling & Documentation
**Goal**: Comprehensive error handling and user documentation
**Plans**: 2 plans

Plans:
- [x] 08-01: Granular error handling
- [x] 08-02: README documentation and examples

</details>

<details>
<summary>v2.2 Speaker Identification (Phases 9-13) - SHIPPED 2026-02-01</summary>

**Milestone Goal:** Add speaker diarization to transcripts with configurable defaults

### Phase 9: Configuration System
**Goal**: Load and validate hierarchical configuration from TOML files
**Depends on**: Nothing (independent foundation)
**Requirements**: CONF-01, CONF-02, CONF-03, CONF-04, CONF-05, CONF-06, CONF-07
**Success Criteria** (what must be TRUE):
  1. CLI loads config from ~/.config/cesar/config.toml with valid TOML parsing
  2. API loads config from local config.toml file in server directory
  3. CLI arguments override config file values (CLI always wins)
  4. Invalid config values produce clear error messages at startup (fail fast)
  5. User can set default speaker identification behavior in config file
**Plans**: 2 plans

Plans:
- [x] 09-01: Config foundation (Pydantic model, TOML loading, validation, template)
- [x] 09-02: CLI and API config integration

### Phase 10: Speaker Diarization Core
**Goal**: Identify speakers in audio using pyannote with timestamp alignment
**Depends on**: Phase 9 (config system for model paths and speaker count defaults)
**Requirements**: DIAR-09, DIAR-10, DIAR-11, DIAR-12
**Success Criteria** (what must be TRUE):
  1. Speaker identification works completely offline after initial model download
  2. System detects speakers automatically when no count specified
  3. User sees progress feedback during diarization process (separate from transcription)
  4. User can specify minimum number of speakers via config or parameter
  5. User can specify maximum number of speakers via config or parameter
**Plans**: 2 plans

Plans:
- [x] 10-01: Core diarization module (pyannote pipeline, HF token, GPU detection)
- [x] 10-02: Timestamp alignment (temporal intersection, segment splitting)

### Phase 11: Orchestration & Formatting
**Goal**: Coordinate transcription with diarization and format speaker-labeled output
**Depends on**: Phase 10 (diarization capability must exist to orchestrate)
**Requirements**: DIAR-03, DIAR-04, DIAR-05
**Success Criteria** (what must be TRUE):
  1. Transcript output includes speaker labels (Speaker 1, Speaker 2, etc.) for each segment
  2. Transcript output includes timestamps for each speaker segment
  3. Speaker-labeled output uses Markdown format with inline bold labels
  4. Plain text transcripts and speaker-labeled transcripts use consistent formatting
**Plans**: 2 plans

Plans:
- [x] 11-01: TDD formatter (MarkdownTranscriptFormatter with speaker headers and timestamps)
- [x] 11-02: Orchestrator (TranscriptionOrchestrator coordinating pipeline with fallback)

### Phase 12: CLI Integration
**Goal**: User-facing CLI flag for speaker identification
**Depends on**: Phase 11 (orchestration must work to expose via CLI)
**Requirements**: DIAR-01, DIAR-06
**Success Criteria** (what must be TRUE):
  1. User can enable speaker identification via --diarize flag
  2. Speaker identification works with local audio files via CLI
  3. CLI shows progress for both transcription and diarization steps
  4. CLI displays speaker count in output summary
**Plans**: 1 plan

Plans:
- [x] 12-01: Add --diarize flag with orchestrator integration and multi-step progress

### Phase 13: API Integration
**Goal**: Speaker identification via API endpoints with job queue support
**Depends on**: Phase 11 (orchestration must work to expose via API)
**Requirements**: DIAR-02, DIAR-07, DIAR-08
**Success Criteria** (what must be TRUE):
  1. User can enable speaker identification via API parameter (diarize: true)
  2. Speaker identification works with URL audio sources via API
  3. Speaker identification works with YouTube videos via API
  4. API job responses include speaker count when diarization enabled
  5. API job status tracking includes diarization progress phase
**Plans**: 3 plans

Plans:
- [x] 13-01: Models, database, and repository for diarization fields
- [x] 13-02: Worker integration with orchestrator
- [x] 13-03: Server endpoints and retry functionality

</details>

<details>
<summary>v2.3 WhisperX Migration (Phases 14-16) - SHIPPED 2026-02-02</summary>

**Milestone Goal:** Replace pyannote diarization with WhisperX unified pipeline for better alignment and simpler architecture

### Phase 14: WhisperX Foundation
**Goal**: Install WhisperX and create wrapper module for unified pipeline
**Depends on**: Nothing (fresh foundation replacing pyannote)
**Requirements**: WX-01, WX-02, WX-05
**Success Criteria** (what must be TRUE):
  1. whisperx package installs successfully with compatible torch versions
  2. WhisperX model loads and transcribes audio files
  3. wav2vec2 alignment produces word-level timestamps
  4. Diarization pipeline assigns speakers to words
  5. Unit tests verify each pipeline stage in isolation
**Plans**: 3 plans in 3 waves

Plans:
- [x] 14-01: Update dependencies (remove pyannote.audio, add whisperx) [Wave 1]
- [x] 14-02: Create WhisperXPipeline wrapper module [Wave 2]
- [x] 14-03: Unit tests for WhisperXPipeline [Wave 3]

### Phase 15: Orchestrator Simplification
**Goal**: Replace existing pipeline with WhisperX unified approach
**Depends on**: Phase 14 (WhisperX wrapper must exist)
**Requirements**: WX-03, WX-04, WX-08, WX-09
**Success Criteria** (what must be TRUE):
  1. timestamp_aligner.py is deleted from codebase
  2. orchestrator.py uses WhisperX pipeline instead of separate components
  3. Markdown output format matches existing format (speaker labels, timestamps)
  4. DiarizationError and AuthenticationError exceptions work unchanged
  5. Fallback to plain transcription works when diarization fails
**Plans**: 3 plans in 3 waves

Plans:
- [x] 15-01: Core module updates (orchestrator, diarization, delete timestamp_aligner)
- [x] 15-02: CLI and API worker integration with WhisperXPipeline
- [x] 15-03: Test updates for new architecture

### Phase 16: Interface Verification
**Goal**: Validate all CLI and API interfaces work unchanged with new backend
**Depends on**: Phase 15 (orchestrator must be updated first)
**Requirements**: WX-06, WX-07, WX-10, WX-11, WX-12
**Success Criteria** (what must be TRUE):
  1. CLI --diarize flag produces speaker-labeled output (no interface changes)
  2. API diarize parameter produces speaker-labeled response (no interface changes)
  3. All existing diarization unit tests pass (with updated mocks)
  4. E2E CLI test: `cesar transcribe --diarize <file>` produces correct Markdown
  5. E2E API test: POST /transcribe with diarize=true produces correct response
**Plans**: 3 plans in 2 waves

Plans:
- [x] 16-01: E2E CLI diarization tests
- [x] 16-02: E2E API diarization tests
- [x] 16-03: Full test suite verification

</details>

## Progress

**Execution Order:**
Phases execute in numeric order: 14 -> 15 -> 16

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Package & CLI | v1.0 | 3/3 | Complete | 2026-01-23 |
| 2. Database & Jobs | v2.0 | 2/2 | Complete | 2026-01-23 |
| 3. Background Worker | v2.0 | 1/1 | Complete | 2026-01-23 |
| 4. API Core | v2.0 | 2/2 | Complete | 2026-01-23 |
| 5. CLI Integration | v2.0 | 2/2 | Complete | 2026-01-23 |
| 6. YouTube Download | v2.1 | 2/2 | Complete | 2026-02-01 |
| 7. CLI & API Integration | v2.1 | 3/3 | Complete | 2026-02-01 |
| 8. Error Handling & Documentation | v2.1 | 2/2 | Complete | 2026-02-01 |
| 9. Configuration System | v2.2 | 2/2 | Complete | 2026-02-01 |
| 10. Speaker Diarization Core | v2.2 | 2/2 | Complete | 2026-02-01 |
| 11. Orchestration & Formatting | v2.2 | 2/2 | Complete | 2026-02-01 |
| 12. CLI Integration | v2.2 | 1/1 | Complete | 2026-02-01 |
| 13. API Integration | v2.2 | 3/3 | Complete | 2026-02-01 |
| 14. WhisperX Foundation | v2.3 | 3/3 | Complete | 2026-02-02 |
| 15. Orchestrator Simplification | v2.3 | 3/3 | Complete | 2026-02-02 |
| 16. Interface Verification | v2.3 | 3/3 | Complete | 2026-02-02 |
