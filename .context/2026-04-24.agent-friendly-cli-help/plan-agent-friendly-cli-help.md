---
status: completed
date: 2026-04-24
subject: 2026-04-24.agent-friendly-cli-help
topics: [cli-help, agent-ux, click]
research: []
spec:
memory: [agent-friendly-cli-help-2026-04-24.md]
---

# Plan: Agent-Friendly CLI Help

## Goal
Make Cesar's built-in CLI help more useful for agents and humans, especially through `-h` / `--help`.

## Scope
- **In scope**: Click help aliases, richer command descriptions, example-driven help output, help-path dependency resilience.
- **Out of scope**: New machine-readable discovery commands, API redesign, transcription behavior changes.

## Affected Files
- `cesar/cli.py` - improve top-level and subcommand help, add `-h` aliases, lazy-load uvicorn.
- `cesar/youtube_handler.py` - allow help/import paths to work without `yt-dlp` installed.
- `tests/test_cli.py` - cover `-h` aliases and serve help behavior.

## Implementation Steps
1. Add shared Click context settings so `-h` works alongside `--help`.
2. Expand root, `transcribe`, and `serve` help text with workflows, automation tips, and examples.
3. Free `-h` for help by moving `serve --host` short flag to `-H`.
4. Lazy-load optional runtime dependencies so help works in minimal environments.
5. Verify with targeted CLI tests and direct `python -m cesar.cli ... -h` checks.

## Verification
- [x] `python -m pytest tests/test_cli.py -q`
- [x] `python -m cesar.cli -h`
- [x] `python -m cesar.cli transcribe -h`
- [x] `python -m cesar.cli serve -h`
