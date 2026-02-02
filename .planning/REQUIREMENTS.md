# Requirements: Cesar v2.3 WhisperX Migration

**Defined:** 2026-02-01
**Core Value:** Transcribe audio to text anywhere, offline, with a single command or API call — no cloud services, no API keys, no ongoing costs

## v2.3 Requirements

Requirements for WhisperX migration milestone. Replaces pyannote diarization with WhisperX unified pipeline.

### Core Migration

- [ ] **WX-01**: Replace pyannote.audio diarization with WhisperX pipeline
- [ ] **WX-02**: Use wav2vec2 alignment for word-level timestamps
- [ ] **WX-03**: Delete timestamp_aligner.py module (WhisperX handles alignment)
- [ ] **WX-04**: Simplify orchestrator to use WhisperX unified pipeline
- [ ] **WX-05**: Update dependencies (add whisperx, update torch versions)

### Interface Preservation

- [ ] **WX-06**: CLI --diarize flag works unchanged
- [ ] **WX-07**: API diarize parameter works unchanged
- [ ] **WX-08**: Markdown output format preserved (speaker labels, timestamps)
- [ ] **WX-09**: Error handling interfaces preserved (DiarizationError, AuthenticationError)

### Quality

- [ ] **WX-10**: All existing diarization tests pass (with mock updates)
- [ ] **WX-11**: E2E test: CLI transcription with diarization produces correct output
- [ ] **WX-12**: E2E test: API job with diarization produces correct response

## Out of Scope

Explicitly excluded features with reasoning.

| Feature | Reason |
|---------|--------|
| Pyannote fallback backend | Complete replacement, simpler codebase |
| New CLI flags | Migration only, no new features |
| New API parameters | Migration only, no new features |
| Performance optimization | Validate baseline first, optimize later |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WX-01 | Phase 14: WhisperX Foundation | Pending |
| WX-02 | Phase 14: WhisperX Foundation | Pending |
| WX-03 | Phase 15: Orchestrator Simplification | Pending |
| WX-04 | Phase 15: Orchestrator Simplification | Pending |
| WX-05 | Phase 14: WhisperX Foundation | Pending |
| WX-06 | Phase 16: Interface Verification | Pending |
| WX-07 | Phase 16: Interface Verification | Pending |
| WX-08 | Phase 15: Orchestrator Simplification | Pending |
| WX-09 | Phase 15: Orchestrator Simplification | Pending |
| WX-10 | Phase 16: Interface Verification | Pending |
| WX-11 | Phase 16: Interface Verification | Pending |
| WX-12 | Phase 16: Interface Verification | Pending |

**Coverage:**
- v2.3 requirements: 12 total
- Mapped to phases: 12/12
- Unmapped: 0

---
*Requirements defined: 2026-02-01*
*Last updated: 2026-02-01 after roadmap creation*
