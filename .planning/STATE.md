# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-01)

**Core value:** Transcribe audio to text anywhere, offline, with a single command or API call — no cloud services, no API keys, no ongoing costs
**Current focus:** Phase 13 - API Integration (in progress)

## Current Position

Phase: 13 of 13 (API Integration)
Plan: 3 of 3 (13-03 complete, 13-02 pending)
Status: In progress
Last activity: 2026-02-01 — Completed 13-03-PLAN.md

Progress: [████████████░░░░░░░░] 62% (26 of 42 total plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 26
- Average duration: ~3.0 min/plan (v2.1-v2.6)
- Total execution time: ~50 min total

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Package & CLI | 3 | - | - |
| 2. Database & Jobs | 2 | - | - |
| 3. Background Worker | 1 | - | - |
| 4. API Core | 2 | - | - |
| 5. CLI Integration | 2 | - | - |
| 6. YouTube Download | 2 | - | - |
| 7. CLI & API Integration | 3 | - | - |
| 8. Error Handling & Documentation | 2 | - | - |
| 9. Configuration System | 2 | 5min | 2.5min |
| 10. Speaker Diarization Core | 2 | 8min | 4min |
| 11. Orchestration & Formatting | 2 | 6min | 3min |
| 12. CLI Integration | 1 | 4min | 4min |
| 13. API Integration | 2/3 | 10min | 5min |

**Recent Trend:**
- Last 3 plans: 4min (12-01), 5min (13-01), 5min (13-03)
- Trend: Consistent execution pace

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v2.1: yt-dlp for YouTube downloads (only viable option, youtube-dl unmaintained)
- v2.1: m4a format for YouTube audio (smaller than wav, compatible with faster-whisper)
- v2.1: DOWNLOADING status for YouTube jobs (separate download from transcription phase)
- v2.0: Pydantic v2 models (validation, serialization, ConfigDict pattern)
- v2.0: SQLite for job persistence (no external dependencies, fits offline-first)
- v2.2: tomllib for TOML parsing (Python 3.11+ stdlib, no external dependency)
- v2.2: Separate config paths for CLI and API (user-wide vs project-specific)
- v2.2: Click context for config sharing (ctx.obj dict pattern)
- v2.2: FastAPI app.state for config storage (accessible to all endpoints)
- v2.3: pyannote.audio 3.1 for speaker diarization (industry-standard, offline-capable)
- v2.3: Token resolution hierarchy for HF auth (provided > env > cached)
- v2.3: Default speaker range 1-5 (prevents extreme auto-detection)
- v2.3: Lazy pipeline loading (defer model load until first use)
- v2.3: Temporal intersection for speaker alignment (more accurate than majority voting)
- v2.3: Segment splitting at speaker changes (proportional text distribution by time)
- v2.3: Overlapping speech threshold 500ms (mark as "Multiple speakers")
- v2.3: Decisecond timestamp precision (MM:SS.d format for readability)
- v2.4: Default minimum segment duration 0.5s (filters diarization artifacts)
- v2.4: Speaker label format "Speaker N" (human-friendly vs SPEAKER_XX)
- v2.4: Markdown section headers for speakers (### Speaker N)
- v2.4: Timestamps on separate line below speaker headers
- v2.4: Progress allocation 0-60% transcription, 60-90% diarization, 90-100% formatting
- v2.4: Transcription errors propagate, diarization/formatting errors trigger fallback
- v2.4: keep_intermediate flag for debug mode (saves transcription.txt + diarization.json)
- v2.4: Automatic file extension handling (.md for diarized, .txt for plain)
- v2.5: Default --diarize to True (users get speaker labels by default)
- v2.5: Auto-correct output extensions with user warning (.txt -> .md when diarize=True)
- v2.5: Pass min/max_speakers through orchestrate() not constructor
- v2.6: PARTIAL status for transcription OK, diarization failed (API partial failure handling)
- v2.6: diarize defaults to True in API (matches CLI behavior)
- v2.6: Progress tracking: overall, phase, phase_pct (API progress reporting)
- v2.6: diarized boolean flag for explicit fallback detection
- v2.6: Union[bool, DiarizeOptions] for flexible API diarize parameter
- v2.6: Retry endpoint only for PARTIAL status jobs

### Pending Todos

- Execute 13-02-PLAN.md (Worker Integration) - worker has config but doesn't use orchestrator yet

### Blockers/Concerns

- Pre-existing test failures in TestYouTubeErrorFormatting and TestCLIConfigLoading (mock issues with CliRunner)
- 13-02 (Worker Integration) not yet executed - worker imports but doesn't use orchestrator

## Session Continuity

Last session: 2026-02-01
Stopped at: Completed 13-03-PLAN.md (Server Endpoints)
Resume file: None
Next step: Execute 13-02-PLAN.md (Worker Integration)
