# Technology Stack: Python CLI Packaging for pipx

**Project:** Cesar (offline audio transcription CLI)
**Researched:** 2026-01-23
**Research Mode:** Stack dimension for pip/pipx installability

## Executive Summary

To make Cesar installable via `pipx install git+<url>`, you need a properly structured `pyproject.toml` with entry points. The modern Python packaging ecosystem has standardized on `pyproject.toml` (PEP 517/518/621) as the single configuration file. The choice of build backend (setuptools, hatchling, flit) matters less than proper configuration.

**Recommendation:** Use **setuptools** as the build backend because:
1. Already in the project's venv (setuptools 80.9.0 per requirements.txt)
2. Most widely tested with pip/pipx
3. Zero additional dependencies to learn
4. Mature, battle-tested, excellent documentation

## Recommended Stack

### Build System
| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| setuptools | >=70.0.0 | Build backend | HIGH |
| build | >=1.0.0 | Build frontend (dev only) | HIGH |

**Why setuptools over alternatives:**
- **Hatchling**: Modern, elegant, but adds a new tool to learn. Better for greenfield projects.
- **Flit**: Minimal, but less flexibility for projects with complex dependencies like ML libs.
- **Poetry**: Project management tool, not just build backend. Overkill for adding packaging to existing project.
- **PDM**: Similar to Poetry. Good, but unnecessary complexity.

Setuptools has evolved significantly. The modern `pyproject.toml`-only approach (no setup.py, no setup.cfg) is fully supported since setuptools 61.0.0 and is the recommended path.

### Entry Points Configuration
| Component | Value | Purpose | Confidence |
|-----------|-------|---------|------------|
| `[project.scripts]` | `cesar = "cesar.cli:main"` | Creates `cesar` command | HIGH |

This is the standard way to create console scripts. pipx specifically looks for `[project.scripts]` entry points.

### Package Structure
| Pattern | Recommendation | Confidence |
|---------|---------------|------------|
| Layout | `src/` layout (src/cesar/) | HIGH |
| Import style | Package import (from cesar.cli) | HIGH |
| Entry module | `cli.py` with Click group | HIGH |

## Recommended pyproject.toml Structure

```toml
[build-system]
requires = ["setuptools>=70.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cesar"
version = "1.0.0"
description = "Offline audio transcription CLI using faster-whisper"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "Author Name", email = "author@example.com"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Multimedia :: Sound/Audio :: Speech",
]
keywords = ["transcription", "whisper", "audio", "speech-to-text", "offline"]

dependencies = [
    "faster-whisper>=1.0.0",
    "click>=8.0.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=1.0.0",
    "black>=24.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    "pre-commit>=3.0.0",
]

[project.scripts]
cesar = "cesar.cli:main"

[project.urls]
Homepage = "https://github.com/user/cesar"
Repository = "https://github.com/user/cesar"
Issues = "https://github.com/user/cesar/issues"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"*" = ["py.typed"]
```

## Package Layout Transformation

### Current Layout (Flat)
```
cesar/
├── transcribe.py      # Entry point
├── cli.py             # Click CLI
├── transcriber.py     # Core logic
├── device_detection.py
├── utils.py
├── requirements.txt
└── tests/
```

### Target Layout (src/ layout)
```
cesar/
├── pyproject.toml
├── README.md
├── src/
│   └── cesar/
│       ├── __init__.py
│       ├── cli.py          # Click group with subcommands
│       ├── transcriber.py
│       ├── device_detection.py
│       ├── utils.py
│       └── py.typed        # Type hints marker
├── tests/
│   └── ...
└── (requirements.txt kept for backward compat, optional)
```

**Why src/ layout:**
- Prevents accidental imports from local directory during development
- Forces you to install package to test it (catches packaging bugs early)
- Standard practice for distributable packages
- Recommended by PyPA

**Confidence:** HIGH (src/ layout is explicitly recommended in PyPA packaging guide)

## CLI Structure for Subcommands

Current `cli.py` uses a single `@click.command()`. For subcommand structure (`cesar transcribe`), refactor to use `@click.group()`:

```python
# src/cesar/cli.py
import click

@click.group()
@click.version_option(version="1.0.0", prog_name="cesar")
def main():
    """Cesar - Offline audio transcription CLI"""
    pass

@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('-o', '--output', required=True, type=click.Path())
# ... other options ...
def transcribe(input_file, output, ...):
    """Transcribe audio files to text"""
    # existing transcription logic
    pass

# Future: @main.command() for summarize, models, config, etc.
```

**Confidence:** HIGH (standard Click pattern, well-documented)

## pipx Installation Flow

After proper packaging:

```bash
# Install from git (what user wants)
pipx install git+https://github.com/user/cesar.git

# Install from local checkout (development)
pipx install --editable .

# Install specific version/branch
pipx install git+https://github.com/user/cesar.git@v1.0.0
pipx install git+https://github.com/user/cesar.git@installer
```

**What pipx does:**
1. Creates isolated virtualenv in `~/.local/pipx/venvs/cesar/`
2. Installs package and dependencies into that venv
3. Symlinks `cesar` command to `~/.local/bin/cesar`
4. User runs `cesar transcribe <file>` globally

**Confidence:** HIGH (standard pipx behavior)

## Alternatives Considered

| Build Backend | Pros | Cons | Verdict |
|---------------|------|------|---------|
| **setuptools** | Universal, battle-tested, already installed | Verbose config, legacy baggage | **RECOMMENDED** |
| hatchling | Modern, clean, good defaults | New tool to learn, less battle-tested | Good alternative |
| flit | Minimal, fast | Less flexible, struggles with complex deps | Not recommended |
| poetry | Full project management | Overkill, different lockfile format | Not recommended |
| pdm | Modern, PEP 582 support | Overkill for existing project | Not recommended |

## What NOT to Use

| Anti-Pattern | Why Avoid |
|--------------|-----------|
| `setup.py` alone | Deprecated approach, pyproject.toml is standard |
| `setup.cfg` | Transitional format, pyproject.toml preferred |
| Poetry for just packaging | Adds poetry.lock complexity, overkill |
| Flat layout without src/ | Import confusion during development |
| `pip install .` globally | Pollutes global Python, pipx is cleaner |
| requirements.txt for deps | Use pyproject.toml `dependencies`, requirements.txt for pinning |

## Dependencies Consideration

The project has heavy dependencies (torch, faster-whisper, ctranslate2). These are handled fine by pip/pipx, but note:

1. **Install time:** First install downloads ~2GB of torch/CUDA libs
2. **Platform wheels:** faster-whisper has pre-built wheels for common platforms
3. **Python version:** Verify faster-whisper supports Python 3.14 (check PyPI)

**Confidence:** MEDIUM (need to verify faster-whisper 3.14 compatibility)

**Mitigation:** Set `requires-python = ">=3.10"` to support common versions while allowing 3.14.

## Verification Steps

After creating pyproject.toml:

```bash
# 1. Build package locally
python -m build

# 2. Test local pip install
pip install dist/cesar-1.0.0-py3-none-any.whl

# 3. Verify command works
cesar --version
cesar transcribe --help

# 4. Test pipx install from local
pipx install .

# 5. Test pipx install from git (after push)
pipx install git+https://github.com/user/cesar.git
```

## Sources and Confidence

| Claim | Source | Confidence |
|-------|--------|------------|
| pyproject.toml is standard | PEP 517/518/621 (PyPA standards) | HIGH |
| setuptools supports pyproject.toml-only | setuptools docs, in use since 61.0.0 | HIGH |
| src/ layout recommended | PyPA packaging guide | HIGH |
| Click group for subcommands | Click documentation | HIGH |
| pipx install from git | pipx documentation | HIGH |
| setuptools 80.9.0 available | requirements.txt shows it installed | HIGH |
| faster-whisper 3.14 support | Not verified, need to check PyPI | MEDIUM |

**Note:** WebSearch and WebFetch were unavailable during this research. Recommendations are based on my training data (knowledge cutoff May 2025) and observed project state. The core recommendations (pyproject.toml, setuptools, entry points) are stable standards unlikely to have changed.

## Summary for Roadmap

1. **Phase 1:** Create pyproject.toml with setuptools backend
2. **Phase 2:** Restructure to src/ layout
3. **Phase 3:** Refactor cli.py to use Click groups for subcommands
4. **Phase 4:** Test local pip/pipx install
5. **Phase 5:** Test git+url install

**Critical path:** pyproject.toml with proper `[project.scripts]` entry point is the minimum viable change. src/ layout and subcommands are improvements but not blockers for basic pipx installability.

---

*Research completed: 2026-01-23*
*Confidence: HIGH for core recommendations, MEDIUM for dependency version compatibility*
