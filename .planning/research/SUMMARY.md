# Project Research Summary

**Project:** Cesar (Offline Audio Transcription CLI)
**Domain:** Python CLI packaging for pip/pipx distribution
**Researched:** 2026-01-23
**Confidence:** HIGH

## Executive Summary

Cesar is an existing, functional offline audio transcription CLI tool built with faster-whisper, Click, and Rich. The project goal is to make it installable via `pipx install git+<url>` with a proper subcommand structure (`cesar transcribe`). This is a well-understood domain with established patterns: modern Python packaging uses `pyproject.toml` (PEP 517/518/621) with a `src/` layout, console script entry points, and package-qualified imports.

The recommended approach is to use **setuptools** as the build backend (already in the project's environment, battle-tested, universal compatibility) with a `src/cesar/` package layout. The current flat file structure with sibling imports (`from transcriber import AudioTranscriber`) is the primary technical obstacle - these imports will fail after packaging. The migration requires moving all source files into `src/cesar/`, converting imports to package-qualified form, and configuring entry points.

Key risks are centered on the first-run experience rather than packaging mechanics. The tool has two external dependencies that cannot be expressed in Python packaging: **ffprobe** (for audio duration) and **whisper models** (75MB-3GB downloads on first use). Both require clear error messages and user prompts. The packaging itself is straightforward once imports are corrected; the main pitfall is testing only in development mode where flat imports still work.

## Key Findings

### Recommended Stack

Use setuptools with `pyproject.toml` as the sole configuration file. This is the most conservative choice: setuptools is already installed (80.9.0), is universally tested with pip/pipx, and requires no new tools to learn.

**Core technologies:**
- **setuptools>=70.0.0**: Build backend - already installed, universal pip/pipx compatibility
- **pyproject.toml**: Single configuration file - PEP 517/518/621 standard, replaces setup.py/setup.cfg
- **src/ layout**: Package structure - prevents import confusion, catches packaging bugs during development

**Do not use:**
- Poetry or PDM (overkill for adding packaging to existing project)
- setup.py alone (deprecated)
- Flat layout (import confusion during development)

### Expected Features

**Must have (table stakes):**
- `pyproject.toml` with build system and dependencies
- `[project.scripts]` entry point for `cesar` command
- Package structure with `__init__.py` and proper imports
- Single source of truth for version
- Declared dependencies (convert from requirements.txt)

**Should have (competitive):**
- Subcommand structure (`cesar transcribe`) for future expansion
- First-run model download prompt with size estimate
- Clear ffprobe error message with install instructions
- Shell completion support (Click has built-in support)

**Defer (v2+):**
- Config file support (~/.config/cesar/config.toml)
- Machine-readable output (--format json)
- Progress persistence for interrupted transcriptions
- Plugin architecture

### Architecture Approach

Restructure from flat Python files to `src/cesar/` package layout. This is a mechanical refactor: move files, update imports, add `__init__.py` and `__main__.py`, configure pyproject.toml. The existing component boundaries (cli.py, transcriber.py, device_detection.py, utils.py) are already well-defined and require no architectural changes.

**Major components (unchanged responsibilities):**
1. **cli.py** - Click CLI with Rich output, argument parsing, progress display
2. **transcriber.py** - AudioTranscriber class, model management, transcription orchestration
3. **device_detection.py** - Hardware detection, optimal configuration selection
4. **utils.py** - Time formatting, validation helpers

**Key patterns to follow:**
- Lazy loading of heavy dependencies (faster-whisper, torch) - already implemented
- Optional dependency handling with graceful fallback - already implemented
- Version from single source using `importlib.metadata`

### Critical Pitfalls

1. **Relative imports break after packaging** - Current `from transcriber import AudioTranscriber` fails when installed. Must convert all to `from cesar.transcriber import AudioTranscriber`. This affects cli.py, transcriber.py, and all test files. Address first.

2. **Test imports fail after restructure** - Tests use same flat import style. Must update test imports and run tests against installed package (`pip install -e .`) not source files.

3. **ffprobe not found** - External binary dependency that Python packaging cannot express. Must check at startup and provide clear error with install instructions.

4. **Model download without consent** - 75MB-3GB downloads on first use. Must check cache first, prompt with size estimate, show progress.

5. **PyTorch installation size** - ~2GB download as transitive dependency of faster-whisper. Document install time expectations; cannot easily avoid.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Package Structure
**Rationale:** Everything else depends on correct package structure. Import failures are the primary blocker.
**Delivers:** Installable package via `pip install -e .` with working `cesar` command
**Addresses:** pyproject.toml, src/ layout, entry points, subcommand structure, version sync
**Avoids:** Relative import breakage (P1), entry point signature mismatch (P2), test import failures (P10)

**Tasks:**
1. Create `src/cesar/` directory structure
2. Move source files with updated imports
3. Create `__init__.py`, `__main__.py`, `pyproject.toml`
4. Convert cli.py to Click group with `transcribe` subcommand
5. Update and verify all tests pass with installed package
6. Delete old `transcribe.py` entry point

### Phase 2: External Dependencies
**Rationale:** User-facing errors from missing ffprobe and surprise model downloads are the next most impactful issues.
**Delivers:** Clear error messages, model download prompts, graceful handling of missing external tools
**Addresses:** First-run experience, ffprobe dependency, model download consent
**Avoids:** ffprobe missing (P4), model download without consent (P5)

**Tasks:**
1. Add startup check for ffprobe with helpful error message
2. Implement model cache check before loading
3. Add download prompt with model size estimate
4. Show Rich progress bar during model download
5. Document external dependencies in README

### Phase 3: Distribution Validation
**Rationale:** Before publishing, validate the entire user flow works in clean environments.
**Delivers:** Verified `pipx install git+<url>` workflow, documentation
**Addresses:** README rendering, license file, Python version constraints
**Avoids:** README not rendered (P11), license missing (P12), version constraint issues (P13)

**Tasks:**
1. Test `pipx install .` in fresh virtual environment
2. Test `pipx install git+<url>` from GitHub
3. Validate README renders correctly (twine check)
4. Add LICENSE file (MIT)
5. Test on both macOS and Linux
6. Update documentation with install instructions

### Phase 4: Polish (Optional)
**Rationale:** Nice-to-have improvements after core packaging works.
**Delivers:** Shell completion, improved help output, offline mode flag
**Addresses:** Differentiating features from FEATURES.md

**Tasks:**
1. Add shell completion generation (`--install-completion`)
2. Add `--offline` flag that fails if model not cached
3. Improve help text with model size information
4. Add `--debug` flag for verbose diagnostics

### Phase Ordering Rationale

- **Phase 1 must be first** because all other work depends on a working package structure. Attempting any other improvements on the flat file structure will require redoing work.
- **Phase 2 before Phase 3** because external dependency handling affects the user experience that needs validation in Phase 3.
- **Phase 3 before Phase 4** because publishing without validation risks a broken first impression. Polish can happen post-launch.
- **Phase 4 is optional** for MVP - these features can be added in subsequent releases without breaking changes.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Model download prompt implementation may need HuggingFace Hub API research for cache detection

Phases with standard patterns (skip research-phase):
- **Phase 1:** Well-documented patterns (PyPA guides, PEP standards, Click docs)
- **Phase 3:** Standard validation workflow
- **Phase 4:** Standard Click patterns (shell completion, flags)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | PEP standards, setuptools docs, established since 2021 |
| Features | HIGH | PyPA guides, widely adopted patterns from popular CLI tools |
| Architecture | MEDIUM | Standard patterns, but web sources unavailable for verification |
| Pitfalls | HIGH | Based on project-specific code analysis and established patterns |

**Overall confidence:** HIGH

The core packaging approach (pyproject.toml, setuptools, src/ layout, entry points) is based on finalized PEP standards and is extremely stable. The main uncertainty is whether faster-whisper has any undocumented compatibility issues with Python 3.14.

### Gaps to Address

- **faster-whisper Python 3.14 compatibility**: Not verified. Mitigate by setting `requires-python = ">=3.10"` and testing on 3.10/3.11/3.12.
- **HuggingFace Hub API for model cache detection**: May need research during Phase 2 to implement download prompt correctly.
- **Shell completion installation**: Click's `--install-completion` behavior varies by shell; may need testing during Phase 4.

## Sources

### Primary (HIGH confidence)
- PEP 517 - Build system interface
- PEP 518 - pyproject.toml for build requirements
- PEP 621 - Project metadata in pyproject.toml
- Python Packaging User Guide (packaging.python.org)
- Click documentation - Command groups, shell completion
- setuptools documentation

### Secondary (MEDIUM confidence)
- src/ layout pattern - widely adopted since 2018
- patterns from popular CLI tools (black, ruff, pytest)

### Tertiary (LOW confidence)
- faster-whisper 3.14 compatibility - needs verification on PyPI

---
*Research completed: 2026-01-23*
*Ready for roadmap: yes*
