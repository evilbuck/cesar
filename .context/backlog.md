# Backlog

## Details

### implement-cache-foundation
**Description**: Implement content-addressable storage for intermediate artifacts.
**Context**: 
- Phase 17 of v2.4.
- Requirements: CACHE-01, CACHE-02.
- Success criteria: Cache directory at ~/.cache/cesar/, atomic writes, YouTube audio retrieval, crash survival.
- **Plan**: See [17-cache-foundation-PLAN.md](.context/plans/17-cache-foundation-PLAN.md)

### fix-cli-test-failures
**Description**: Fix 6 failing tests in tests/test_cli.py related to YouTube error formatting and config loading.
**Context**: 
- Relevant files: `tests/test_cli.py`
- Failing tests:
  - `TestYouTubeErrorFormatting.test_non_verbose_hides_cause`
  - `TestYouTubeErrorFormatting.test_verbose_shows_cause`
  - `TestYouTubeErrorFormatting.test_verbose_without_cause_no_crash`
  - `TestYouTubeErrorFormatting.test_youtube_error_displays_message`
  - `TestCLIConfigLoading.test_cli_fails_on_invalid_config`
  - `TestCLIConfigLoading.test_cli_runs_without_config`
- Symptoms: Tests expect output containing 'YouTube Error:' or 'not found' but get empty string or full CLI help text instead
- Likely cause: CLI runner issue (click.testing.CliRunner) or error output formatting problem

## High Priority

## Medium Priority

## Completed
- [x] Fix CLI Test Failures (2026-03-27)

## Low Priority / Nice to Have

## Completed
- [x] Add machine-readable CLI discovery via `cesar commands --json` (2026-04-24)
- [x] Improve CLI help and `-h` support for agents (2026-04-24)
- [x] Implement Cache Foundation (2026-03-27)
- [x] Research v2.4 Cache Foundation (2026-03-27)
