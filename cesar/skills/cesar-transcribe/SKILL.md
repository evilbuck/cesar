---
name: cesar-transcribe
description: Transcribe audio and video files to text using Cesar, an offline CLI tool. Use when asked to transcribe, convert speech to text, generate transcripts, extract text from audio/video files, or process screen recordings for review. Supports local files (mp3, wav, m4a, mp4, etc.) and YouTube URLs. Produces plain text, speaker-labeled output, or agent-review packages with screenshots and sidecar metadata.
compatibility: Requires cesar installed (pipx install git+https://github.com/evilbuck/cesar.git) and FFmpeg on PATH.
---

Transcribe audio and video files using Cesar. Cesar runs completely offline after
the initial model download.

## When to use CLI vs API

- **CLI (`cesar transcribe`)**: Single files, scripts, pipelines. One invocation per file.
- **API (`cesar serve`)**: Multiple concurrent jobs, programmatic integration, async workflows.
- **Agent review (`--mode agent-review`)**: Screen recordings → transcript + screenshots + sidecar JSON.

## Quick reference

```bash
# Transcribe a local file (speaker labels enabled by default)
cesar transcribe meeting.mp3 -o meeting.md

# Plain text without speaker labels
cesar transcribe meeting.mp3 -o meeting.txt --no-diarize

# Transcribe a YouTube video
cesar transcribe "https://youtube.com/watch?v=VIDEO_ID" -o transcript.md

# Suppress progress output (useful in scripts)
cesar transcribe meeting.mp3 -o meeting.md --quiet

# Screen recording → agent-readable review with screenshots and sidecar
cesar transcribe review.mp4 -o review.md --mode agent-review

# Start HTTP API server
cesar serve --host 0.0.0.0 --port 5000

# Discover all commands and options
cesar commands --json
```

## Supported input formats

mp3, wav, m4a, flac, ogg, wma, aac, mp4, mkv, avi, mov, webm, and any format
supported by FFmpeg.

## Output formats

Use the output file extension to control format:
- `.txt` — plain text
- `.md` — markdown with optional speaker labels
- `.srt` — SubRip subtitle format
- `.vtt` — WebVTT subtitle format

## Key options

| Option | Effect |
|--------|--------|
| `-o PATH` | Output file path (required) |
| `--no-diarize` | Skip speaker identification, plain text only |
| `--mode MODE` | `transcription` (default) or `agent-review` |
| `--model SIZE` | Model: tiny, base, small, medium, large (default: base) |
| `--device DEVICE` | cpu, cuda, mps, auto (default: auto) |
| `--quiet` | Suppress progress bars and status output |
| `--verbose` | Show detailed logs including timestamps |
| `--language LANG` | Force language instead of auto-detect |

## Agent review mode (`--mode agent-review`)

For screen recordings where the speaker is narrating visual changes. Produces:

- `{name}.md` — Markdown transcript with screenshot references
- `{name}.sidecar.json` — Machine-readable metadata (segments, screenshots, associations)
- `{name}/images/` — Extracted screenshots

Screenshots are triggered by:
1. Time-based sampling (default: every 30s)
2. Speech cues (e.g., "this", "here", "look at", "issue")
3. Scene changes detected by FFmpeg

| Agent-review option | Effect |
|---------------------|--------|
| `--screenshots-interval N` | Seconds between time-based screenshots (default: 30) |
| `--speech-cues WORDS` | Comma-separated cue words (default list built-in) |
| `--scene-threshold N` | FFmpeg scene detection sensitivity 0.0-1.0 (default: 0.3) |
| `--no-scene-detection` | Disable scene change detection |

```bash
# Basic agent review
cesar transcribe review.mp4 -o review.md --mode agent-review

# Faster screenshots, custom cues
cesar transcribe review.mp4 -o review.md --mode agent-review \
  --screenshots-interval 15 --speech-cues "this,here,issue,bug"
```

## Gotchas

- **FFmpeg must be on PATH**. Without it, transcription and YouTube downloads fail.
- **First run downloads the model** (~150MB for base, up to ~3GB for large). Subsequent
  runs are fully offline.
- **YouTube downloads require FFmpeg** for audio extraction. Use `--quiet` in scripts to
  reduce noise during download.
- **Config not found is informational only**. Cesar works without a config file using
  sensible defaults.
- **Diarization requires a HuggingFace token**. Set `HF_TOKEN` env var or add
  `hf_token` to `~/.config/cesar/config.toml`. Without it, use `--no-diarize`.
- **Speaker labels are ON by default**. If the user doesn't mention speaker labels and
  you're unsure about their HF token setup, use `--no-diarize` to avoid auth errors.

## Recommended patterns

For most one-shot tasks:

```bash
cesar transcribe INPUT -o OUTPUT.md --no-diarize --quiet
```

When the user explicitly wants speaker labels and has HF token configured:

```bash
cesar transcribe INPUT -o OUTPUT.md --quiet
```

For programmatic discovery of all commands, options, and examples:

```bash
cesar commands --json
```

## Configuration

Optional config at `~/.config/cesar/config.toml`:

```toml
hf_token = "your_hf_token_here"  # For speaker identification
model_size = "base"               # Default model size
```

## Skill installation

```bash
# Install into current project
cesar skill install

# Install globally for all agent platforms
cesar skill install --global

# Install for specific platforms only
cesar skill install --global --platform pi --platform claude
```
