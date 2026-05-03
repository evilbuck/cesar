---
name: cesar-transcribe
description: Transcribe audio and video files to text using Cesar, an offline CLI tool. Use when asked to transcribe, convert speech to text, generate transcripts, or extract text from audio/video files. Supports local files (mp3, wav, m4a, mp4, etc.) and YouTube URLs. Can produce plain text or speaker-labeled output.
compatibility: Requires cesar installed (pipx install git+https://github.com/evilbuck/cesar.git) and FFmpeg on PATH.
---

Transcribe audio and video files using Cesar. Cesar runs completely offline after
the initial model download.

## When to use CLI vs API

- **CLI (`cesar transcribe`)**: Single files, scripts, pipelines. One invocation per file.
- **API (`cesar serve`)**: Multiple concurrent jobs, programmatic integration, async workflows.

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
| `--model SIZE` | Model: tiny, base, small, medium, large (default: base) |
| `--device DEVICE` | cpu, cuda, mps, auto (default: auto) |
| `--quiet` | Suppress progress bars and status output |
| `--verbose` | Show detailed logs including timestamps |
| `--language LANG` | Force language instead of auto-detect |

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
