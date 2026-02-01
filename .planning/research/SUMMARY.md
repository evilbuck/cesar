# Project Research Summary

**Project:** Cesar v2.2 - Speaker Identification & Configuration Systems
**Domain:** Offline audio transcription with speaker diarization
**Researched:** 2026-02-01
**Confidence:** HIGH

## Executive Summary

Adding speaker diarization to Cesar requires integrating two major capabilities: speaker identification via pyannote.audio and a configuration system via Pydantic Settings with TOML. The research confirms this is well-trodden ground with established patterns, but success depends on avoiding critical pitfalls around timestamp alignment, memory management, and config validation.

**The recommended approach:** Sequential processing (transcribe first, diarize second, align timestamps, format as Markdown) using pyannote.audio 3.1+ with exclusive speaker mode. Configuration loads at system boundaries (CLI per-invocation, API at lifespan startup) with Pydantic validation. Both systems integrate as optional enhancements to existing AudioTranscriber without modification to core transcription logic.

**Key risks:** (1) Timestamp alignment between Whisper and pyannote segments can fail catastrophically if done manually — use pyannote's `exclusive=True` flag and temporal overlap algorithm, never manual reconciliation. (2) Dual model loading causes OOM crashes on target 8GB RAM systems — implement phased processing with sequential model loading/unloading and INT8 quantization. (3) Config validation happening during execution wastes user time — validate entire config at startup with Pydantic, fail fast with actionable errors.

## Key Findings

### Recommended Stack

pyannote.audio 3.1+ is the clear winner for offline speaker diarization in 2026. It runs fully offline after model download, uses pure PyTorch (no onnxruntime conflicts with faster-whisper), delivers excellent accuracy (DER ~11-19%), and has proven integration patterns with Whisper-family models. For configuration, Pydantic Settings 2.x provides type-safe settings with native TOML support, while tomli-w handles TOML writing (stdlib tomllib is read-only).

**Core technologies:**
- **pyannote.audio 3.1+**: Speaker diarization pipeline — best open-source option, runs offline, pure PyTorch, proven Whisper integration
- **pydantic-settings 2.x**: Type-safe config loader — native TOML/env/secrets support, integrates with existing Pydantic v2 stack
- **tomli-w 1.2+**: TOML file writer — complements stdlib tomllib (read-only), simple API matching json.dump pattern
- **torch 2.0+**: Deep learning framework — already in project (v2.7.1), required by pyannote, GPU-optional

**Critical version note:** pyannote.audio 3.0.0 had onnxruntime conflicts with faster-whisper. Use 3.1+ (pure PyTorch).

### Expected Features

**Must have (table stakes):**
- Basic speaker identification with auto-detection — core diarization capability users expect
- Speaker labels in output (Markdown format) — users need to know who spoke when
- Timestamps per speaker segment — track when each speaker talked
- Offline operation after model download — matches project's core offline-first value
- Config file in standard location (~/.config/cesar/config.toml) — XDG convention
- CLI args override config — CLI should always have final say
- Progress feedback — diarization is slow (2-4 hours on CPU), users need visibility

**Should have (competitive):**
- Fully offline diarization with no cloud dependencies — differentiates from cloud API competitors
- Markdown output format with speaker formatting — clean, documentation-friendly transcripts
- Unified config for CLI + API — single config file works for both interfaces
- YouTube + diarization — speaker ID works on YouTube videos (unique capability)
- Speaker count hints (--min-speakers/--max-speakers) — improves accuracy when user knows bounds

**Defer (v2+):**
- Real-time diarization — requires streaming architecture, 10x effort, defer to v3.0+
- Speaker name recognition — requires voice enrollment, not general-purpose, manual post-processing instead
- SRT/VTT export with speakers — non-standard format, validate demand first
- Picovoice Falcon integration — 100x faster CPU diarization, defer until CPU-only use case validated

### Architecture Approach

The architecture adds two major components without modifying existing AudioTranscriber: (1) TranscriptionOrchestrator coordinates optional processing steps (transcription → diarization → alignment → formatting), (2) ConfigManager loads and validates hierarchical config (defaults → file → env → CLI args). Sequential processing (not parallel) simplifies implementation and targets 8GB RAM systems. Models are lazy-loaded with explicit lifecycle management (load, use, unload, load next).

**Major components:**
1. **ConfigManager** — Load, merge, validate config hierarchy; Pydantic BaseSettings with custom source priority
2. **TranscriptionOrchestrator** — Coordinate transcription → diarization → alignment → formatting; wraps AudioTranscriber + SpeakerIdentifier
3. **SpeakerIdentifier** — Run pyannote.audio diarization, extract speaker segments; pyannote Pipeline API
4. **SegmentAligner** — Match transcription segments to speaker timestamps; temporal overlap algorithm
5. **MarkdownFormatter** — Format segments with speaker labels (SPEAKER_00, SPEAKER_01); unified formatter for both plain and diarized output

### Critical Pitfalls

1. **Timestamp reconciliation failure** — Whisper and pyannote have independent timing systems; manual timestamp merging causes 80% misattribution by end of file. **Avoid:** Use pyannote's `exclusive=True` flag, process in order (diarize → transcribe with context), never manually reconcile timestamps. Implement alignment verification tests with multi-speaker audio.

2. **Offline model download race conditions** — Both faster-whisper and pyannote download models simultaneously on first run; parallel downloads corrupt cache, partial downloads not re-downloaded on retry. **Avoid:** Implement explicit `cesar --install-models` command with sequential downloads, verify with checksums, store installation state in `~/.cache/cesar/installed-models.json`.

3. **Speaker count detection failures** — pyannote auto-detection splits one speaker into multiple labels or merges different speakers; setting `max_speakers=10` when only 2 speakers exist reduces accuracy. **Avoid:** Expose `num_speakers` and `max_speakers` as explicit config options, default to `num_speakers=2` for podcast use case, validate detected count against expected range.

4. **Config validation happens too late** — Validation occurs during execution (model path when loading model, speaker count when starting diarization); 45-minute job discovers invalid config at the end. **Avoid:** Use Pydantic models with strict type checking, validate entire config at startup, provide `cesar config validate` command.

5. **Memory explosion from dual model loading** — faster-whisper + pyannote simultaneously consume 6-8GB RAM; OOM crashes on 2-hour podcasts with 8GB systems. **Avoid:** Phased processing with explicit model lifecycle (load Whisper, transcribe, unload, load pyannote, diarize, unload), use INT8 quantization on CPU, implement memory budget checks at startup.

## Implications for Roadmap

Based on research, suggested phase structure prioritizes configuration foundation before ML integration, then builds diarization core before exposing to users.

### Phase 1: Configuration System
**Rationale:** Foundation for all new features; can ship independently; easier to test without ML models
**Delivers:** Config loading with TOML support, Pydantic validation, hierarchical precedence
**Addresses:** Config file support (FEATURES.md table stakes), validation errors for invalid config (FEATURES.md table stakes)
**Avoids:** Config validation too late (PITFALLS.md #4)

### Phase 2: Speaker Diarization Core
**Rationale:** Core logic independent of orchestration; establishes diarization API before integration; validates memory/performance characteristics on target hardware
**Delivers:** SpeakerIdentifier class with pyannote integration, SegmentAligner with temporal overlap algorithm
**Addresses:** Basic speaker identification (FEATURES.md table stakes), auto-detect speakers (FEATURES.md table stakes)
**Avoids:** Timestamp reconciliation failure (PITFALLS.md #1), speaker count detection failures (PITFALLS.md #3), memory explosion (PITFALLS.md #5), offline model download issues (PITFALLS.md #2)

### Phase 3: Orchestration & Formatting
**Rationale:** Integrates Phase 1 + Phase 2 outputs; sequential pipeline design; unified output formatter prevents format drift
**Delivers:** TranscriptionOrchestrator coordinating transcription → diarization → alignment, MarkdownFormatter for speaker-labeled output
**Addresses:** Markdown output with speaker labels (FEATURES.md table stakes), timestamps per speaker (FEATURES.md table stakes)
**Avoids:** Format inconsistency between plain and diarized output (PITFALLS.md #6)

### Phase 4: CLI Integration
**Rationale:** User-facing feature exposing all functionality; easiest to test manually; validates end-to-end flow
**Delivers:** `--diarize` flag, speaker config options, progress display for diarization step, result display with speaker count
**Addresses:** Diarization enable/disable flag (FEATURES.md MVP), progress feedback (FEATURES.md table stakes)

### Phase 5: API Integration
**Rationale:** Parallel to CLI (can swap order); more complex due to async job queue; shares orchestrator with CLI
**Delivers:** Speaker detection params in API endpoints, Job model updates, worker integration, API responses with speaker info
**Addresses:** API speaker identification support, works with all input sources (FEATURES.md differentiators)

### Phase Ordering Rationale

- **Config first:** Simplest component, no ML dependencies, foundation for feature flags and model selection
- **Diarization core before integration:** Validates pyannote behavior, memory requirements, and alignment algorithms on real hardware before exposing to users
- **Orchestration before interfaces:** Single implementation shared by CLI and API prevents duplication and format drift
- **CLI before API:** Simpler testing, fewer moving parts, validates full pipeline before adding async complexity
- **Dependencies:** Phase 1 is independent; Phase 2 depends on Phase 1 (config loading); Phases 3-5 depend on Phases 1-2

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Diarization Core):** Complex ML integration with memory/performance trade-offs — may need pyannote-specific research for optimization strategies
- **Phase 3 (Orchestration):** Alignment algorithm tuning for edge cases (crosstalk, silence, short utterances) — may need research-phase for WhisperX patterns

Phases with standard patterns (skip research-phase):
- **Phase 1 (Config):** Well-documented Pydantic Settings patterns, straightforward implementation
- **Phase 4 (CLI):** Click framework expertise already in project, standard flag additions
- **Phase 5 (API):** FastAPI expertise already in project, standard endpoint additions

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | pyannote.audio 3.1+ and Pydantic Settings 2.x are well-documented, widely adopted, verified with official sources |
| Features | HIGH | Table stakes and differentiators align with competitor analysis and user expectations from established tools |
| Architecture | HIGH | Sequential processing pattern is proven (WhisperX, whisper-diarization), config injection is standard Pydantic pattern |
| Pitfalls | HIGH | All critical pitfalls documented in real-world issue trackers (WhisperX #499, pyannote #1452) and practitioner blogs |

**Overall confidence:** HIGH

### Gaps to Address

- **CPU vs GPU performance trade-offs:** Research documents 2-4 hours CPU processing for 1 hour audio but doesn't provide detailed profiling data for different audio characteristics (silence ratio, speaker overlap, background noise). Address during Phase 2 implementation with profiling on diverse sample audio.

- **Alignment algorithm edge cases:** Temporal overlap algorithm is standard practice, but handling of crosstalk, silence gaps, and very short utterances (<1s) needs validation during Phase 2. May require tuning threshold parameters or implementing confidence scoring.

- **Speaker count validation heuristics:** Research suggests validating detected count against expected range (2-4 for podcasts) but doesn't specify when to trust auto-detection vs. requiring manual override. Address during Phase 2 with testing on diverse speaker counts.

- **Config migration strategy:** Initial config schema will evolve as features are added. Research doesn't address backward compatibility for config files when schema changes. Address during Phase 1 with versioning strategy (config_version field, migration utilities).

## Sources

### Primary (HIGH confidence)
- pyannote.audio GitHub (official) — Installation, offline usage, Python requirements
- speaker-diarization-3.1 on Hugging Face (official) — Model requirements, usage instructions, offline capabilities
- Pydantic Settings Documentation (official) — TOML support, validation patterns, settings hierarchy
- Python TOML libraries (official) — tomllib, tomli-w, tomlkit comparison
- WhisperX GitHub (reference implementation) — Integration patterns, alignment approaches, parallel vs. sequential processing

### Secondary (MEDIUM confidence)
- Best Speaker Diarization Models Compared 2026 (brasstranscripts.com) — Pyannote 3.1 vs alternatives, accuracy comparison
- Whisper Speaker Diarization: Python Tutorial 2026 (brasstranscripts.com) — Integration patterns, best practices
- Whisper and Pyannote: The Ultimate Solution for Speech Transcription (scalastic.io) — Integration architecture, alignment approaches
- pyannote.ai blog (STT Orchestration, Community-1 Release) — Advanced patterns, performance optimization
- WhisperX Issue #499 (GitHub) — pyannote 3.0 performance regression, version compatibility

### Tertiary (LOW confidence)
- pyannote-whisper GitHub (reference only) — Alternative integration approach, not production-ready
- Picovoice Falcon documentation — CPU-optimized alternative, not yet validated for this use case

---
*Research completed: 2026-02-01*
*Ready for roadmap: yes*
