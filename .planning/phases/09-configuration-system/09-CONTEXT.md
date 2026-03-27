# Phase 9: Configuration System - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Load and validate hierarchical configuration from TOML files to control default behaviors across CLI and API. Users can set preferences (like speaker identification defaults) without passing flags every time. CLI loads from `~/.config/cesar/config.toml`, API loads from local `config.toml`. CLI arguments always override config values.

</domain>

<decisions>
## Implementation Decisions

### Config file structure
- **Flat structure**: All settings at root level (e.g., `diarize = true`, `min_speakers = 2`)
- **Scope for v2.2**: Only diarization settings (`diarize`, `min_speakers`, `max_speakers`)
- **Inline documentation**: Generated config includes comments explaining each setting and valid values
- **Startup check**: Check for config file on startup and prompt user to create if missing

### Validation behavior
- **Validation timing**: At startup/load time (fail fast)
- **Error handling**: Hard fail with clear error message explaining what's wrong and how to fix it
- **Error message style**: User-friendly with examples (e.g., "Invalid value for 'min_speakers': expected integer >= 1, got 'auto'. Example: min_speakers = 2")
- **Validation depth**: Full validation including:
  - Type checking (bool for `diarize`, int for speakers)
  - Range validation (min/max_speakers >= 1)
  - Logic checks (min_speakers <= max_speakers if both set)

### Default value strategy
- **Default location**: Defaults defined in code, but generated config shows all available settings with default values as comments
- **Missing config file**: Prompt to create `~/.config/cesar/config.toml` on first run with commented defaults
- **CLI override semantics**: CLI arguments always win - any CLI flag completely overrides the config value

### Claude's Discretion
- Specific default values for diarization settings (conservative disabled vs enabled with auto-detect)
- Implementation details of TOML parsing and loading
- Config file creation prompt UI/UX
- Directory creation if `~/.config/cesar/` doesn't exist

</decisions>

<specifics>
## Specific Ideas

- Config file should have helpful comments so users understand what each setting does without referring to docs
- Fail fast on invalid config - better to catch errors at startup than during transcription
- User-friendly error messages with examples make troubleshooting easier

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-configuration-system*
*Context gathered: 2026-02-01*
