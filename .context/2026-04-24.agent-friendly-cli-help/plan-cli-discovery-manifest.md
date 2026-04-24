---
status: completed
date: 2026-04-24
subject: 2026-04-24.agent-friendly-cli-help
topics: [cli-discovery, json, automation]
research: []
spec:
memory: [cli-discovery-manifest-2026-04-24.md]
---

# Plan: CLI Discovery Manifest

## Goal
Add a machine-readable CLI discovery surface so agents can inspect Cesar capabilities without scraping human help text.

## Scope
- **In scope**: a discovery command, JSON manifest output, clean output in no-config environments, tests, README note.
- **Out of scope**: general `--json-help` support on every command, API schema changes, execution behavior changes.

## Affected Files
- `cesar/cli.py` - add `commands` command and manifest helpers.
- `tests/test_cli.py` - validate text and JSON discovery output.
- `README.md` - document the new discovery command.

## Implementation Steps
1. Add a small manifest builder based on Click command metadata plus agent-specific examples.
2. Expose it via `cesar commands` and `cesar commands --json`.
3. Suppress config noise for discovery output so JSON stays parseable.
4. Verify tests and direct CLI invocation.

## Verification
- [x] `python -m pytest tests/test_cli.py -q`
- [x] `python -m cesar.cli commands --json`
- [x] `python -m cesar.cli commands`
- [x] `python -m cesar.cli -h`
