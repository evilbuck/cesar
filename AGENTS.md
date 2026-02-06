# AGENTS.md

This file provides guidance to agentic coding agents working with the Cesar repository.

## Project Overview

Cesar is an offline audio transcription CLI tool using faster-whisper. The project implements a modular Python application that transcribes audio files completely offline after initial setup.

## Core Architecture

- **Modular design**: Separated CLI interface from core transcription logic
- **CLI Framework**: Click-based command line interface with Rich formatting
- **Core Library**: `AudioTranscriber` class for transcription functionality
- **Target platform**: Cross-platform with optimized CPU processing
- **Offline-first**: No internet required after initial model download

## File Structure

- `cesar/cli.py`: Click-based command line interface with Rich formatting
- `cesar/transcriber.py`: Core `AudioTranscriber` class and transcription logic
- `cesar/orchestrator.py`: Orchestrates transcription and formatting pipeline
- `cesar/diarization.py`: Speaker diarization types and exceptions
- `cesar/whisperx_wrapper.py`: WhisperX pipeline wrapper
- `cesar/device_detection.py`: Device capabilities detection
- `cesar/youtube_handler.py`: YouTube audio download functionality
- `cesar/transcript_formatter.py`: Transcript formatting utilities
- `cesar/api/`: FastAPI server implementation
- `tests/`: Comprehensive unit tests

## Build/Test Commands

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run single test file
python -m pytest tests/test_cli.py

# Run single test method
python -m pytest tests/test_cli.py::TestCLI::test_cli_help

# Run with verbose output
python -m pytest tests/ -v

# Stop on first failure
python -m pytest tests/ -x

# Run with coverage (if pytest-cov installed)
python -m pytest tests/ --cov=cesar
```

### Development Commands
```bash
# Install dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"

# Run the CLI tool
python -m cesar.cli --help

# Run the API server
python -m cesar.api.server
```

## Code Style Guidelines

### Imports
- Use standard library imports first, then third-party, then local imports
- Group imports by type with blank lines between groups
- Use absolute imports for local modules (e.g., `from cesar.transcriber import AudioTranscriber`)
- Avoid wildcard imports (`from module import *`)

```python
# Standard library imports
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Third-party imports
import click
import uvicorn
from rich.console import Console

# Local imports
from cesar.config import CesarConfig
from cesar.transcriber import AudioTranscriber
```

### Type Hints
- Use type hints for all function parameters and return values
- Use `Optional[T]` for nullable types
- Use `Union[T, U]` for multiple possible types
- Use `Dict[str, Any]` for generic dictionaries
- Use `Path` from pathlib instead of `str` for file paths

```python
def process_file(
    input_path: Path,
    output_path: Path,
    config: Optional[CesarConfig] = None
) -> TranscriptionResult:
    """Process audio file and return transcription result."""
    pass
```

### Naming Conventions
- **Classes**: PascalCase (e.g., `AudioTranscriber`, `DeviceDetector`)
- **Functions/Variables**: snake_case (e.g., `process_file`, `model_size`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `SUPPORTED_FORMATS`)
- **Private methods**: Prefix with underscore (e.g., `_load_model`)
- **Exceptions**: End with "Error" (e.g., `DiarizationError`, `ConfigError`)

### Error Handling
- Define custom exception classes for domain-specific errors
- Use specific exception types instead of generic `Exception`
- Include meaningful error messages with context
- Handle expected errors gracefully with fallback logic

```python
class DiarizationError(Exception):
    """Base exception for diarization errors."""
    pass

class AuthenticationError(DiarizationError):
    """HuggingFace authentication failed."""
    pass

# Usage
raise AuthenticationError("HuggingFace token is invalid or missing")
```

### Docstrings
- Use triple quotes for all modules, classes, and public methods
- Include Args, Returns, and Raises sections where applicable
- Use Google-style docstring format

```python
class AudioTranscriber:
    """Core audio transcription class using faster-whisper

    Args:
        model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
        device: Device to use ('auto', 'cpu', 'cuda', 'mps')
        compute_type: Compute type ('auto', 'float32', 'float16', 'int8', 'int8_float16')
    """
    pass
```

### Configuration
- Use Pydantic models for configuration validation
- Store configuration in TOML files
- Use `ConfigDict` for Pydantic model configuration
- Implement field validators for complex validation logic

```python
class CesarConfig(BaseModel):
    """Configuration model for Cesar transcription settings."""
    
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True
    )
    
    diarize: bool = Field(
        False,
        description="Enable speaker identification (speaker labels in output)"
    )
```

### Logging
- Use the standard `logging` module
- Create module-level loggers: `logger = logging.getLogger(__name__)`
- Use appropriate log levels: DEBUG, INFO, WARNING, ERROR
- Include context in log messages

```python
import logging

logger = logging.getLogger(__name__)

# Usage
logger.info("Loading model %s on device %s", model_size, device)
logger.error("Failed to load model: %s", str(e))
```

### File I/O
- Use `pathlib.Path` for all file operations
- Handle file existence checks before operations
- Use context managers for file operations
- Clean up temporary files in tearDown methods

```python
from pathlib import Path

input_file = Path("audio.mp3")
if not input_file.exists():
    raise FileNotFoundError(f"Input file not found: {input_file}")

with input_file.open("rb") as f:
    data = f.read()
```

### Testing
- Use `unittest` for test cases
- Use `unittest.mock` for mocking external dependencies
- Test both success and failure scenarios
- Clean up temporary files in tearDown methods
- Use descriptive test method names

```python
class TestAudioTranscriber(unittest.TestCase):
    """Test AudioTranscriber functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.input_file = Path(self.temp_dir) / "test.mp3"
        self.input_file.touch()
    
    def tearDown(self):
        """Clean up test files"""
        shutil.rmtree(self.temp_dir)
    
    def test_transcribe_success(self):
        """Test successful transcription"""
        transcriber = AudioTranscriber()
        result = transcriber.transcribe(self.input_file)
        self.assertIsNotNone(result)
```

### Dependencies
- Use `pyproject.toml` for dependency management
- Group dependencies by type: core, development, optional
- Pin versions for stability
- Use `setuptools` for package building

### API Design
- Use FastAPI for HTTP endpoints
- Define Pydantic models for request/response schemas
- Use proper HTTP status codes
- Implement proper error handling with HTTPException

```python
@app.post("/transcribe", response_model=Job)
def transcribe(
    input_file: UploadFile = File(...),
    diarize: bool = Form(False)
) -> Job:
    """Start transcription job"""
    job = create_job(input_file, diarize)
    return job
```

### Performance
- Use streaming for large files
- Implement batch processing where appropriate
- Cache expensive computations
- Use appropriate data structures for performance

### Documentation
- Update README.md when adding new features
- Document API endpoints in docstrings
- Include usage examples in documentation
- Maintain changelog for version updates

## Development Workflow

1. Write tests first (TDD approach)
2. Implement functionality to pass tests
3. Add comprehensive error handling
4. Update documentation
5. Run full test suite before committing
6. Check code style and formatting

## Common Patterns

### Device Detection
```python
from cesar.device_detection import DeviceDetector

detector = DeviceDetector()
capabilities = detector.get_capabilities()
```

### Configuration Loading
```python
from cesar.config import load_config

config = load_config()
if config.diarize:
    # Enable diarization
    pass
```

### Error Handling Pattern
```python
try:
    result = process_file(input_path, output_path)
except FileNotFoundError as e:
    logger.error("Input file not found: %s", input_path)
    raise
except ProcessingError as e:
    logger.error("Processing failed: %s", str(e))
    raise
```

## Notes for Agents

- Always run tests after making changes
- Use `python -m pytest tests/test_file.py::TestClassName::test_method` for single test debugging
- Check `pyproject.toml` for dependency versions
- Use `pathlib.Path` for all file operations
- Follow the established error handling patterns
- Update documentation when adding new features
- Use the existing logging patterns throughout the codebase