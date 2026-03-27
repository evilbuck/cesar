# Phase 16: Interface Verification - Context

**Gathered:** 2026-02-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate all CLI and API interfaces work unchanged with the new WhisperX backend. This is a verification phase — no new features, only confirming existing behavior is preserved after the migration.

</domain>

<decisions>
## Implementation Decisions

### E2E Test Approach
- Use real audio files from assets/testing-file (not synthetic)
- Audio files must be under 10 seconds for CI speed
- Mock at the whisperx library boundary (no real model downloads in CI)
- Tests verify integration code, not whisperx library itself

### Claude's Discretion
- CLI test invocation method (CliRunner vs subprocess — follow existing patterns)
- Specific test file selection from assets/
- Mock structure and fixture organization
- Whether to split unit vs integration test files

</decisions>

<specifics>
## Specific Ideas

- Priority is fast CI — tests should run quickly without network access or model downloads
- Real audio provides true validation that the pipeline handles actual audio correctly

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-interface-verification*
*Context gathered: 2026-02-02*
