# Phase 1: Package & CLI Structure - Research

**Researched:** 2026-01-23
**Domain:** Python packaging, Click CLI, pipx compatibility
**Confidence:** HIGH

## Summary

This phase transforms the existing flat Python scripts into an installable package with a global `cesar` command. The codebase already uses Click for the CLI, making the transition straightforward. The main work involves:

1. Creating a proper Python package structure with `pyproject.toml`
2. Refactoring the CLI from a flat command to a command group with subcommands
3. Registering the entry point for the `cesar` command
4. Implementing single-source versioning via `importlib.metadata`

The existing modular architecture (cli.py, transcriber.py, device_detection.py, utils.py) maps cleanly to a package structure. Tests are comprehensive and use Click's CliRunner, so they will continue to work after restructuring.

**Primary recommendation:** Use flat layout (not src layout) since the codebase already follows this pattern and has no namespace conflicts. Add pyproject.toml with setuptools build backend and `[project.scripts]` entry point.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| setuptools | >=61.0 | Build backend | Most widely used, stable, supports pyproject.toml natively |
| click | 8.x | CLI framework | Already in use, excellent subcommand support |
| importlib.metadata | stdlib | Version retrieval | Standard library since Python 3.8, no dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich | 13.x+ | Terminal formatting | Already in use for progress display |
| faster-whisper | 1.1.1 | Transcription engine | Core dependency, already in use |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| setuptools | hatchling | Hatch is newer but setuptools is more familiar, both work equally well |
| setuptools | poetry | Poetry adds dependency lock file, not needed for CLI tool |
| flat layout | src layout | src layout is cleaner for libraries, but flat is simpler for existing codebases |

**Installation:**
```bash
pipx install .
# or
pipx install git+https://github.com/username/cesar.git
```

## Architecture Patterns

### Recommended Package Structure (Flat Layout)

The existing flat structure should be maintained with minimal changes:

```
cesar/                         # Project root
├── pyproject.toml             # NEW: Package configuration
├── README.md                  # Existing
├── cesar/                     # NEW: Package directory (rename from flat files)
│   ├── __init__.py            # NEW: Package init with version
│   ├── __main__.py            # NEW: python -m cesar support
│   ├── cli.py                 # MOVE: from root
│   ├── transcriber.py         # MOVE: from root
│   ├── device_detection.py    # MOVE: from root
│   └── utils.py               # MOVE: from root
├── tests/                     # MOVE: consolidate test files
│   ├── __init__.py
│   ├── test_cli.py
│   ├── test_transcriber.py
│   ├── test_device_detection.py
│   ├── test_utils.py
│   └── ... (existing tests)
└── assets/                    # Existing: test audio files
```

### Pattern 1: Click Command Group with Subcommands

**What:** Convert flat `@click.command()` to `@click.group()` with subcommands
**When to use:** When CLI needs multiple commands (transcribe, future summarize)
**Example:**
```python
# Source: https://click.palletsprojects.com/en/stable/commands-and-groups/
import click
from importlib.metadata import version

@click.group()
@click.version_option(version=version("cesar"), prog_name="cesar")
def cli():
    """Cesar: Offline audio transcription"""
    pass

@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('-o', '--output', required=True, type=click.Path())
# ... other options
def transcribe(input_file, output, ...):
    """Transcribe audio files to text using faster-whisper"""
    # Implementation here
    pass
```

### Pattern 2: Single-Source Versioning

**What:** Version defined once in pyproject.toml, accessed via importlib.metadata
**When to use:** Always for CLI tools
**Example:**
```python
# Source: https://packaging.python.org/en/latest/discussions/single-source-version/
# In cesar/__init__.py
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("cesar")
except PackageNotFoundError:
    __version__ = "0.0.0"  # Development fallback
```

### Pattern 3: Entry Point Registration

**What:** Register console script in pyproject.toml
**When to use:** For global CLI commands
**Example:**
```toml
# Source: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
[project.scripts]
cesar = "cesar.cli:cli"
```

### Anti-Patterns to Avoid
- **Hardcoding version in multiple places:** Use importlib.metadata instead
- **Using __version__ in package directly:** Click 8.3+ deprecates this; use version() function
- **Mixing setup.py and pyproject.toml:** Use pyproject.toml exclusively for new packages
- **Complex lazy loading:** Not needed for small CLI; adds debugging complexity

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Version management | Custom version file parsing | `importlib.metadata.version()` | Standard, handles edge cases, works with pip |
| CLI argument parsing | argparse from scratch | Click (already used) | Declarative, composable, excellent error messages |
| Progress display | Custom terminal codes | Rich (already used) | Cross-platform, handles terminal quirks |
| Package discovery | Manual __init__.py listing | setuptools.packages.find | Auto-discovery prevents missing modules |

**Key insight:** The existing codebase already uses the right tools. The task is restructuring, not rewriting.

## Common Pitfalls

### Pitfall 1: Import Path Changes After Restructuring
**What goes wrong:** Tests fail because imports like `from cli import main` no longer work
**Why it happens:** Moving files into a package changes the import path
**How to avoid:** Update all imports to use package prefix: `from cesar.cli import cli`
**Warning signs:** `ModuleNotFoundError` in tests after restructuring

### Pitfall 2: Relative vs Absolute Imports
**What goes wrong:** Package works when installed but fails during development
**Why it happens:** Mixing relative and absolute imports inconsistently
**How to avoid:** Use absolute imports within the package: `from cesar.transcriber import AudioTranscriber`
**Warning signs:** Works in dev, fails when installed via pipx

### Pitfall 3: Missing __init__.py
**What goes wrong:** Submodules not discoverable, mysterious import failures
**Why it happens:** Forgetting __init__.py when creating package directory
**How to avoid:** Always create __init__.py, even if empty (though ours will have version)
**Warning signs:** `ModuleNotFoundError` for modules that clearly exist

### Pitfall 4: Version Not Available During Development
**What goes wrong:** `cesar --version` crashes during development without install
**Why it happens:** `importlib.metadata.version()` requires installed package
**How to avoid:** Use try/except with fallback version
**Warning signs:** `PackageNotFoundError` when running locally

### Pitfall 5: Entry Point Points to Wrong Function
**What goes wrong:** `cesar` command does nothing or errors immediately
**Why it happens:** Entry point string doesn't match actual function name/location
**How to avoid:** Triple-check: `cesar = "cesar.cli:cli"` means `cli` function in `cesar/cli.py`
**Warning signs:** Command installed but errors on invocation

## Code Examples

Verified patterns from official sources:

### pyproject.toml Complete Example
```toml
# Source: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "cesar"
version = "1.0.0"
description = "Offline audio transcription CLI using faster-whisper"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [
    {name = "Author Name", email = "author@example.com"}
]
keywords = ["transcription", "whisper", "audio", "speech-to-text", "offline"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Multimedia :: Sound/Audio :: Speech",
]
dependencies = [
    "click>=8.0.0",
    "rich>=13.0.0",
    "faster-whisper>=1.0.0",
]

[project.scripts]
cesar = "cesar.cli:cli"

[project.urls]
Homepage = "https://github.com/username/cesar"
Repository = "https://github.com/username/cesar.git"

[tool.setuptools.packages.find]
where = ["."]
include = ["cesar*"]
```

### CLI Entry Point (cesar/cli.py)
```python
# Source: https://click.palletsprojects.com/en/stable/commands-and-groups/
"""Click-based CLI for cesar audio transcription"""
import sys
from importlib.metadata import version
from pathlib import Path

import click
from rich.console import Console

from cesar.transcriber import AudioTranscriber
from cesar.utils import format_time, estimate_processing_time

console = Console()

@click.group()
@click.version_option(version=version("cesar"), prog_name="cesar")
def cli():
    """Cesar: Offline audio transcription using faster-whisper"""
    pass

@cli.command()
@click.argument(
    'input_file',
    type=click.Path(exists=True, readable=True, path_type=Path),
    metavar='INPUT_FILE'
)
@click.option(
    '-o', '--output',
    required=True,
    type=click.Path(path_type=Path),
    help='Path for the output text file'
)
# ... rest of existing options
def transcribe(input_file, output, ...):
    """Transcribe audio files to text using faster-whisper (offline)"""
    # Move existing main() body here
    pass
```

### Package __init__.py
```python
# Source: https://packaging.python.org/en/latest/discussions/single-source-version/
"""Cesar: Offline audio transcription CLI"""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("cesar")
except PackageNotFoundError:
    __version__ = "0.0.0"  # Development fallback
```

### __main__.py for python -m support
```python
"""Support for python -m cesar"""
from cesar.cli import cli

if __name__ == "__main__":
    cli()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| setup.py | pyproject.toml (PEP 621) | 2021/stable 2023 | All new packages should use pyproject.toml |
| __version__ attribute | importlib.metadata | Click 8.3 (May 2025) | Click deprecated __version__, use version() |
| setup.cfg | pyproject.toml | 2023 | setuptools fully supports pyproject.toml |

**Deprecated/outdated:**
- `setup.py` for simple packages: Use pyproject.toml instead
- `pkg_resources` for version: Use importlib.metadata (faster, stdlib)
- Click's `@click.version_option()` without explicit version: Must now pass version explicitly

## Open Questions

Things that couldn't be fully resolved:

1. **Test file organization**
   - What we know: Tests exist in both root (test_*.py) and tests/ directory
   - What's unclear: Are all tests duplicates, or do they serve different purposes?
   - Recommendation: Audit and consolidate into tests/ directory during restructure

2. **transcribe.py entry point**
   - What we know: Currently used as `python transcribe.py`
   - What's unclear: Should this file remain for backward compatibility?
   - Recommendation: Remove after package is working; document new usage

## Sources

### Primary (HIGH confidence)
- [Click Documentation - Commands and Groups](https://click.palletsprojects.com/en/stable/commands-and-groups/) - Subcommand patterns
- [Python Packaging Guide - Writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) - Complete pyproject.toml structure
- [Setuptools - Entry Points](https://setuptools.pypa.io/en/latest/userguide/entry_point.html) - Console scripts configuration
- [Python Packaging Guide - Single Source Version](https://packaging.python.org/en/latest/discussions/single-source-version/) - Version management

### Secondary (MEDIUM confidence)
- [Real Python - Click CLI](https://realpython.com/python-click/) - Practical Click examples
- [Python Packaging Guide - src vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) - Layout decisions

### Tertiary (LOW confidence)
- WebSearch results for pipx compatibility - General guidance, not official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official documentation for all tools
- Architecture: HIGH - Click official docs, Python packaging guide
- Pitfalls: MEDIUM - Based on common patterns, not systematic study

**Research date:** 2026-01-23
**Valid until:** 2026-04-23 (90 days - stable ecosystem, no major changes expected)
