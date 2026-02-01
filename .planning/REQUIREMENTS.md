# Requirements: Cesar v2.2 Speaker Identification

**Defined:** 2026-02-01
**Core Value:** Transcribe audio to text anywhere, offline, with a single command or API call — no cloud services, no API keys, no ongoing costs

## v2.2 Requirements

Requirements for speaker identification and configuration system milestone.

### Speaker Diarization

- [ ] **DIAR-01**: User can enable speaker identification via CLI flag
- [ ] **DIAR-02**: User can enable speaker identification via API parameter
- [ ] **DIAR-03**: Transcript output includes speaker labels (Speaker 1, Speaker 2, etc.)
- [ ] **DIAR-04**: Transcript output includes timestamps for each speaker segment
- [ ] **DIAR-05**: Speaker-labeled output uses Markdown format with inline bold labels
- [ ] **DIAR-06**: Speaker identification works with local audio files
- [ ] **DIAR-07**: Speaker identification works with URL audio sources
- [ ] **DIAR-08**: Speaker identification works with YouTube videos
- [ ] **DIAR-09**: Speaker identification works offline after initial model download
- [ ] **DIAR-10**: User sees progress feedback during diarization process
- [ ] **DIAR-11**: User can specify minimum number of speakers
- [ ] **DIAR-12**: User can specify maximum number of speakers

### Configuration System

- [ ] **CONF-01**: CLI loads config from ~/.config/cesar/config.toml
- [ ] **CONF-02**: API loads config from local config.toml file
- [ ] **CONF-03**: Config file uses TOML format
- [ ] **CONF-04**: Config values are validated with clear error messages
- [ ] **CONF-05**: CLI arguments override config file values
- [ ] **CONF-06**: User can set default speaker identification behavior in config
- [ ] **CONF-07**: User can set speaker count defaults in config

## Future Requirements

Deferred to later milestones.

### Advanced Diarization

- **DIAR-20**: Real-time speaker identification during streaming
- **DIAR-21**: Speaker name recognition from voice enrollment
- **DIAR-22**: SRT/VTT export with speaker labels
- **DIAR-23**: Speaker embedding extraction for voice matching

### Advanced Configuration

- **CONF-20**: Config file migration utilities for schema changes
- **CONF-21**: Interactive config setup wizard
- **CONF-22**: Config validation command (cesar config validate)
- **CONF-23**: Multiple config profiles (development, production)

## Out of Scope

Explicitly excluded features with reasoning.

| Feature | Reason |
|---------|--------|
| Cloud-based speaker identification | Violates offline-first core value, ongoing API costs |
| Real-time diarization | Requires streaming architecture (10x effort), defer to v3.0+ |
| Speaker name recognition | Requires voice enrollment, not general-purpose |
| GUI config editor | CLI tool, config file editing is sufficient |
| Windows support | Focus on macOS/Linux first (existing constraint) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONF-01 | Phase 9 | Complete |
| CONF-02 | Phase 9 | Complete |
| CONF-03 | Phase 9 | Complete |
| CONF-04 | Phase 9 | Complete |
| CONF-05 | Phase 9 | Complete |
| CONF-06 | Phase 9 | Complete |
| CONF-07 | Phase 9 | Complete |
| DIAR-09 | Phase 10 | Complete |
| DIAR-10 | Phase 10 | Complete |
| DIAR-11 | Phase 10 | Complete |
| DIAR-12 | Phase 10 | Complete |
| DIAR-03 | Phase 11 | Pending |
| DIAR-04 | Phase 11 | Pending |
| DIAR-05 | Phase 11 | Pending |
| DIAR-01 | Phase 12 | Pending |
| DIAR-06 | Phase 12 | Pending |
| DIAR-02 | Phase 13 | Pending |
| DIAR-07 | Phase 13 | Pending |
| DIAR-08 | Phase 13 | Pending |

**Coverage:**
- v2.2 requirements: 19 total
- Mapped to phases: 19/19 (100%)
- Unmapped: 0

**Coverage verification:**
- Phase 9: 7 requirements (all CONF)
- Phase 10: 4 requirements (DIAR-09, DIAR-10, DIAR-11, DIAR-12)
- Phase 11: 3 requirements (DIAR-03, DIAR-04, DIAR-05)
- Phase 12: 2 requirements (DIAR-01, DIAR-06)
- Phase 13: 3 requirements (DIAR-02, DIAR-07, DIAR-08)
- Total: 19 requirements

---
*Requirements defined: 2026-02-01*
*Last updated: 2026-02-01 after roadmap creation (100% coverage validated)*
