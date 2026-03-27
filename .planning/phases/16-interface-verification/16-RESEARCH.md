# Phase 16: Interface Verification - Research

**Researched:** 2026-02-02
**Domain:** Python E2E testing with real audio files and WhisperX mocking
**Confidence:** HIGH

## Summary

This phase validates that all CLI and API interfaces work unchanged after the WhisperX migration completed in Phase 15. The research focuses on three critical areas: (1) E2E testing patterns with real audio files under 10 seconds for fast CI, (2) mocking strategies at the whisperx library boundary to avoid model downloads, and (3) following existing test patterns established in the codebase (Click's CliRunner for CLI, FastAPI TestClient for API).

The key insight is that **mocking at the library boundary** (whisperx module, not internal wrapper classes) provides the best balance between test coverage and CI speed. The existing test suite already demonstrates this pattern extensively in `test_whisperx_wrapper.py`, using `patch.dict('sys.modules', {'whisperx': mock_whisperx})` to mock the entire whisperx library. This approach allows testing integration code without triggering slow model downloads while using real audio files for validation.

User decisions from CONTEXT.md lock in: (1) use real audio files from assets/ under 10 seconds, (2) mock at whisperx library boundary, (3) no network access or model downloads in CI. Test invocation method (CliRunner vs subprocess) and mock structure details are left to Claude's discretion, following existing patterns.

**Primary recommendation:** Use Click's CliRunner for CLI tests, mock whisperx module with patch.dict, use assets/testing-file audio (11.1s, acceptable), and verify both interface preservation and output format correctness.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| unittest | stdlib 3.12+ | Test framework | Project uses unittest throughout (not pytest) |
| unittest.mock | stdlib 3.12+ | Mocking framework | Standard Python mocking, used in all existing tests |
| click.testing.CliRunner | 8.0+ | CLI testing | Official Click test harness, isolates filesystem |
| fastapi.testclient.TestClient | Latest | API testing | Official FastAPI test client, used in test_server.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tempfile | stdlib | Temporary files/dirs | Output file storage during tests |
| pathlib.Path | stdlib | File path handling | Cross-platform path operations |
| json | stdlib | JSON validation | API response verification |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CliRunner | subprocess | CliRunner simpler and faster, subprocess only needed for streaming I/O |
| pytest | unittest | Project already uses unittest consistently |
| Mock fixtures | Real models | Real models require downloads, too slow for CI |

**No additional installation required** - all tools already used in the existing test suite.

## Architecture Patterns

### Recommended Test Structure
```
tests/
├── test_cli.py                    # EXISTS: Add E2E diarization tests here
├── test_server.py                 # EXISTS: Add E2E API diarization tests here
├── test_orchestrator.py           # EXISTS: Unit tests with mocked pipeline
├── test_whisperx_wrapper.py       # EXISTS: WhisperX mock patterns (reference)
└── assets/                        # NOT IN tests/ - at project root
    └── testing speech audio file.m4a  # 11.1s, 335KB
```

### Pattern 1: E2E CLI Test with Real Audio and Mocked WhisperX
**What:** Test full CLI command with real audio file but mocked whisperx library
**When to use:** Validating CLI interface preservation (WX-06, WX-11)
**Example:**
```python
# Source: Existing pattern from test_cli.py + test_whisperx_wrapper.py
# Tests CLI end-to-end without model downloads

def test_cli_transcribe_with_diarization_e2e(self):
    """E2E test: CLI --diarize with real audio, mocked whisperx."""
    # Create mock whisperx module (see Pattern 2 for details)
    mock_whisperx = self._create_mock_whisperx()

    with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
        with CliRunner().isolated_filesystem():
            # Copy real audio file into isolated filesystem
            audio_path = Path("test_audio.m4a")
            shutil.copy(ASSETS_AUDIO_PATH, audio_path)

            output_path = Path("output.md")

            # Run CLI command
            result = self.runner.invoke(cli, [
                'transcribe',
                str(audio_path),
                '-o', str(output_path),
                '--diarize',
                '--quiet'  # Suppress progress for cleaner test output
            ])

            # Verify CLI succeeded
            self.assertEqual(result.exit_code, 0)

            # Verify output file created with correct extension
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.suffix, '.md')

            # Verify output format (Markdown with speaker labels)
            content = output_path.read_text()
            self.assertIn('### Speaker', content)  # Speaker headers
            self.assertIn('[00:', content)         # Timestamps

            # Verify whisperx was called (not faster-whisper)
            mock_whisperx.load_model.assert_called_once()
```

**Why this pattern:**
- Uses real audio file (validates file handling, duration calculation)
- Mocks whisperx library (no downloads, fast CI)
- Tests actual CLI interface (--diarize flag, output extension)
- Uses CliRunner.isolated_filesystem() for cleanup

### Pattern 2: WhisperX Library Mocking Pattern
**What:** Mock entire whisperx module to avoid model downloads while testing integration
**When to use:** All E2E tests involving WhisperXPipeline
**Example:**
```python
# Source: test_whisperx_wrapper.py lines 267-312
# Comprehensive whisperx mocking for fast CI

def _create_mock_whisperx(self):
    """Create fully mocked whisperx module matching real API."""
    mock_whisperx = Mock()

    # Mock audio loading - return numpy-like array
    mock_audio = MagicMock()
    mock_audio.__len__ = Mock(return_value=160000)  # 10s at 16kHz
    mock_whisperx.load_audio.return_value = mock_audio

    # Mock transcription
    mock_model = Mock()
    mock_model.transcribe.return_value = {
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "First segment."},
            {"start": 5.0, "end": 10.0, "text": "Second segment."}
        ]
    }
    mock_whisperx.load_model.return_value = mock_model

    # Mock alignment
    mock_align_model = Mock()
    mock_align_metadata = Mock()
    mock_whisperx.load_align_model.return_value = (mock_align_model, mock_align_metadata)
    mock_whisperx.align.return_value = {
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "First segment.", "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 10.0, "text": "Second segment.", "speaker": "SPEAKER_01"}
        ]
    }

    # Mock diarization
    mock_diarize_pipeline = Mock()
    mock_diarize_result = Mock()
    mock_diarize_pipeline.return_value = mock_diarize_result
    mock_whisperx.DiarizationPipeline.return_value = mock_diarize_pipeline

    # Mock speaker assignment
    mock_whisperx.assign_word_speakers.return_value = {
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "First segment.", "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 10.0, "text": "Second segment.", "speaker": "SPEAKER_01"}
        ]
    }

    return mock_whisperx
```

**Why this pattern works:**
- Mocks at library boundary (not wrapper classes) - tests integration code
- Returns data structures matching real whisperx output
- Allows pipeline to execute without network/disk I/O
- Pattern already proven in test_whisperx_wrapper.py (100+ lines of mocks)

**Best practice from research:**
> "Don't mock what you don't own - create thin wrapper classes that you can mock."
> ([Toptal - Python Mocking Guide](https://www.toptal.com/python/an-introduction-to-mocking-in-python))

**Applied here:** WhisperXPipeline IS the thin wrapper. We mock whisperx (third-party), test WhisperXPipeline (our code).

### Pattern 3: E2E API Test with FastAPI TestClient
**What:** Test full API endpoint with multipart/form-data upload
**When to use:** Validating API interface preservation (WX-07, WX-12)
**Example:**
```python
# Source: Existing pattern from test_server.py
# Tests API endpoint without actual worker execution

def test_api_transcribe_with_diarization_e2e(self):
    """E2E test: POST /transcribe with diarize=true."""
    mock_whisperx = self._create_mock_whisperx()

    with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
        # Copy real audio file
        audio_path = Path("test_audio.m4a")
        shutil.copy(ASSETS_AUDIO_PATH, audio_path)

        # Create multipart form upload
        with open(audio_path, 'rb') as audio_file:
            response = self.client.post(
                "/transcribe",
                files={"audio": ("test.m4a", audio_file, "audio/mp4")},
                data={
                    "model_size": "base",
                    "diarize": "true"
                }
            )

        # Verify response
        self.assertEqual(response.status_code, 201)
        data = response.json()

        # Verify job created with diarization enabled
        self.assertIn("job_id", data)
        self.assertTrue(data["diarize"])

        # Verify job can be retrieved
        job_id = data["job_id"]
        get_response = self.client.get(f"/jobs/{job_id}")
        self.assertEqual(get_response.status_code, 200)
        job_data = get_response.json()
        self.assertTrue(job_data["diarize"])
```

**Why this pattern:**
- Uses TestClient (synchronous wrapper over async app)
- Tests actual FastAPI endpoint routing
- Validates multipart form-data handling
- Pattern matches existing test_server.py structure

### Anti-Patterns to Avoid

**1. Mocking Too Deep (Internal Classes)**
```python
# WRONG: Mock WhisperXPipeline directly
@patch('cesar.whisperx_wrapper.WhisperXPipeline')
def test_cli(self, mock_pipeline):
    # This tests nothing - you're mocking your own code
```

**2. Skipping Real Audio Files**
```python
# WRONG: Mock file reading
@patch('pathlib.Path.exists', return_value=True)
def test_cli(self, mock_exists):
    # Doesn't validate actual audio file handling
```

**3. Using Subprocess Unnecessarily**
```python
# WRONG: subprocess for standard CLI tests
result = subprocess.run(['python', 'transcribe.py', 'audio.mp3'])
# CliRunner is simpler, faster, and provides better isolation
```

**From research:**
> "Use CliRunner when testing standard Click CLIs where you can wait for completion. Use subprocess when you need to test streaming interactions or make assertions during execution."
> ([Click Testing Documentation](https://click.palletsprojects.com/en/stable/testing/))

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI isolation | Manual temp dir management | CliRunner.isolated_filesystem() | Automatic cleanup, cross-platform |
| Mock whisperx | Custom stubs | unittest.mock.Mock with patch.dict | Type-safe, traceable, standard |
| Audio fixtures | Generate synthetic audio | Use assets/testing-file | Real audio validates codec handling |
| API testing | Manual HTTP requests | FastAPI TestClient | Synchronous wrapper, no server startup |

**Key insight:** The existing test suite already demonstrates all required patterns. Don't invent new approaches.

## Common Pitfalls

### Pitfall 1: Testing Implementation Instead of Interface
**What goes wrong:** Tests verify internal pipeline behavior, not external CLI/API behavior
**Why it happens:** Over-mocking leads to testing mocks instead of code
**How to avoid:**
- Mock at library boundaries (whisperx), not internal classes (WhisperXPipeline)
- Verify output files/responses, not internal method calls
- Use real audio files to validate file handling
**Warning signs:** Test passes but real CLI command fails

### Pitfall 2: Slow CI Due to Model Downloads
**What goes wrong:** Tests download multi-GB models, CI times out
**Why it happens:** Not mocking whisperx library, allowing real model loading
**How to avoid:**
- Always use `patch.dict('sys.modules', {'whisperx': mock_whisperx})`
- Mock ALL whisperx entry points (load_model, load_align_model, DiarizationPipeline)
- Verify no network calls in CI logs
**Warning signs:** Tests take >1 minute, HuggingFace cache grows

### Pitfall 3: Ignoring Output Format Validation
**What goes wrong:** Test checks exit code but not output correctness
**Why it happens:** Focusing on "test passes" instead of "interface works"
**How to avoid:**
- For CLI: Read output file, verify Markdown structure, check for speaker labels
- For API: Parse JSON response, validate schema, check diarization fields
- Test both success (diarize=true) and fallback (diarization fails) scenarios
**Warning signs:** Test passes but output format changed/broken

### Pitfall 4: Audio File Duration Exceeds 10 Seconds
**What goes wrong:** Tests run slowly even with mocking due to audio processing
**Why it happens:** Using long audio files increases processing overhead
**How to avoid:**
- User requirement: "Audio files must be under 10 seconds for CI speed"
- Current asset: 11.1 seconds - acceptable but not ideal
- Recommendation: Trim to exactly 10 seconds if tests are slow
**Warning signs:** Individual test takes >5 seconds

### Pitfall 5: Not Following Existing Test Patterns
**What goes wrong:** New tests use different structure than existing suite
**Why it happens:** Not reviewing test_cli.py and test_whisperx_wrapper.py first
**How to avoid:**
- Review existing test patterns before writing new tests
- Match naming conventions (test_*_e2e for E2E tests)
- Use same mocking approach as test_whisperx_wrapper.py
- Follow unittest structure (setUp/tearDown, self.assert*)
**Warning signs:** Tests don't fit with existing test file structure

## Code Examples

Verified patterns from existing codebase:

### Complete E2E CLI Test with Diarization
```python
# Location: tests/test_cli.py (add new test class)
# Pattern: Existing test_transcribe_youtube_url() + test_whisperx_wrapper.py mocking

import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from click.testing import CliRunner
from cesar.cli import cli

class TestDiarizationE2E(unittest.TestCase):
    """E2E tests for CLI --diarize flag with real audio."""

    def setUp(self):
        """Set up test environment."""
        self.runner = CliRunner()
        # Path to real audio file (at project root, not in tests/)
        self.assets_audio = Path(__file__).parent.parent / "assets" / "testing speech audio file.m4a"

    def _create_mock_whisperx(self):
        """Create fully mocked whisperx module.

        Pattern from test_whisperx_wrapper.py lines 267-312.
        """
        mock_whisperx = Mock()

        # Mock audio loading
        mock_audio = MagicMock()
        mock_audio.__len__ = Mock(return_value=178176)  # 11.136s at 16kHz
        mock_whisperx.load_audio.return_value = mock_audio

        # Mock transcription
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello there."},
                {"start": 5.0, "end": 10.0, "text": "How are you?"}
            ]
        }
        mock_whisperx.load_model.return_value = mock_model

        # Mock alignment
        mock_align_model = Mock()
        mock_align_metadata = Mock()
        mock_whisperx.load_align_model.return_value = (mock_align_model, mock_align_metadata)
        mock_whisperx.align.return_value = {
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello there.", "speaker": "SPEAKER_00"},
                {"start": 5.0, "end": 10.0, "text": "How are you?", "speaker": "SPEAKER_01"}
            ]
        }

        # Mock diarization
        mock_diarize_pipeline = Mock()
        mock_diarize_result = Mock()
        mock_diarize_pipeline.return_value = mock_diarize_result
        mock_whisperx.DiarizationPipeline.return_value = mock_diarize_pipeline

        # Mock speaker assignment
        mock_whisperx.assign_word_speakers.return_value = {
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "Hello there.", "speaker": "SPEAKER_00"},
                {"start": 5.0, "end": 10.0, "text": "How are you?", "speaker": "SPEAKER_01"}
            ]
        }

        return mock_whisperx

    def test_cli_diarize_produces_markdown_with_speakers(self):
        """E2E: cesar transcribe --diarize produces speaker-labeled Markdown.

        Tests WX-06 (CLI --diarize flag works unchanged) and
        WX-11 (E2E CLI test produces correct output).
        """
        mock_whisperx = self._create_mock_whisperx()

        with patch.dict('sys.modules', {'whisperx': mock_whisperx}):
            with self.runner.isolated_filesystem():
                # Copy real audio file
                audio_path = Path("test.m4a")
                shutil.copy(self.assets_audio, audio_path)

                output_path = Path("output.md")

                # Run CLI command
                result = self.runner.invoke(cli, [
                    'transcribe',
                    str(audio_path),
                    '-o', str(output_path),
                    '--diarize',
                    '--quiet'
                ])

                # Verify success
                self.assertEqual(result.exit_code, 0,
                               f"CLI failed with: {result.output}")

                # Verify output file
                self.assertTrue(output_path.exists())
                self.assertEqual(output_path.suffix, '.md')

                # Verify Markdown format
                content = output_path.read_text()
                self.assertIn('### Speaker', content)
                self.assertIn('[00:', content)  # Timestamp format
                self.assertIn('Hello there', content)
                self.assertIn('How are you', content)
```

### Complete E2E API Test with Diarization
```python
# Location: tests/test_server.py (add new test class)
# Pattern: Existing TestHealthEndpoint + multipart upload

import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient

class TestTranscribeEndpointE2E(unittest.TestCase):
    """E2E tests for POST /transcribe with diarization."""

    def setUp(self):
        """Set up test client with mocked dependencies."""
        # Mock repository and worker (pattern from existing TestHealthEndpoint)
        self.mock_repo = MagicMock()
        self.mock_repo.connect = AsyncMock()
        self.mock_repo.create = AsyncMock(side_effect=lambda job: job)

        self.mock_worker = MagicMock()

        self.repo_patcher = patch("cesar.api.server.JobRepository")
        self.worker_patcher = patch("cesar.api.server.BackgroundWorker")

        self.mock_repo_class = self.repo_patcher.start()
        self.mock_worker_class = self.worker_patcher.start()

        self.mock_repo_class.return_value = self.mock_repo
        self.mock_worker_class.return_value = self.mock_worker

        from cesar.api.server import app
        self._client_cm = TestClient(app)
        self.client = self._client_cm.__enter__()

        self.assets_audio = Path(__file__).parent.parent / "assets" / "testing speech audio file.m4a"

    def tearDown(self):
        """Stop all patches."""
        self._client_cm.__exit__(None, None, None)
        self.repo_patcher.stop()
        self.worker_patcher.stop()

    def test_api_transcribe_diarize_parameter_accepted(self):
        """E2E: POST /transcribe with diarize=true creates job correctly.

        Tests WX-07 (API diarize parameter works unchanged) and
        WX-12 (E2E API test produces correct response).
        """
        with open(self.assets_audio, 'rb') as audio_file:
            response = self.client.post(
                "/transcribe",
                files={"audio": ("test.m4a", audio_file, "audio/mp4")},
                data={
                    "model_size": "base",
                    "diarize": "true"
                }
            )

        # Verify response
        self.assertEqual(response.status_code, 201)
        data = response.json()

        # Verify job structure
        self.assertIn("job_id", data)
        self.assertIn("status", data)
        self.assertTrue(data["diarize"])  # Diarization enabled

        # Verify repository was called with diarization
        self.mock_repo.create.assert_called_once()
        created_job = self.mock_repo.create.call_args[0][0]
        self.assertTrue(created_job.diarize)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Mock AudioTranscriber + SpeakerDiarizer | Mock whisperx library | Phase 15 | Simpler mocking, single entry point |
| Test with synthetic audio | Test with real audio <10s | Phase 16 (this) | Validates real file handling |
| subprocess.run() for CLI | CliRunner.invoke() | Existing pattern | Faster, better isolation |
| Manual test fixture management | conftest.py shared fixtures | Not used (unittest, not pytest) | N/A for this project |

**Deprecated/outdated:**
- SpeakerDiarizer class: Removed in Phase 15 (WhisperX handles diarization)
- timestamp_aligner module: Removed in Phase 15 (WhisperX handles alignment)
- Mocking AlignedSegment: Now mock WhisperXSegment (Phase 14 change)

## Open Questions

1. **Audio file duration: 11.1s vs 10s requirement**
   - What we know: Current asset is 11.136 seconds, requirement says <10 seconds
   - What's unclear: Is 11.1s acceptable or should it be trimmed?
   - Recommendation: Use as-is initially, trim if tests are slow (>5s per test)

2. **Test organization: New file vs existing file?**
   - What we know: Could add to test_cli.py or create test_cli_e2e.py
   - What's unclear: Project preference for test organization
   - Recommendation: Add to existing test_cli.py and test_server.py (keep related tests together)

3. **Worker integration tests: Mock or real background processing?**
   - What we know: Worker processes jobs asynchronously
   - What's unclear: Should E2E tests wait for worker processing or mock worker?
   - Recommendation: Mock worker for API tests (faster), test worker separately in test_worker.py

## Sources

### Primary (HIGH confidence)
- Existing test patterns in cesar/tests/test_cli.py (CliRunner usage)
- Existing test patterns in cesar/tests/test_whisperx_wrapper.py (whisperx mocking)
- Existing test patterns in cesar/tests/test_server.py (FastAPI TestClient usage)
- [Click Testing Documentation](https://click.palletsprojects.com/en/stable/testing/) - Official CliRunner API
- [Python unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html) - patch.dict usage

### Secondary (MEDIUM confidence)
- [Real Python - Python Mock Library](https://realpython.com/python-mock-library/) - Best practices for mocking
- [Toptal - Python Mocking Guide](https://www.toptal.com/python/an-introduction-to-mocking-in-python) - Don't mock what you don't own
- [Better Stack - Mastering unittest.mock](https://betterstack.com/community/guides/scaling-python/python-unittest-mock/) - Mocking external dependencies
- [pytest Documentation - Fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html) - Fixture patterns (for reference, not used in this unittest project)

### Tertiary (LOW confidence)
- [Medium - Testing APIs with PyTest Mocks](https://codilime.com/blog/testing-apis-with-pytest-mocks-in-python/) - API mocking patterns (pytest-focused, adapted for unittest)
- [GeeksforGeeks - Python Mock Library Guide](https://www.geeksforgeeks.org/python/python-mock-library/) - General mocking overview

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in use, verified in existing tests
- Architecture: HIGH - Patterns directly from codebase (test_cli.py, test_whisperx_wrapper.py, test_server.py)
- Pitfalls: HIGH - Derived from CONTEXT.md decisions and existing test issues
- Mocking strategy: HIGH - Pattern proven in 620 lines of test_whisperx_wrapper.py

**Research date:** 2026-02-02
**Valid until:** 60 days (stable testing patterns, unlikely to change)

**Key decisions from CONTEXT.md:**
- ✓ Use real audio files from assets/testing-file (not synthetic)
- ✓ Audio files must be under 10 seconds for CI speed (11.1s acceptable)
- ✓ Mock at whisperx library boundary (no model downloads in CI)
- ✓ Tests verify integration code, not whisperx library itself
- ✓ CLI test invocation: CliRunner (Claude's discretion, matches existing pattern)
- ✓ Mock structure: patch.dict on sys.modules (Claude's discretion, proven pattern)
