# Architecture Patterns: Python CLI Package Structure

**Domain:** Python CLI packaging for audio transcription tool
**Researched:** 2026-01-23
**Confidence:** MEDIUM (based on training data, official docs unavailable for verification)

## Executive Summary

The cesar project needs to be restructured from flat Python files to a proper installable package. This document recommends the **src layout** with `pyproject.toml` as the single source of configuration, following modern Python packaging standards (PEP 517, PEP 518, PEP 621).

## Recommended Architecture

### Target Project Layout (src layout)

```
cesar/
├── pyproject.toml          # Single source of package configuration
├── README.md
├── LICENSE
├── requirements.txt        # Optional: for development pinning
├── src/
│   └── cesar/              # Package name
│       ├── __init__.py     # Package metadata (__version__, etc.)
│       ├── __main__.py     # python -m cesar support
│       ├── cli.py          # Click CLI interface
│       ├── transcriber.py  # Core AudioTranscriber class
│       ├── device_detection.py
│       └── utils.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Pytest fixtures
│   ├── test_cli.py
│   ├── test_transcriber.py
│   ├── test_device_detection.py
│   └── test_utils.py
├── docs/
│   └── ...
└── assets/
    └── testing speech audio file.m4a
```

### Why src Layout (Not Flat Layout)

| Criterion | src Layout | Flat Layout |
|-----------|------------|-------------|
| Import isolation | Tests import installed package, not local files | Tests may accidentally import local uninstalled code |
| Namespace clarity | Clear separation: source in src/, tests separate | Package mixed with config files |
| CI/CD reliability | `pip install .` must succeed for tests to pass | Can mask installation bugs |
| Industry adoption | Django, Flask, pytest, click all use src layout | Legacy projects |

**Recommendation:** Use src layout because it catches packaging errors during development rather than in production.

## Component Boundaries

| Component | File | Responsibility | Dependencies |
|-----------|------|----------------|--------------|
| Entry Point | `__main__.py` | `python -m cesar` support | cli |
| CLI Layer | `cli.py` | Argument parsing, Rich output, progress display | transcriber, utils |
| Core Engine | `transcriber.py` | Audio file transcription, model management | device_detection, faster-whisper |
| Device Layer | `device_detection.py` | Hardware detection, optimal config | torch (optional), subprocess |
| Utilities | `utils.py` | Time formatting, validation helpers | (none) |

### Dependency Flow

```
User Command
    │
    ▼
cli.py (Click + Rich)
    │
    ▼
transcriber.py (AudioTranscriber)
    │
    ├──► device_detection.py (OptimalConfiguration)
    │
    └──► faster-whisper (WhisperModel)
```

## Migration Plan from Current Structure

### Current Files → Target Locations

| Current Location | Target Location |
|------------------|-----------------|
| `transcribe.py` | DELETE (replaced by entry point) |
| `cli.py` | `src/cesar/cli.py` |
| `transcriber.py` | `src/cesar/transcriber.py` |
| `device_detection.py` | `src/cesar/device_detection.py` |
| `utils.py` | `src/cesar/utils.py` |
| `test_*.py` (root) | `tests/test_*.py` |
| `tests/test_*.py` | `tests/test_*.py` (consolidate) |

### Import Changes Required

Current imports (relative):
```python
# cli.py
from transcriber import AudioTranscriber
from utils import format_time, estimate_processing_time
```

Target imports (absolute within package):
```python
# cesar/cli.py
from cesar.transcriber import AudioTranscriber
from cesar.utils import format_time, estimate_processing_time
```

### New Files to Create

#### `src/cesar/__init__.py`
```python
"""
Cesar - Offline audio transcription using faster-whisper
"""
__version__ = "1.0.0"
__all__ = ["AudioTranscriber", "cli"]

from cesar.transcriber import AudioTranscriber
```

#### `src/cesar/__main__.py`
```python
"""
Entry point for python -m cesar
"""
from cesar.cli import main

if __name__ == "__main__":
    main()
```

#### `pyproject.toml`
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cesar"
version = "1.0.0"
description = "Offline audio transcription CLI using faster-whisper"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
keywords = ["transcription", "whisper", "audio", "speech-to-text", "cli"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Multimedia :: Sound/Audio :: Speech",
]

dependencies = [
    "faster-whisper>=1.0.0",
    "click>=8.0.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
cuda = [
    "torch>=2.0.0",
]

[project.scripts]
cesar = "cesar.cli:main"
transcribe = "cesar.cli:main"  # Backward compat alias

[project.urls]
Homepage = "https://github.com/user/cesar"
Documentation = "https://github.com/user/cesar#readme"
Repository = "https://github.com/user/cesar.git"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.black]
line-length = 100
target-version = ["py310", "py311", "py312"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "UP"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
```

## Entry Point Configuration

### Console Scripts (Recommended)

The `[project.scripts]` section in pyproject.toml creates console commands:

```toml
[project.scripts]
cesar = "cesar.cli:main"
```

After `pip install .`:
- User can run: `cesar input.mp3 -o output.txt`
- Equivalent to: `python -m cesar input.mp3 -o output.txt`

### Why Click's main() Works

Click commands decorated with `@click.command()` are callable. The entry point calls the function directly:

```python
# cesar/cli.py
@click.command(name="transcribe")
def main(...):
    ...

# Entry point calls cesar.cli:main which invokes the Click command
```

## Patterns to Follow

### Pattern 1: Lazy Loading Heavy Dependencies

**What:** Defer importing heavy libraries until actually needed
**When:** faster-whisper, torch are expensive to import
**Example:**
```python
# transcriber.py - current pattern (good)
def _load_model(self) -> None:
    if self.model is not None:
        return
    from faster_whisper import WhisperModel  # Lazy import
    self.model = WhisperModel(...)
```

### Pattern 2: Version Single Source of Truth

**What:** Define version once in `__init__.py`, reference elsewhere
**When:** Always
**Example:**
```python
# cesar/__init__.py
__version__ = "1.0.0"

# pyproject.toml uses dynamic versioning OR hardcoded (simpler)
[project]
version = "1.0.0"

# cli.py
from cesar import __version__

@click.version_option(version=__version__, prog_name="cesar")
def main(...):
```

### Pattern 3: Optional Dependencies with Graceful Fallback

**What:** Handle missing optional packages gracefully
**When:** torch is optional for CPU-only usage
**Current pattern (good):**
```python
# device_detection.py
def _check_cuda(self) -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        # Fallback to nvidia-smi check
        ...
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Relative Imports in Package

**What:** Using `from .transcriber import ...` inconsistently
**Why bad:** Can cause confusion between development and installed versions
**Instead:** Use explicit absolute imports: `from cesar.transcriber import ...`

### Anti-Pattern 2: Hardcoded Paths

**What:** Using `Path(__file__).parent / "assets"` for package data
**Why bad:** Doesn't work with installed packages
**Instead:** Use `importlib.resources` for package data:
```python
from importlib import resources
with resources.files("cesar").joinpath("data/file.txt").open() as f:
    ...
```

### Anti-Pattern 3: Multiple Entry Points with Duplicated Code

**What:** Having both `transcribe.py` and `__main__.py` with similar code
**Why bad:** Maintenance burden, potential for divergence
**Instead:** Single entry point in `cli.py`, thin wrappers only

## Build Order Implications

### Phase 1: Project Structure (do first)
1. Create `src/cesar/` directory
2. Move source files with updated imports
3. Create `__init__.py` and `__main__.py`
4. Create `pyproject.toml`

### Phase 2: Test Migration (do second)
1. Consolidate tests into `tests/`
2. Update test imports to use installed package
3. Create `conftest.py` for shared fixtures
4. Verify tests pass with `pip install -e .`

### Phase 3: Entry Points (do third)
1. Add `[project.scripts]` to pyproject.toml
2. Remove old `transcribe.py` entry point
3. Test `cesar` and `transcribe` commands work

### Phase 4: CI/CD Integration (do last)
1. Add GitHub Actions for testing
2. Add PyPI publishing workflow
3. Add version tagging

**Critical dependency:** Tests MUST run against installed package (`pip install -e .`), not local imports. This is enforced by src layout.

## Scalability Considerations

| Concern | Current State | After Restructure |
|---------|--------------|-------------------|
| Adding subcommands | Would need manual routing | Click groups: `@cli.group()` |
| Plugin architecture | Not possible | Entry points: `[project.entry-points."cesar.plugins"]` |
| Multiple output formats | Hardcoded in cli.py | Separate formatters in `cesar/formatters/` |
| Configuration files | Not supported | Add `cesar/config.py` with TOML/YAML support |

## Testing Strategy

### Recommended Test Structure

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── test_cli.py           # CLI integration tests
├── test_transcriber.py   # Core transcription tests
├── test_device_detection.py
├── test_utils.py
└── fixtures/
    └── sample_audio.m4a  # Small test file
```

### Test Fixture Example (conftest.py)

```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_audio():
    """Path to sample audio file for testing"""
    return Path(__file__).parent / "fixtures" / "sample_audio.m4a"

@pytest.fixture
def tmp_output(tmp_path):
    """Temporary output file path"""
    return tmp_path / "output.txt"
```

## Sources

- Python Packaging Authority (PyPA) tutorials and guides
- PEP 517 (build system interface)
- PEP 518 (pyproject.toml build requirements)
- PEP 621 (project metadata in pyproject.toml)
- setuptools documentation

**Confidence note:** This document is based on training data as of May 2025. The patterns described are well-established (PEP 621 finalized in 2021), but specific pyproject.toml syntax should be verified against current setuptools/PyPA documentation before implementation.
