# Coding Conventions

**Analysis Date:** 2026-01-23

## Naming Patterns

**Files:**
- Lowercase with underscores: `transcriber.py`, `device_detection.py`, `test_utils.py`
- Test files prefixed with `test_`: `test_cli.py`, `test_transcriber.py`
- Main entry point is `transcribe.py` which delegates to `cli.py`

**Functions:**
- snake_case for all functions: `format_time()`, `validate_input_file()`, `get_audio_duration()`
- Private methods prefixed with underscore: `_load_model()`, `_detect_capabilities()`, `_check_cuda()`
- Validation functions prefixed with `validate_`: `validate_model_size()`, `validate_device()`

**Variables:**
- snake_case for all variables: `model_size`, `compute_type`, `audio_duration`
- Constants as UPPER_SNAKE_CASE: `SUPPORTED_FORMATS`
- Loop variables can be single letter: `f` for file handles, `e` for exceptions

**Classes:**
- PascalCase: `AudioTranscriber`, `DeviceDetector`, `OptimalConfiguration`, `ProgressTracker`
- Dataclasses follow same convention: `DeviceCapabilities`

**Types:**
- Type hints used throughout: `Optional[str]`, `Dict[str, Any]`, `Callable[[float, int, float], None]`
- Union types: `Union[int, float]`

## Code Style

**Formatting:**
- Black and ruff are in `requirements.txt` for code formatting
- No explicit config files detected - using defaults
- 4-space indentation
- Double quotes for docstrings, single quotes acceptable for strings

**Linting:**
- ruff listed in requirements.txt
- mypy listed in requirements.txt for type checking
- isort for import sorting
- pre_commit framework available

## Import Organization

**Order:**
1. Standard library imports (`os`, `sys`, `time`, `subprocess`, `tempfile`, `pathlib`)
2. Third-party imports (`click`, `rich`, `unittest.mock`)
3. Local/project imports (`from transcriber import AudioTranscriber`)

**Path Aliases:**
- No path aliases configured
- Direct relative imports used: `from transcriber import AudioTranscriber`

**Example from `cli.py`:**
```python
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn
)

from transcriber import AudioTranscriber
from utils import format_time, estimate_processing_time
```

## Error Handling

**Patterns:**
- Use specific exception types: `FileNotFoundError`, `ValueError`, `PermissionError`, `RuntimeError`
- Re-raise with clear messages: `raise FileNotFoundError(f"Input file not found: {file_path}")`
- Catch multiple exceptions in CLI for user-friendly output
- Use `sys.exit(1)` for CLI errors

**CLI Error Handling Pattern (from `cli.py`):**
```python
try:
    # main logic
except FileNotFoundError as e:
    error_msg = f"Error: {e}"
    console.print(f"[red]{error_msg}[/red]")
    click.echo(error_msg, err=True)
    return 1
except ValueError as e:
    error_msg = f"Error: {e}"
    console.print(f"[red]{error_msg}[/red]")
    click.echo(error_msg, err=True)
    return 1
except KeyboardInterrupt:
    error_msg = "Transcription interrupted by user"
    console.print(f"\n[yellow]{error_msg}[/yellow]")
    return 1
except Exception as e:
    error_msg = f"Unexpected error: {e}"
    console.print(f"[red]{error_msg}[/red]")
    if verbose:
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
    return 1
```

**Model Loading Fallback Pattern (from `transcriber.py`):**
```python
try:
    self.model = WhisperModel(...)
except Exception as e:
    # Fallback to CPU with safe compute type
    self.device = "cpu"
    self.compute_type = "float32"
    self.batch_size = 1
    self.model = WhisperModel(...)
```

## Logging

**Framework:** Not using logging module - uses Rich console for output

**Patterns:**
- `console.print()` for user-facing messages with Rich markup
- `click.echo(..., err=True)` for plain text error output (testing compatibility)
- Color codes: `[red]` for errors, `[yellow]` for warnings, `[green]` for success, `[cyan]` for info
- Verbose mode shows additional detail via `--verbose` flag

**Console Output Pattern:**
```python
console = Console()

# Success messages
console.print(f"[bold green]✓ Transcription completed![/bold green]")

# Info messages
console.print(f"✓ Input file validated: [green]{input_file}[/green]")

# Warnings
console.print(f"[yellow]Warning: Could not determine audio duration: {e}[/yellow]")

# Verbose mode info
if verbose:
    console.print("\n[bold]Model Configuration:[/bold]")
    console.print(f"  Model size: [cyan]{model_info['model_size']}[/cyan]")
```

## Comments

**When to Comment:**
- Module-level docstrings at top of every file
- Class and method docstrings for public APIs
- Inline comments for non-obvious logic

**Docstring Format (Google style):**
```python
def transcribe_file(
    self,
    input_path: str,
    output_path: str,
    progress_callback: Optional[Callable[[float, int, float], None]] = None
) -> Dict[str, Any]:
    """
    Transcribe audio file to text

    Args:
        input_path: Path to input audio file
        output_path: Path to output text file
        progress_callback: Optional callback function for progress updates
                          Called with (progress_percentage, segment_count, elapsed_time)

    Returns:
        Dictionary with transcription results:
        {
            'language': str,
            'language_probability': float,
            ...
        }
    """
```

## Function Design

**Size:** Functions are focused and typically under 50 lines

**Parameters:**
- Use type hints for all parameters
- Default values where sensible: `model_size: str = "base"`
- Use `Optional[T]` for nullable parameters
- Group related options (e.g., device, compute_type, batch_size)

**Return Values:**
- Use type hints for return values: `-> Dict[str, Any]`, `-> str`, `-> Path`
- Return dictionaries for complex results (e.g., transcription result)
- Return Path objects when dealing with file paths

## Module Design

**Exports:**
- No `__all__` definitions - all public symbols are exported
- Private methods use underscore prefix: `_load_model()`

**Barrel Files:**
- Not used - direct imports from module files

**Module Organization:**
- `transcribe.py`: Entry point only
- `cli.py`: CLI interface with Click
- `transcriber.py`: Core `AudioTranscriber` class
- `utils.py`: Standalone utility functions
- `device_detection.py`: Device detection classes and functions

## Class Design

**Initialization Pattern:**
```python
class AudioTranscriber:
    SUPPORTED_FORMATS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma'}

    def __init__(self, model_size: str = "base", device: Optional[str] = None, ...):
        self.model_size = model_size
        self.config = OptimalConfiguration()
        self.device = self.config.get_optimal_device(device)
        # ... more initialization
        self.model = None  # Lazy loading
```

**Lazy Loading:**
- Models loaded on first use via `_load_model()` method
- Checked with `if self.model is not None: return`

**Dataclasses for Value Objects:**
```python
@dataclass
class DeviceCapabilities:
    has_cuda: bool = False
    has_mps: bool = False
    cuda_version: Optional[str] = None
    gpu_memory: Optional[int] = None
    cpu_cores: int = 1
    optimal_threads: int = 1
```

## CLI Design (Click Framework)

**Command Structure:**
```python
@click.command(name="transcribe")
@click.argument('input_file', type=click.Path(exists=True, readable=True, path_type=Path))
@click.option('-o', '--output', required=True, type=click.Path(path_type=Path), help='...')
@click.option('--model', type=click.Choice(['tiny', 'base', ...], case_sensitive=False), default='base')
@click.option('--verbose', '-v', is_flag=True, help='...')
@click.version_option(version="1.0.0", prog_name="transcribe")
def main(input_file, output, model, ...):
    """Command docstring shown in help"""
```

**Option Conventions:**
- Short and long forms: `-o`, `--output`
- Flags use `is_flag=True`: `--verbose`, `--quiet`
- Choices for constrained values: `type=click.Choice([...])`
- IntRange for numeric constraints: `type=click.IntRange(min=1, max=64)`

---

*Convention analysis: 2026-01-23*
