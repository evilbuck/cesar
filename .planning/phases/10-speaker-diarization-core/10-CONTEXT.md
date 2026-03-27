# Phase 10: Speaker Diarization Core - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Identify speakers in audio using pyannote with timestamp alignment. The system must work completely offline after initial model download, detect speakers automatically or accept user-specified counts, and provide progress feedback during processing. This phase delivers the core diarization capability - formatting and CLI/API integration are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Model selection & offline behavior
- **Model choice:** Claude's discretion - choose best balance of accuracy, offline capability, and ease of setup
- **Model download:** Auto-download on first use with progress shown
- **Model storage:** Same location as whisper models (`~/.cache/huggingface/`)
- **Authentication:** Prompt for HuggingFace token interactively if missing, save to config, then retry download
- **Error handling:** If token missing or download fails, prompt user for token rather than failing immediately

### Speaker detection modes
- **Auto-detection:** Automatic with reasonable defaults - apply sensible constraints to prevent extreme cases
- **Default speaker range:** 1-5 speakers when user doesn't specify
- **Min/max constraints:** Treat as guidance hints to model, not hard constraints - allow flexibility if audio clearly shows different count
- **Single speaker handling:** Skip diarization output if only 1 speaker detected - output looks like normal transcription (no labels)

### Progress & feedback
- **Progress detail:** Simple phase indicator - just show "Detecting speakers..." with spinner
- **Progress UI:** Separate sequential steps - transcription progress first, then diarization progress
- **Time estimates:** Show estimated time remaining based on audio length and processing speed
- **Speaker count display:** Only show in final summary after completion (not real-time updates)

### Timestamp alignment strategy
- **Alignment approach:** Split segments at speaker changes - if speaker changes mid-segment, split that segment for accurate attribution
- **Overlapping speech:** Show as "Multiple speakers" when multiple speakers talk simultaneously
- **Timestamp precision:** Decisecond precision (00:05.2) - balances accuracy with readability
- **Misalignment handling:** Warn user and continue with best-effort alignment - log issues but complete the process

### Claude's Discretion
- Exact pyannote model version selection (2.1 vs 3.1)
- Specific implementation of progress time estimation algorithm
- Heuristics for best-effort alignment when timestamps don't match perfectly
- Exact threshold for what constitutes "significant misalignment" worthy of warning

</decisions>

<specifics>
## Specific Ideas

No specific requirements - open to standard approaches for speaker diarization with pyannote

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 10-speaker-diarization-core*
*Context gathered: 2026-02-01*
