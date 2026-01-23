# Feature Landscape: Python CLI Packaging

**Domain:** Python CLI tool packaging for pip/pipx installability
**Researched:** 2026-01-23
**Context:** Existing Click-based CLI tool being packaged for distribution

## Table Stakes

Features users expect. Missing = pip/pipx install fails or feels broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `pyproject.toml` with build system | Modern Python standard (PEP 517/518) | Low | Required since Python 3.6+, setuptools or hatchling |
| `[project.scripts]` entry point | Makes `cesar` command available | Low | Maps command name to Python function |
| Package structure with `__init__.py` | Python needs importable package | Low | Move modules into `src/cesar/` or `cesar/` directory |
| Semantic version in single source | Users expect `--version` to work | Low | Define in `pyproject.toml` or `__version__` |
| Declared dependencies | pip installs dependencies automatically | Low | Already have `requirements.txt`, convert to `pyproject.toml` |
| Python version constraint | Prevents install on incompatible Python | Low | `requires-python = ">=3.10"` |
| README as long description | PyPI/GitHub display | Low | Already exists |
| License declaration | Package metadata requirement | Low | Add to `pyproject.toml` |
| Relative imports within package | Imports break without this | Medium | Current code uses sibling imports |

## Differentiators

Features that set well-packaged CLI tools apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Subcommand structure | Future-proofs for new commands | Medium | `cesar transcribe`, `cesar models`, etc. |
| Shell completion generation | Power user productivity | Medium | Click has built-in support via `click.shell_complete` |
| Rich help formatting | Professional appearance | Low | Already using Rich, can extend to help |
| `py.typed` marker | IDE support for library users | Low | Empty file signals typing support |
| `--debug` flag | Troubleshooting assistance | Low | Show stack traces, verbose diagnostics |
| Config file support | Persist user preferences | Medium | `~/.config/cesar/config.toml` |
| Machine-readable output | Scripting/automation | Medium | `--format json` option |
| First-run experience | Guides new users | Medium | Model download prompt, help hints |
| Offline indicator | Trust building | Low | Show "Offline ready" after model cached |
| Progress persistence | Resume interrupted work | High | Checkpoint system for long transcriptions |

## Anti-Features

Features to explicitly NOT build. Common mistakes in CLI packaging.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| setup.py without pyproject.toml | Legacy, harder to maintain | Use `pyproject.toml` exclusively |
| Hardcoded paths | Breaks on other systems | Use `pathlib` and XDG base directories |
| Implicit dependencies | Install fails mysteriously | Declare all in `pyproject.toml` |
| Global state/singletons | Testing/parallelism issues | Pass configuration explicitly |
| Printing instead of logging | Can't control output | Use `logging` module with levels |
| Catching all exceptions | Hides real errors | Catch specific exceptions |
| Required config files | Fails on fresh install | Sensible defaults, optional config |
| Non-zero exit on success | Breaks shell scripts | `sys.exit(0)` on success, non-zero on error |
| ANSI codes without detection | Garbled output in pipes | Let Rich handle TTY detection |
| Bundling large assets | Huge package size | Download on first use (already doing this) |
| `__main__.py` only entry | No programmatic import | Expose clean API in `__init__.py` |

## Feature Dependencies

```
pyproject.toml (foundation)
    |
    +-- [project.scripts] entry point
    |       |
    |       +-- Package structure (required for entry point to work)
    |               |
    |               +-- Relative imports (required for package)
    |
    +-- Declared dependencies
    |
    +-- Python version constraint
```

```
Subcommand structure
    |
    +-- Click groups (instead of single command)
    |
    +-- Separate command modules
```

```
Shell completion
    |
    +-- Click shell_complete integration
    |
    +-- Install script or instructions
```

## MVP Recommendation

For MVP (pipx installable), prioritize:

1. **pyproject.toml** - Foundation, everything depends on this
2. **Package structure** - Move to `src/cesar/` layout
3. **Entry point** - `cesar` command registration
4. **Subcommand structure** - `cesar transcribe` (enables future expansion)
5. **Relative imports** - Fix imports for package context

Defer to post-MVP:

- **Shell completion**: Nice-to-have, can add later without breaking changes
- **Config file support**: Complexity, most users won't need
- **Machine-readable output**: Wait for actual demand
- **Progress persistence**: High complexity, niche use case

## Complexity Analysis

### Low Complexity (< 1 hour)

| Feature | Why Low | Risk |
|---------|---------|------|
| pyproject.toml creation | Standard template | Low |
| Entry point declaration | One line config | Low |
| Version in single source | Pattern well-documented | Low |
| Python constraint | One line config | Low |
| README as description | One line config | Low |
| License declaration | One line config | Low |
| `py.typed` marker | Empty file | Low |
| `--debug` flag | Click pattern | Low |

### Medium Complexity (1-4 hours)

| Feature | Why Medium | Risk |
|---------|------------|------|
| Package structure refactor | Many files to move, imports to fix | Medium |
| Subcommand structure | Restructure CLI, but Click supports well | Low |
| Shell completion | Click built-in, but install complexity | Low |
| Relative imports | Requires testing all import paths | Medium |
| First-run experience | UX decisions, model download prompt | Low |
| Config file support | File format, merge with CLI args | Medium |

### High Complexity (> 4 hours)

| Feature | Why High | Risk |
|---------|----------|------|
| Progress persistence | Checkpoint format, resume logic | High |
| Machine-readable output | Multiple format support, schema design | Medium |

## Package Structure Options

### Option A: Flat Package (Simpler)

```
cesar/
    __init__.py
    __main__.py
    cli.py
    transcriber.py
    device_detection.py
    utils.py
pyproject.toml
```

**Pros:** Minimal change, familiar layout
**Cons:** Name collision risk, less standard

### Option B: src/ Layout (Recommended)

```
src/
    cesar/
        __init__.py
        __main__.py
        cli.py
        transcriber.py
        device_detection.py
        utils.py
pyproject.toml
tests/
```

**Pros:** Prevents accidental local imports, standard modern layout
**Cons:** More file moves, requires import path changes

**Recommendation:** Use src/ layout. It's the modern standard and prevents the common pitfall of accidentally importing local source instead of installed package during development.

## Entry Point Configuration

```toml
[project.scripts]
cesar = "cesar.cli:main"
```

For subcommand structure with Click groups:

```python
# cli.py
import click

@click.group()
@click.version_option()
def cli():
    """Cesar - Offline audio transcription"""
    pass

@cli.command()
@click.argument('input_file')
@click.option('-o', '--output', required=True)
def transcribe(input_file, output):
    """Transcribe audio file to text"""
    ...

# Entry point targets 'cli' group, not individual command
```

```toml
[project.scripts]
cesar = "cesar.cli:cli"
```

## Dependency Declaration

Convert from `requirements.txt` to `pyproject.toml`:

**Core dependencies only:**
```toml
[project]
dependencies = [
    "faster-whisper>=1.0.0",
    "click>=8.0.0",
    "rich>=13.0.0",
]
```

**Note:** `torch`, `ctranslate2`, `huggingface-hub` are transitive dependencies of `faster-whisper` - don't re-declare.

**Optional dev dependencies:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "black>=25.0.0",
    "ruff>=0.10.0",
    "mypy>=1.0.0",
]
```

## First-Run Experience

For tools that download large assets on first use:

1. **Check if model exists** before attempting download
2. **Prompt user** with size estimate: "Model 'base' (74MB) not found. Download now? [Y/n]"
3. **Show download progress** with Rich progress bar
4. **Confirm success** with "Model cached to ~/.cache/huggingface/hub/"
5. **Handle offline gracefully** with clear error message

```python
def ensure_model_available(model_size: str, auto_download: bool = False) -> bool:
    """Check model availability, optionally prompt for download."""
    if model_cached(model_size):
        return True

    if auto_download:
        download_model(model_size)
        return True

    # Interactive prompt
    console.print(f"Model '{model_size}' not found locally.")
    if click.confirm(f"Download model ({MODEL_SIZES[model_size]})?"):
        download_model(model_size)
        return True

    return False
```

## Sources

**Confidence Levels:**
- HIGH: PyPA (Python Packaging Authority) documentation, PEP standards
- MEDIUM: Widely adopted patterns from popular CLI tools (black, ruff, pytest)
- LOW: Community conventions without official documentation

**References:**
- PEP 517 - Build system interface (HIGH)
- PEP 518 - pyproject.toml for build requirements (HIGH)
- PEP 621 - Project metadata in pyproject.toml (HIGH)
- Click documentation - Command groups and completion (HIGH)
- Python Packaging User Guide - packaging.python.org (HIGH)
- src layout pattern - widely adopted since 2018 (MEDIUM)

---

*Research conducted: 2026-01-23*
