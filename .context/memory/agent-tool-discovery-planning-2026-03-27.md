---
date: 2026-03-27
domains: [planning, docs, cli]
topics: [agent-discovery, cli-help, AGENTS-md, automation, tool-enablement]
related: [planning-cache-foundation-2026-03-27.md, research-2026-03-27.md]
priority: medium
status: active
---

# Session: 2026-03-27 - Agent Tool Discovery Planning

## Context
- Goal: Plan how to make Cesar easier for agents to discover and invoke.
- User wanted web-backed research and a bounded Buck workflow plan.

## Decisions Made
- Use the existing CLI as the primary agent entry point.
- Prioritize `AGENTS.md` guidance plus cleaner/example-rich Click help as the MVP.
- Defer machine-readable discovery (`--json`/manifest-style command) to a phase-2 option.
- Do not start with MCP wrapping.

## Implementation Notes
- Research delegated to `buck-expert-researcher` task `ses_2cec76668ffeM8OnQ3RUnJ1bSK`.
- Repo inspection confirmed existing surfaces:
  - `AGENTS.md`
  - `README.md`
  - `cesar/cli.py`
  - existing Click-based `cesar` CLI entrypoint in `pyproject.toml`
- Noted current issue: top-level CLI help prints config-not-found noise, which hurts agent parsing/discovery.

## Artifacts
- Saved plan: `.context/plans/agent-tool-discovery-plan-2026-03-27.md`

## Next Steps
- [ ] Execute the plan with `/b-build-hard`
- [ ] Update `AGENTS.md`, `README.md`, and `cesar/cli.py`
- [ ] Add/adjust CLI help tests for clean discovery behavior
- [ ] Re-evaluate whether a JSON discovery command is needed after MVP verification
