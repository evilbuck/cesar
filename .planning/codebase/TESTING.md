# Testing Patterns

**Analysis Date:** 2026-01-23

## Test Framework

**Runner:**
- unittest (Python standard library)
- pytest 8.4.0 also available in requirements.txt
- Config: No pytest.ini or pyproject.toml test config detected

**Assertion Library:**
- unittest assertions: `assertEqual`, `assertTrue`, `assertIn`, `assertRaises`, `assertGreater`
- Click testing: `CliRunner` from `click.testing`

**Run Commands:**
```bash
python test_utils.py         # Run single test file
python test_cli.py           # Run CLI tests
python test_transcriber.py   # Run transcriber tests
python test_device_detection.py  # Run device detection tests

# Using pytest (if preferred)
pytest                       # Run all tests
pytest -v                    # Verbose output
pytest tests/                # Run tests directory
```

## Test File Organization

**Location:**
- Root-level test files: `test_cli.py`, `test_transcriber.py`, `test_utils.py`, `test_device_detection.py`
- Legacy tests directory: `tests/` (contains older tests for previous architecture)

**Naming:**
- Test files: `test_<module>.py`
- Test classes: `Test<ClassName>` or `Test<Functionality>`
- Test methods: `test_<behavior_description>`

**Structure:**
```
cesar/
├── test_cli.py                    # CLI interface tests
├── test_transcriber.py            # Core transcriber tests
├── test_utils.py                  # Utility function tests
├── test_device_detection.py       # Device detection tests
└── tests/                         # Legacy tests directory
    ├── test_cli.py                # Old CLI tests (argparse based)
    ├── test_model.py              # Model initialization tests
    ├── test_parallel_processing.py # Parallel processing tests
    ├── test_transcription.py      # Transcription function tests
    └── test_validation.py         # Validation function tests
```

## Test Structure

**Suite Organization:**
```python
#!/usr/bin/env python3
"""Unit tests for the CLI module"""

import unittest
import tempfile
import os
from pathlib import Path
import sys

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from click.testing import CliRunner
from cli import main


class TestCLI(unittest.TestCase):
    """Test cases for the Click-based CLI"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_audio_file = Path("assets/nih_3min.mp3")
        self.temp_dir = tempfile.mkdtemp()
        self.temp_output = Path(self.temp_dir) / "test_cli_output.txt"

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_help_command(self):
        """Test CLI help command"""
        result = self.runner.invoke(main, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Transcribe audio files to text", result.output)


class TestCLIErrorHandling(unittest.TestCase):
    """Test CLI error handling scenarios"""
    # ... more tests


if __name__ == "__main__":
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCLI))
    suite.addTests(loader.loadTestsFromTestCase(TestCLIErrorHandling))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
```

**Patterns:**
- `setUp()`: Create temp directories, initialize test objects
- `tearDown()`: Clean up temp files with `shutil.rmtree()`
- Import shutil inside tearDown to avoid import issues
- Use `Path` objects for file paths

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patterns:**
```python
from unittest.mock import patch, MagicMock

class TestDeviceDetector(unittest.TestCase):

    @patch('os.cpu_count')
    def test_detect_capabilities_cpu_cores(self, mock_cpu_count):
        """Test CPU core detection"""
        mock_cpu_count.return_value = 8
        caps = self.detector._detect_capabilities()
        self.assertEqual(caps.cpu_cores, 8)

    @patch('device_detection.DeviceDetector._check_cuda')
    @patch('device_detection.DeviceDetector._check_mps')
    def test_detect_capabilities_no_gpu(self, mock_mps, mock_cuda):
        """Test capabilities detection with no GPU"""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        caps = self.detector._detect_capabilities()
        self.assertFalse(caps.has_cuda)

    @patch('subprocess.run')
    def test_get_audio_duration_success(self, mock_run):
        """Test successful audio duration detection"""
        mock_run.return_value.stdout = "1800.5\n"
        mock_run.return_value.returncode = 0
        duration = get_audio_duration("test.mp3")
        self.assertEqual(duration, 1800.5)
```

**What to Mock:**
- External processes: `subprocess.run` for ffprobe/ffmpeg calls
- System calls: `os.cpu_count()`, `platform.system()`
- Third-party libraries: `faster_whisper.WhisperModel`
- Time functions: `time.time()` for consistent test results
- Environment checks: CUDA/MPS detection

**What NOT to Mock:**
- Pure utility functions (test actual logic)
- File I/O for temp files (use real temp directories)
- Path operations (use pathlib normally)

## Fixtures and Factories

**Test Data:**
```python
def setUp(self):
    """Set up test fixtures"""
    # Temporary directory for test files
    self.temp_dir = tempfile.mkdtemp()
    self.temp_output = Path(self.temp_dir) / "test_output.txt"

    # Real test audio file (optional dependency)
    self.test_audio_file = Path("assets/nih_3min.mp3")

    # Initialize object under test
    self.transcriber = AudioTranscriber(model_size="tiny")
```

**Location:**
- Test fixtures created inline in `setUp()`
- Real test audio files in `assets/` directory: `assets/nih_3min.mp3`

**Mock Object Creation:**
```python
# Mock segment objects
mock_segment1 = MagicMock()
mock_segment1.text = "Hello world"
mock_segment1.end = 5.0
mock_segment2 = MagicMock()
mock_segment2.text = "This is a test"
mock_segment2.end = 10.0

# Mock transcription info
mock_info = MagicMock()
mock_info.language = "en"
mock_info.language_probability = 0.95
mock_info.duration = 10.0

# Configure mock model
mock_model.transcribe.return_value = ([mock_segment1, mock_segment2], mock_info)
```

## Coverage

**Requirements:** Not enforced - no coverage configuration detected

**View Coverage:**
```bash
# Install coverage if needed
pip install pytest-cov

# Run with coverage
pytest --cov=. --cov-report=html

# Or with unittest
coverage run -m unittest discover
coverage report
coverage html
```

## Test Types

**Unit Tests:**
- Test individual functions and methods in isolation
- Mock external dependencies
- Focus on single behavior per test
- Files: `test_utils.py`, `test_device_detection.py`

**Integration Tests:**
- Test component interactions
- Use real file system with temp directories
- Files: `test_transcriber.py`, `test_cli.py`

**Conditional Integration Tests (require real audio file):**
```python
@unittest.skipUnless(Path("assets/nih_3min.mp3").exists(), "Test audio file not available")
def test_full_transcription_workflow(self):
    """Test complete transcription workflow"""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        self.skipTest("faster-whisper not installed")

    # ... actual transcription test
```

**E2E Tests:**
- CLI tests using Click's `CliRunner`
- Test full command line invocation
- Verify exit codes, output messages, and file creation

## Common Patterns

**Skip Conditions:**
```python
# Skip if test file not available
@unittest.skipUnless(Path("assets/nih_3min.mp3").exists(), "Test audio file not available")

# Skip if dependency not installed
try:
    from faster_whisper import WhisperModel
except ImportError:
    self.skipTest("faster-whisper not installed")

# Skip on Windows
if os.name != 'nt':  # Different permission model
```

**Async Testing:**
- Not used in current codebase (synchronous code)
- pytest-asyncio available in requirements.txt for future use

**Error Testing:**
```python
def test_validate_input_file_not_exists(self):
    """Test input file validation with non-existing file"""
    with self.assertRaises(FileNotFoundError):
        self.transcriber.validate_input_file("nonexistent_file.mp3")

def test_validate_model_size_invalid(self):
    """Test model size validation with invalid inputs"""
    invalid_models = ["invalid", "huge", "mini", ""]
    for model in invalid_models:
        with self.assertRaises(ValueError) as context:
            validate_model_size(model)
        self.assertIn("Invalid model size", str(context.exception))
```

**CLI Testing with CliRunner:**
```python
def test_help_command(self):
    """Test CLI help command"""
    result = self.runner.invoke(main, ['--help'])
    self.assertEqual(result.exit_code, 0)
    self.assertIn("Transcribe audio files to text", result.output)

def test_nonexistent_input_file(self):
    """Test CLI with non-existent input file"""
    result = self.runner.invoke(main, [
        'nonexistent_file.mp3',
        '-o', str(self.temp_output)
    ])
    self.assertNotEqual(result.exit_code, 0)
    self.assertIn("does not exist", result.output)
```

**Environment Restoration:**
```python
def test_setup_environment(self):
    """Test environment variable setup"""
    original_omp = os.environ.get("OMP_NUM_THREADS")

    try:
        setup_environment(4)
        self.assertEqual(os.environ["OMP_NUM_THREADS"], "4")

    finally:
        # Restore original environment
        if original_omp is not None:
            os.environ["OMP_NUM_THREADS"] = original_omp
        elif "OMP_NUM_THREADS" in os.environ:
            del os.environ["OMP_NUM_THREADS"]
```

## Test Data Location

**Test Audio Files:**
- Location: `assets/nih_3min.mp3`
- ~3 minute audio file for integration tests
- Tests skip gracefully if not present

**Temporary Files:**
- Created with `tempfile.mkdtemp()` in `setUp()`
- Cleaned with `shutil.rmtree()` in `tearDown()`
- Always use `Path` objects for cross-platform compatibility

## Running Tests

**Run all root-level tests:**
```bash
python -m unittest test_*.py
```

**Run with verbosity:**
```bash
python test_cli.py  # Each file has its own runner with verbosity=2
```

**Run specific test class:**
```bash
python -m unittest test_cli.TestCLI
```

**Run specific test method:**
```bash
python -m unittest test_cli.TestCLI.test_help_command
```

---

*Testing analysis: 2026-01-23*
