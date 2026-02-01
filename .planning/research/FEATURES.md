# Feature Research: Speaker Diarization & Configuration Systems

**Domain:** Offline transcription tool with speaker identification and config management
**Researched:** 2026-02-01
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist for speaker diarization and config systems. Missing these = product feels incomplete.

#### Speaker Diarization Features

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Basic speaker identification | Core diarization capability | MEDIUM | Pyannote 3.1 is standard, requires GPU or slow CPU processing (2-4 hours per 1 hour audio) |
| Speaker labels in output | Users need to know who spoke | LOW | Simple text formatting: `**[00:00:05] Speaker 1:** text` |
| Timestamps per speaker segment | Track when each speaker talked | LOW | Already have segment timestamps from transcription, need alignment |
| Auto-detect number of speakers | Most users don't know speaker count | MEDIUM | Pyannote handles this by default, though manual override improves accuracy |
| Offline operation | Matches project's core value | LOW | Pyannote models download to Hugging Face cache (~2-3GB), work offline after |
| Progress feedback | Diarization is slow, users need visibility | LOW | Existing Rich progress system extends easily |

#### Configuration System Features

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Config file in standard location | `~/.config/cesar/config.toml` is convention | LOW | Standard XDG Base Directory pattern |
| CLI args override config file | CLI should always have final say | LOW | Layered config: defaults → file → CLI args |
| Validation with clear errors | Prevent invalid config from breaking tool | LOW | Pydantic Settings handles this automatically |
| Defaults for all settings | Tool works without config file | LOW | Already have defaults in CLI args |
| Human-readable format | Users hand-edit config files | LOW | TOML is designed for this |
| Comments in config file | Users need to understand options | LOW | TOML supports comments natively |

### Differentiators (Competitive Advantage)

Features that align with project's "offline, no cloud services" core value and set it apart.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Fully offline diarization | No API keys, no cloud dependencies, no costs | MEDIUM | Pyannote Community-1 or 3.1 both work offline; most competitors require paid APIs |
| Markdown output format | Clean, readable transcripts with formatting | LOW | Format: `**[HH:MM:SS] Speaker N:** text` - integrates well with documentation workflows |
| Unified config for CLI + API | Single config file works for both interfaces | MEDIUM | Pydantic Settings can share config between FastAPI and Click |
| YouTube + diarization | Speaker ID works on YouTube videos too | LOW | Already have YouTube support; diarization works on any audio source |
| Speaker count hints | `--min-speakers`/`--max-speakers` improve accuracy | LOW | Pyannote supports these params; optional optimization |
| Fast CPU fallback | Picovoice Falcon: 100x faster on CPU | HIGH | Alternative to Pyannote for CPU-only users; separate integration |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems or scope creep.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time diarization | "I want live transcription with speakers" | Requires streaming architecture, buffering complexity, 10x effort | Process pre-recorded audio; defer to v3.0+ |
| Speaker name recognition | "Can it identify John vs Mary?" | Requires voice enrollment/training per speaker, not general-purpose | Use generic labels (Speaker 1/2/3); manual post-processing if needed |
| GUI config editor | "Command line is hard" | Adds Qt/Electron dependency, breaks offline-first simplicity | Document config file format; users edit with text editor |
| Per-project config files | "Different settings per transcription job" | Config scope confusion, adds `.cesar/config.toml` to every dir | Use CLI args for one-off overrides; global config for defaults |
| Automatic speaker labeling | "Tell me which speaker is which based on voice" | Requires speaker database/enrollment; overfitting to specific domains | Provide timestamps and generic labels; users add semantic meaning |
| Cloud model fallback | "Use better model if internet available" | Violates offline-first principle, unpredictable behavior | Pick one model, work offline always |
| SRT/VTT output with speakers | "I want subtitle files with speaker IDs" | Subtitle formats weren't designed for diarization; hacky workarounds | Markdown is primary output; add SRT export later if validated need |

## Feature Dependencies

```
[Existing: Transcription Engine (faster-whisper)]
    └──requires──> [Existing: Audio Input Handling]
    └──requires──> [Existing: Progress Display (Rich)]

[NEW: Speaker Diarization]
    └──requires──> [Existing: Transcription Engine]
    └──requires──> [NEW: Pyannote Integration]
    └──requires──> [NEW: Timestamp Alignment]
    └──enhances──> [Existing: Markdown Output]

[NEW: Configuration System]
    └──requires──> [NEW: TOML Parsing]
    └──requires──> [NEW: Pydantic Validation]
    └──enhances──> [Existing: CLI Interface]
    └──enhances──> [Existing: API Interface]

[NEW: Markdown Speaker Output]
    └──requires──> [NEW: Speaker Diarization]
    └──requires──> [Existing: Segment Timestamps]

[OPTIONAL: Speaker Count Hints]
    └──enhances──> [NEW: Speaker Diarization]
    └──conflicts──> [Auto-detect speakers] (mutually exclusive modes)
```

### Dependency Notes

- **Speaker Diarization requires Transcription Engine:** Diarization runs on same audio file; timestamps must align with transcription segments
- **Configuration System enhances both interfaces:** Both CLI and API read same config file for defaults
- **Markdown Speaker Output requires both features:** Can't format speaker labels without diarization data
- **Speaker Count Hints conflicts with Auto-detect:** When user provides `--num-speakers=3`, auto-detection is disabled (intentional override)

## MVP Definition

### Launch With (v2.2)

Minimum viable product — what's needed to validate speaker identification.

- [x] **Basic speaker diarization with auto-detection** — Core capability; Pyannote 3.1 default mode
- [x] **Markdown output with speaker labels** — Format: `**[00:00:05] Speaker 1:** text`
- [x] **Config file support (`~/.config/cesar/config.toml`)** — Standard location, TOML format
- [x] **CLI args override config** — Layered config hierarchy
- [x] **Validation errors for invalid config** — Pydantic Settings catches bad values
- [x] **Offline model download on first use** — Pyannote models auto-download to HuggingFace cache
- [x] **Works with all input sources** — Local files, URLs, YouTube (existing capabilities)
- [x] **Diarization enable/disable flag** — `--diarize` / `diarize: true` in config

### Add After Validation (v2.3+)

Features to add once core is working and validated.

- [ ] **Speaker count hints (`--min-speakers`, `--max-speakers`)** — Improves accuracy when user knows bounds
- [ ] **GPU detection and warnings** — Alert users that CPU diarization is slow (2-4 hrs per 1 hr audio)
- [ ] **Diarization-only mode** — Skip transcription, only identify speakers (niche use case)
- [ ] **API model selection parameter** — Allow API clients to choose model size (deferred from v2.0)
- [ ] **Config validation subcommand (`cesar config validate`)** — Check config file without running transcription

### Future Consideration (v3.0+)

Features to defer until product-market fit is established.

- [ ] **Picovoice Falcon integration** — 100x faster CPU diarization; validates CPU-only use case first
- [ ] **Pyannote Community-1 model** — Better accuracy than 3.1; needs validation of upgrade path
- [ ] **SRT/VTT export with speakers** — Non-standard format; validate demand first
- [ ] **Speaker clustering insights** — Who spoke most, speaking time percentages, etc.
- [ ] **Overlapping speech detection** — Advanced feature; pyannote supports it
- [ ] **Real-time streaming diarization** — Major architecture change; defer indefinitely

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Basic speaker diarization | HIGH | MEDIUM | P1 |
| Markdown speaker output | HIGH | LOW | P1 |
| Config file (TOML) | HIGH | LOW | P1 |
| CLI args override config | HIGH | LOW | P1 |
| Validation errors | MEDIUM | LOW | P1 |
| Offline model download | HIGH | LOW | P1 |
| Diarization enable/disable | MEDIUM | LOW | P1 |
| Speaker count hints | MEDIUM | LOW | P2 |
| GPU detection warnings | LOW | LOW | P2 |
| Diarization-only mode | LOW | MEDIUM | P2 |
| Config validation command | LOW | LOW | P2 |
| Picovoice Falcon (CPU perf) | MEDIUM | HIGH | P3 |
| Community-1 model upgrade | MEDIUM | MEDIUM | P3 |
| SRT/VTT export | LOW | MEDIUM | P3 |
| Speaker clustering insights | LOW | HIGH | P3 |
| Overlapping speech | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v2.2 launch
- P2: Should have, add in v2.3 when possible
- P3: Nice to have, future consideration

## Implementation Details

### Speaker Diarization Integration

**Approach:** Post-process transcription with pyannote pipeline

1. Run faster-whisper transcription (existing)
2. Run pyannote speaker diarization on same audio file
3. Align timestamps between transcription segments and speaker segments
4. Format output with speaker labels

**Why this approach:**
- Decoupled: transcription and diarization run independently
- Offline: both models cached locally
- Flexible: can enable/disable diarization without changing transcription
- Standard: matches WhisperX and other tools' architecture

**Alternative considered:** Whisper Speaker Identification (WSI) framework
- **Why not:** Too new (March 2025 research), not production-ready, unvalidated

### Configuration System Integration

**Approach:** Pydantic Settings with TOML source

1. Define `CesarConfig` Pydantic model with all CLI options
2. Use `TomlConfigSettingsSource` to load from `~/.config/cesar/config.toml`
3. Merge layers: defaults → config file → CLI args (highest priority)
4. Share config between CLI (Click) and API (FastAPI)

**Why this approach:**
- Validation: Pydantic catches invalid values automatically
- Type-safe: Config is strongly typed Python dataclass
- Standard: TOML is Python ecosystem standard (PEP 518)
- Unified: Single config works for both CLI and API

**File structure:**
```toml
# ~/.config/cesar/config.toml

[transcription]
model = "base"              # whisper model size
device = "auto"             # auto/cpu/cuda/mps
compute_type = "auto"       # auto/float32/int8

[diarization]
enabled = true              # enable speaker identification
min_speakers = 1            # optional: minimum speakers
max_speakers = 10           # optional: maximum speakers

[output]
format = "markdown"         # text/markdown
quiet = false               # suppress progress
verbose = false             # show detailed info
```

### Markdown Output Format

**Format specification:**

```markdown
# Transcription: example.mp3

**[00:00:05] Speaker 1:** Hello everyone, welcome to today's meeting.

**[00:00:12] Speaker 2:** Thanks for having me. I wanted to discuss the project timeline.

**[00:00:18] Speaker 1:** Of course, let's start with the current status.
```

**Design decisions:**
- Bold speaker labels for readability (`**[timestamp] Speaker N:**`)
- HH:MM:SS timestamp format (already used in existing output)
- Blank line between speaker turns (standard markdown paragraphs)
- Generic labels (Speaker 1/2/3) not names (no voice recognition)

**Fallback:** If diarization disabled or fails, output plain text without speaker labels (existing behavior)

## Competitor Feature Analysis

| Feature | AssemblyAI (Cloud) | WhisperX (OSS) | Deepgram (Cloud) | Cesar (Our Approach) |
|---------|-------------------|----------------|------------------|----------------------|
| Speaker diarization | ✓ 10 speakers max | ✓ Unlimited | ✓ Unlimited | ✓ Pyannote auto-detect |
| Offline operation | ✗ Cloud only | ✓ Local | ✗ Cloud only | ✓ Offline-first |
| Cost | $0.015/min | Free | $0.0125/min | Free |
| Config files | ✗ API params | ✗ CLI args only | ✗ API params | ✓ TOML config |
| Speaker count hints | ✓ API param | ✓ CLI arg | ✓ API param | ✓ Config + CLI |
| GPU acceleration | ✓ Cloud GPU | ✓ Local GPU | ✓ Cloud GPU | ✓ Local GPU/CPU |
| Markdown output | ✗ JSON/SRT/VTT | ✗ JSON | ✗ JSON | ✓ Primary format |
| YouTube support | ✗ Audio only | ✗ Audio only | ✗ Audio only | ✓ Direct URLs |

**Competitive advantage:**
1. **Offline operation:** Only WhisperX and Cesar work offline; we're more accessible (no Python required for WhisperX)
2. **Unified config:** No competitor has config files for defaults; all require API params or CLI args every time
3. **Markdown output:** Clean, readable format for documentation workflows; competitors focus on JSON/SRT
4. **YouTube integration:** Combined with diarization, unique capability

## Technical Constraints

### Performance Expectations

| Model | Hardware | Speed | Accuracy (DER) |
|-------|----------|-------|----------------|
| Pyannote 3.1 | GPU (CUDA) | ~10-30s per 1hr audio | 11-19% error |
| Pyannote 3.1 | CPU only | 2-4 hrs per 1hr audio | 11-19% error |
| Pyannote Community-1 | GPU (CUDA) | ~10-30s per 1hr audio | 8-15% error (improved) |
| Picovoice Falcon | CPU only | ~2.4 min per 1hr audio | Not benchmarked |

**DER = Diarization Error Rate** (lower is better)

**Implications for v2.2:**
- GPU is effectively required for practical use
- Must warn CPU users about expected processing time
- 10-19% error means ~1-2 speaker mistakes per 10-minute audio (acceptable for MVP)

### Storage Requirements

| Component | Size | Location |
|-----------|------|----------|
| Pyannote segmentation model | ~80MB | `~/.cache/huggingface/hub/` |
| Pyannote embedding model | ~17MB | `~/.cache/huggingface/hub/` |
| Pyannote pipeline config | ~1KB | `~/.cache/huggingface/hub/` |
| Total for diarization | ~100MB | Auto-downloaded on first use |

**Combined with existing:**
- Whisper base model: ~150MB
- Total storage for base + diarization: ~250MB

### Offline Operation Requirements

1. **First run (internet required):**
   - Accept Hugging Face model conditions (one-time)
   - Download pyannote models (~100MB)
   - Store in `~/.cache/huggingface/hub/`

2. **Subsequent runs (offline):**
   - Load models from cache
   - No internet required

**User flow:**
```bash
# First run: downloads models
cesar transcribe example.mp3 --diarize
# Prompt: "Speaker diarization requires downloading models (~100MB). Continue? [y/N]"

# Subsequent runs: works offline
cesar transcribe another.mp3 --diarize
```

## Known Limitations

### What We Can't Fix

1. **Speaker confusion with similar voices:** Pyannote struggles when 2+ speakers sound alike; accuracy degrades
2. **Overlapping speech (crosstalk):** Standard mode assigns one speaker per moment; overtalk creates errors or phantom speakers
3. **Short utterances (<1 second):** Diarization accuracy drops significantly for brief interjections
4. **Noisy environments:** Background noise reduces accuracy (though Community-1 improved this)
5. **CPU performance:** 2-4 hours processing time for 1 hour audio on CPU; fundamental model limitation

### What We Can Mitigate

1. **Speaker count accuracy:** Allow `--min-speakers` / `--max-speakers` hints (P2 feature)
2. **Progress visibility:** Show diarization progress separately from transcription (extend Rich UI)
3. **Failed diarization:** Gracefully fall back to plain transcript if diarization errors
4. **Config complexity:** Provide sensible defaults; advanced options are optional

## Sources

### Speaker Diarization
- [Pyannote Audio GitHub](https://github.com/pyannote/pyannote-audio)
- [Pyannote Community-1 Model](https://huggingface.co/pyannote/speaker-diarization-community-1)
- [Pyannote 3.1 Model](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [Best Speaker Diarization Models Compared 2026](https://brasstranscripts.com/blog/speaker-diarization-models-comparison)
- [Whisper Speaker Diarization Guide 2026](https://brasstranscripts.com/blog/whisper-speaker-diarization-guide)
- [Picovoice Falcon Speaker Diarization](https://picovoice.ai/blog/speaker-diarization/)
- [What is Speaker Diarization - AssemblyAI](https://www.assemblyai.com/blog/what-is-speaker-diarization-and-how-does-it-work)
- [Speaker Diarization Challenges and Pitfalls](https://www.mdpi.com/2076-3417/15/4/2002)

### Configuration Management
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [TOML Specification](https://toml.io/en/)
- [JSON vs YAML vs TOML 2026](https://dev.to/jsontoall_tools/json-vs-yaml-vs-toml-which-configuration-format-should-you-use-in-2026-1hlb)
- [Configuration File Best Practices](https://www.techtarget.com/searchdatacenter/tip/Best-practices-for-configuration-file-management)

### Integration Patterns
- [WhisperX GitHub](https://github.com/m-bain/whisperX)
- [Pyannote STT Orchestration](https://www.pyannote.ai/blog/stt-orchestration)
- [Whisper + Pyannote Integration](https://scalastic.io/en/whisper-pyannote-ultimate-speech-transcription/)

### Transcript Formatting
- [Understanding Timestamps and Speaker Labels](https://www.qualtranscribe.com/post/understanding-timestamps-speaker-labels-verbatim-formats)
- [Markdown Conversation Formatting](https://blog.jakelee.co.uk/markdown-conversation-formatting/)
- [Multi-Speaker Transcript Formats](https://brasstranscripts.com/blog/multi-speaker-transcript-formats-srt-vtt-json)
- [Transcription Formatting Best Practices](https://sonix.ai/resources/transcription-formatting/)

---
*Feature research for: Cesar v2.2 Speaker Identification*
*Researched: 2026-02-01*
*Confidence: HIGH (all claims verified with official documentation or multiple credible sources)*
