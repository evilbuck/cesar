# Plan: Agent tool discovery for Cesar CLI

## Goal
Make Cesar easy for coding agents to discover and invoke by building on the existing CLI first, then optionally adding machine-readable discovery if needed.

## Research Reference
- Research task: `buck-expert-researcher` task `ses_2cec76668ffeM8OnQ3RUnJ1bSK`
- Key finding: start with agent-focused docs + cleaner, example-rich CLI help; add a JSON discovery command later only if needed.

## Scope
- **In scope**:
  - Improve agent discoverability through repo instructions and CLI help.
  - Define a low-friction MVP that works with the existing `cesar` CLI.
  - Reserve a phase-2 path for machine-readable CLI discovery.
- **Out of scope**:
  - Wrapping Cesar as MCP in this iteration.
  - Changing core transcription behavior or API contracts. (**NOT DOING**)
  - Broad refactors unrelated to help text, docs, and discovery affordances.

## Affected Files
- `AGENTS.md` - add explicit agent usage guidance and command-selection instructions.
- `README.md` - add short automation/agent usage section.
- `cesar/cli.py` - improve top-level and subcommand help text; remove noisy output during `--help`.
- `tests/test_cli.py` - add or update tests for clean help output and discoverability-oriented examples.
- Optional later: `docs/agent-usage.md` or similar - deeper agent-oriented reference.

## Implementation Steps
1. **Document agent entry points in `AGENTS.md`**
   - Add a focused section like "Using Cesar from agents".
   - Include exact commands agents should prefer, such as:
     - local file transcription
     - YouTube transcription
     - disabling diarization
     - starting the API server
   - Include "use this when / do not use this when" guidance.

2. **Add a concise automation section to `README.md`**
   - Mirror the most important agent-usable commands.
   - Keep it short so it remains a human-readable landing page.
   - Point readers/agents to `AGENTS.md` for repo-specific operational guidance.

3. **Improve CLI help in `cesar/cli.py`**
   - Expand Click help/docstrings for `cli`, `transcribe`, and `serve`.
   - Add examples and clearer distinctions between one-shot CLI use vs API server use.
   - Prefer wording that helps tool selection by agents:
     - what the command does
     - what inputs it expects
     - when to use it
     - common flags

4. **Make `--help` output clean and parseable**
   - Ensure `cesar --help` and subcommand help do not print config-not-found chatter or unrelated startup noise.
   - Keep non-help informational output behind normal execution paths only.

5. **Add regression tests for discovery behavior**
   - Verify help commands succeed and remain quiet.
   - Verify example-oriented help text includes the intended command cues.
   - If existing CLI help tests are failing, fix/help-align them as part of the same pass only where directly relevant.

6. **Define phase 2 but do not implement unless needed**
   - Specify a future `cesar inspect --json` or `cesar manifest --json` command.
   - Proposed output should include command descriptions, option schema, examples, output expectations, and common failure cases.
   - Only prioritize this if docs + help do not yield reliable agent discovery.

## Risks
- `AGENTS.md` improves Buck/Codex-style workflows but is not a universal discovery standard.
- Help text can drift from real behavior if not covered by tests.
- Cleaning help output may intersect with existing CLI config-loading behavior and known CLI tests.
- A future JSON manifest adds maintenance burden if introduced too early.

## Verification
- [ ] `python -m cesar.cli --help` shows clean top-level help with no config warning chatter.
- [ ] `python -m cesar.cli transcribe --help` includes examples or clear usage cues for agents.
- [ ] `python -m cesar.cli serve --help` clearly distinguishes server/API usage from one-shot transcription.
- [ ] CLI tests covering help output pass.
- [ ] Manual prompt-set check succeeds for questions like:
  - How do I transcribe a local file?
  - How do I transcribe a YouTube URL?
  - How do I disable speaker labeling?
  - When should I use `serve` vs `transcribe`?

## Recommended Next Step
- **Use `/b-build-hard`**.
- Reason: this is still bounded, but it likely spans multiple files (`AGENTS.md`, `README.md`, `cesar/cli.py`, tests) and may interact with existing CLI behavior and test failures.
