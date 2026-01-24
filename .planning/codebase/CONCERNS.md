# Codebase Concerns

**Analysis Date:** 2026-01-23

## Tech Debt

**Broken Test Suite in `tests/` Directory:**
- Issue: The entire `tests/` directory contains tests that import non-existent functions from `transcribe.py`
- Files: `tests/test_parallel_processing.py`, `tests/test_model.py`, `tests/test_validation.py`, `tests/test_transcription.py`
- Impact: These tests cannot run and fail immediately with ImportError. Functions like `get_audio_duration`, `should_use_parallel_processing`, `initialize_whisper_model`, `validate_input_file`, `transcribe_audio` do not exist in `transcribe.py`
- Fix approach: Either remove orphaned tests or implement the missing functions. The tests appear to reference a previous architecture where `transcribe.py` contained more logic (now in `transcriber.py`, `cli.py`)

**Duplicate Test Files:**
- Issue: Test files exist in both root and `tests/` directories with overlapping coverage
- Files: `test_cli.py` (root, 389 lines) vs `tests/test_cli.py` (42 lines); `test_transcriber.py` (root) covers what `tests/test_transcription.py` and `tests/test_validation.py` attempted
- Impact: Confusion about which tests are authoritative; broken tests in `tests/` directory
- Fix approach: Remove `tests/` directory or update imports to use the modular architecture (`transcriber.AudioTranscriber`)

**Parallel Processing Feature Incomplete:**
- Issue: `tests/test_parallel_processing.py` tests a parallel chunking feature that was never implemented
- Files: `tests/test_parallel_processing.py` (225 lines of dead code)
- Impact: Tests reference functions like `create_audio_chunks`, `transcribe_chunk`, `assemble_transcripts` that don't exist
- Fix approach: Either implement parallel processing or remove the test file. The functions would need to be added to the codebase.

**Environment Variable Side Effects:**
- Issue: `setup_environment()` modifies global environment variables (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`)
- Files: `device_detection.py:238-250`
- Impact: Can affect other processes or modules in the same Python session
- Fix approach: Consider using context managers or thread-local settings instead of global environment modification

## Known Bugs

**Variable Shadow in transcriber.py:**
- Symptoms: `start_time` variable is reassigned from function parameter to calculated value
- Files: `transcriber.py:200,215-216`
- Trigger: When `start_time_seconds` or `end_time_seconds` are provided, the local `start_time` (which was set to `time.time()` on line 200) is overwritten
- Workaround: The code works but naming is confusing. `transcription_start_time` would be clearer

**Progress Callback Uses Incorrect Variable:**
- Symptoms: Progress calculation uses `start_time` after it may have been reassigned
- Files: `transcriber.py:242`
- Trigger: When using `start_time_seconds` parameter, `elapsed_time` calculation uses the wrong value
- Workaround: None currently; bug affects progress reporting accuracy

## Security Considerations

**Subprocess Calls Without Input Sanitization:**
- Risk: File paths passed to subprocess commands (`ffprobe`, `nvidia-smi`, `nvcc`, `sysctl`) are not sanitized
- Files: `transcriber.py:146-150`, `device_detection.py:61,79,88,104`
- Current mitigation: Paths come from user input via CLI which validates file existence, but arbitrary path injection is possible
- Recommendations: Use `shlex.quote()` for paths or ensure paths are resolved to absolute paths within controlled directories

**No Shell=True Usage (Good):**
- All subprocess calls use explicit command lists without `shell=True`, reducing shell injection risk

## Performance Bottlenecks

**Model Loading on Every Transcription:**
- Problem: Model is loaded lazily but there's no caching across CLI invocations
- Files: `transcriber.py:45-72`
- Cause: CLI instantiates new `AudioTranscriber` per run; model loaded from disk each time
- Improvement path: Consider persistent model server or caching mechanism for batch processing scenarios

**Single-Threaded Transcription:**
- Problem: Large files are transcribed sequentially; no parallelization implemented
- Files: `transcriber.py:156-258`
- Cause: Parallel processing feature was planned (tests exist) but never implemented
- Improvement path: Implement chunk-based parallel transcription for files over 30 minutes (as designed in dead test code)

**FFprobe Called for Every Duration Check:**
- Problem: External ffprobe subprocess spawned for each audio file
- Files: `transcriber.py:132-154`
- Cause: No caching; duration calculated fresh each time
- Improvement path: Cache duration results or use Python libraries (e.g., `mutagen`) to avoid subprocess overhead

## Fragile Areas

**Device Detection Fallback Chain:**
- Files: `device_detection.py:53-110`, `transcriber.py:62-72`
- Why fragile: Multiple fallback attempts (torch -> nvidia-smi -> sysctl) with silent failures; difficult to diagnose why a particular device was selected
- Safe modification: Add logging at each fallback step; consider explicit device validation
- Test coverage: `test_device_detection.py` covers happy paths but edge cases (partial failures, timeout, permission errors) are sparse

**CLI Error Handling Duplication:**
- Files: `cli.py:258-299`
- Why fragile: Each exception type has duplicated console.print + click.echo pattern; easy to miss one when adding new error types
- Safe modification: Extract error handling to helper function
- Test coverage: Error paths tested but verbose mode traceback printing is not

**Progress Tracker Context Manager:**
- Files: `cli.py:28-67`
- Why fragile: Relies on Rich Progress internals; `__enter__` and `__exit__` delegation pattern
- Safe modification: Test with different terminal types (non-TTY, Windows)
- Test coverage: Indirectly tested through CLI tests; no unit tests for ProgressTracker class itself

## Scaling Limits

**Single File Processing:**
- Current capacity: One file at a time via CLI
- Limit: No batch processing capability; must invoke CLI repeatedly
- Scaling path: Add `--batch` mode or directory processing

**Memory Usage with Large Models:**
- Current capacity: Depends on device memory; "large" model requires 4GB+ GPU RAM
- Limit: Model loading can fail silently and fall back to CPU (slow)
- Scaling path: Better memory estimation and user warnings before loading

## Dependencies at Risk

**faster-whisper Version Pinning:**
- Risk: Pinned to 1.1.1; faster-whisper API may change in future versions
- Impact: Model loading and transcription calls may break
- Migration plan: Test with newer versions periodically; `model.transcribe()` API is stable

**Rich Library Heavy Usage:**
- Risk: Deep integration with Rich progress bars and console formatting
- Impact: Version updates could break output formatting
- Migration plan: Current version 14.0.0 is stable; consider abstracting Rich usage

**torch Dependency:**
- Risk: Large dependency (torch 2.7.1) only used for device detection
- Impact: Installation size bloated for users who only need CPU inference
- Migration plan: Make torch optional for device detection; fall back to system commands

## Missing Critical Features

**No Resume/Checkpoint Support:**
- Problem: If transcription fails mid-file, must restart from beginning
- Blocks: Processing very long files reliably

**No Language Detection Override:**
- Problem: Auto-detection only; cannot force specific language
- Blocks: Accurate transcription of multilingual or non-English content

**No Output Format Options:**
- Problem: Plain text only; no SRT, VTT, JSON timestamp formats
- Blocks: Use in video editing and subtitle workflows

## Test Coverage Gaps

**Untested: `tests/` Directory (100% Broken):**
- What's not tested: All tests in `tests/` directory fail to import
- Files: `tests/test_parallel_processing.py`, `tests/test_model.py`, `tests/test_validation.py`, `tests/test_transcription.py`
- Risk: Assumed test coverage that doesn't exist; CI may not be catching these failures
- Priority: High - either fix or remove

**Untested: Device Detection Edge Cases:**
- What's not tested: CUDA present but out of memory; MPS on Intel Mac; mixed GPU configurations
- Files: `device_detection.py`
- Risk: Unexpected device selection or crashes on non-standard hardware
- Priority: Medium

**Untested: Progress Callback Accuracy:**
- What's not tested: Progress percentage calculation correctness; update throttling
- Files: `transcriber.py:240-244`, `cli.py:56-67`
- Risk: Incorrect progress display; potential division by zero if audio_duration is 0
- Priority: Low

**Untested: Error Recovery:**
- What's not tested: What happens when transcription fails mid-file; partial output cleanup
- Files: `transcriber.py:226-245`
- Risk: Corrupted or incomplete output files without user notification
- Priority: Medium

**Untested: Concurrent Usage:**
- What's not tested: Multiple transcription instances; shared model; thread safety
- Files: `transcriber.py` (class-level state)
- Risk: Race conditions if used as library rather than CLI
- Priority: Low (CLI use case is single-threaded)

---

*Concerns audit: 2026-01-23*
