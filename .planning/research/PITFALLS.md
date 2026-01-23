# Domain Pitfalls: Python CLI Packaging

**Domain:** Python CLI packaging with heavy ML dependencies
**Researched:** 2026-01-23
**Confidence:** HIGH (based on established Python packaging patterns and specific project characteristics)

## Critical Pitfalls

Mistakes that cause installation failures, broken packages, or require significant rework.

---

### Pitfall 1: Relative Imports Break After Packaging

**What goes wrong:** Flat script files use `from cli import main` or `from transcriber import AudioTranscriber`. After converting to a package with `src/cesar/` structure, these imports fail with `ModuleNotFoundError` because Python's import system works differently for installed packages vs. scripts.

**Why it happens:**
- Running `python transcribe.py` adds the script's directory to `sys.path`
- Installed packages don't have this behavior — they use the package namespace
- Current code has: `from cli import main`, `from transcriber import AudioTranscriber`, `from device_detection import OptimalConfiguration`

**Consequences:**
- `pipx install` succeeds but `cesar` command fails immediately on first use
- Error appears only at runtime, not during install
- Users get cryptic `ModuleNotFoundError: No module named 'transcriber'`

**Warning signs:**
- Any `from module import X` where `module` is a sibling file (not standard library or external package)
- Test failures when running via `pytest` from different working directories
- Works when run directly but fails via entry point

**Prevention:**
1. Convert all intra-package imports to explicit relative or absolute package imports:
   ```python
   # Before (flat script style)
   from transcriber import AudioTranscriber

   # After (package style - relative)
   from .transcriber import AudioTranscriber

   # After (package style - absolute)
   from cesar.transcriber import AudioTranscriber
   ```
2. Add `__init__.py` that defines the package's public API
3. Test installation in fresh virtual environment before release

**Phase to address:** Phase 1 (Package Structure) — must be first, everything depends on correct imports

**Affected files in this project:**
- `transcribe.py` line 10: `from cli import main`
- `cli.py` lines 20-21: `from transcriber import AudioTranscriber`, `from utils import format_time, estimate_processing_time`
- `transcriber.py` line 10: `from device_detection import OptimalConfiguration, setup_environment`

---

### Pitfall 2: Entry Point Function Signature Mismatch

**What goes wrong:** Click decorators transform functions — the decorated function returns something different than what console_scripts entry points expect. If you point the entry point to the wrong function or the function doesn't handle return codes properly, users get silent failures or incorrect exit codes.

**Why it happens:**
- Click's `@click.command()` decorator wraps the function
- Entry points expect a callable that returns an integer exit code or raises `SystemExit`
- Current code in `cli.py` returns `0` or `1` from `main()`, which is correct
- But `transcribe.py` does `sys.exit(main())` which is the script pattern, not the entry point pattern

**Consequences:**
- `cesar` command always exits with code 0 even on errors
- Or: `TypeError` when Click's return value doesn't match expectations
- CI/CD scripts can't detect failures

**Warning signs:**
- Entry point works but `$?` exit code is always 0
- Error messages appear but script "succeeds"
- Piping to other commands behaves unexpectedly

**Prevention:**
1. Entry point should call the Click command directly (Click handles `sys.exit`):
   ```toml
   [project.scripts]
   cesar = "cesar.cli:main"
   ```
2. Don't wrap Click commands in `sys.exit()` in the entry point — Click does this internally
3. Verify exit codes: `cesar bad-file.mp3 -o out.txt; echo $?` should be non-zero

**Phase to address:** Phase 1 (Package Structure) — entry point configuration

---

### Pitfall 3: PyTorch Installation Complexity

**What goes wrong:** PyTorch is huge (~2GB with CUDA support) and has multiple variants (CPU-only, CUDA 11.8, CUDA 12.1, etc.). A naive `torch>=2.0.0` dependency pulls whichever variant pip/pipx decides, often the largest CUDA version, massively bloating install size and time.

**Why it happens:**
- PyTorch publishes different wheels for different CUDA versions
- Default PyPI torch package may not match user's system
- Users without NVIDIA GPUs don't need CUDA wheels
- Apple Silicon users need the MPS-compatible wheel

**Consequences:**
- 5-10+ minute install times for users with good internet
- 2GB+ download for users who only need CPU inference
- Potential CUDA version mismatches causing runtime errors
- Failed installs on memory-constrained systems

**Warning signs:**
- Install takes very long
- Users report `pip` or `pipx` hanging
- Out of memory during install
- CUDA errors on machines without NVIDIA GPUs

**Prevention:**
1. Consider making torch an optional dependency with guidance:
   ```toml
   [project.optional-dependencies]
   cuda = ["torch[cuda]>=2.0.0"]
   cpu = ["torch>=2.0.0"]  # Minimal
   ```
2. Document platform-specific installation instructions
3. Test install size on fresh environment
4. Consider detecting CUDA at runtime rather than requiring it at install time
5. The current code already handles CUDA absence gracefully — lean into this

**Phase to address:** Phase 2 (Dependencies) — dependency specification

**Note:** faster-whisper already depends on torch, so this is somewhat unavoidable. But controlling *which* torch gets installed matters.

---

### Pitfall 4: Missing External Tool Dependency (ffprobe)

**What goes wrong:** The transcriber uses `ffprobe` (part of ffmpeg) via `subprocess.run()` to get audio duration. This is an external binary, not a Python package. Users who install via pipx get a broken tool if ffmpeg isn't installed.

**Why it happens:**
- Python packaging can only specify Python dependencies
- External binaries must be installed separately by the user
- The error only appears when the specific feature is used (getting duration)
- Error message (`FileNotFoundError: ffprobe`) is unclear for users unfamiliar with ffmpeg

**Consequences:**
- Tool installs successfully but fails on first real use
- Users confused by "ffprobe not found" error
- Bad first-run experience

**Warning signs:**
- `RuntimeError: Failed to get audio duration` in logs
- Users report tool "doesn't work"
- Works on dev machines (ffmpeg installed), fails on fresh installs

**Prevention:**
1. **Check at startup:** Verify ffprobe exists before attempting operations
2. **Clear error message:** "ffprobe not found. Install ffmpeg: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"
3. **Document requirement:** README and help text should mention ffmpeg dependency
4. **Consider fallback:** Use ffprobe for duration but don't make it strictly required for transcription (duration display becomes "unknown")
5. **Alternative:** Use a pure-Python audio library to get duration (e.g., mutagen, pydub) — but adds complexity

**Phase to address:** Phase 3 (User Experience) — startup checks and error messages

**Affected code:**
- `transcriber.py` lines 132-154: `get_audio_duration()` method calls ffprobe

---

### Pitfall 5: Model Download Without User Consent

**What goes wrong:** Whisper models range from 75MB (tiny) to 3GB (large-v3). On first use, faster-whisper automatically downloads the model to `~/.cache/huggingface/`. Users on metered connections or with disk space constraints get surprised by large downloads.

**Why it happens:**
- HuggingFace hub downloads models transparently
- No user prompt before download starts
- Download happens inside the `WhisperModel()` constructor
- Can't easily intercept to add confirmation

**Consequences:**
- Surprised users with large downloads
- Failed downloads on slow connections leave partial models
- Disk space issues
- Bad user experience on first run

**Warning signs:**
- First run takes very long
- User reports "hanging" on first use
- Disk space warnings after install

**Prevention:**
1. **Check if model exists first:** Use huggingface_hub API to check cache before loading
2. **Prompt before download:** "Model 'base' (150MB) not found. Download now? [Y/n]"
3. **Show download progress:** Use Rich progress bar during download
4. **Support offline mode:** `--offline` flag that fails if model not cached
5. **Document model sizes:** Show sizes in `--help` output

**Phase to address:** Phase 3 (User Experience) — model download handling

**Note:** PROJECT.md already identifies this as a requirement: "Prompt before downloading models on first run"

---

## Moderate Pitfalls

Mistakes that cause user confusion, poor DX, or technical debt.

---

### Pitfall 6: Version Not Synchronized

**What goes wrong:** Version is hardcoded in multiple places (`cli.py` has `version="1.0.0"` in the decorator). After packaging, pyproject.toml also defines a version. These get out of sync, confusing users and breaking version checks.

**Why it happens:**
- Click's `@click.version_option(version="1.0.0")` is hardcoded
- pyproject.toml's `version = "1.0.0"` is a separate value
- Easy to update one and forget the other
- No single source of truth

**Consequences:**
- `cesar --version` shows different version than `pip show cesar`
- Confusion in bug reports ("which version are you on?")
- Changelog doesn't match actual releases

**Prevention:**
1. **Single source of truth:** Define version in one place only
2. **Option A — pyproject.toml as source:**
   ```python
   from importlib.metadata import version
   __version__ = version("cesar")

   @click.version_option(version=__version__)
   ```
3. **Option B — __init__.py as source:** Use setuptools-scm or manual `__version__` and reference in pyproject.toml
4. **Test:** Add test that verifies versions match

**Phase to address:** Phase 1 (Package Structure) — version management

**Affected code:**
- `cli.py` line 138: `@click.version_option(version="1.0.0", prog_name="transcribe")`

---

### Pitfall 7: Package Name vs. Command Name Confusion

**What goes wrong:** Package name on PyPI, importable package name, and CLI command name can all differ. This causes confusion and import errors.

**Why it happens:**
- PyPI package name: `cesar` (what you `pip install`)
- Importable name: `cesar` (what you `import cesar`)
- Command name: `cesar` (what you type in terminal)
- These can be different, and often are in real projects
- Dashes vs underscores (`my-package` on PyPI but `my_package` for imports)

**Consequences:**
- `pip install cesar` works but `import cesar` fails
- Users confused about what to import
- Documentation inconsistencies

**Prevention:**
1. **Keep names consistent:** Use same name for all three (cesar)
2. **Avoid hyphens in package name:** Use underscores if multi-word (not applicable here)
3. **Document clearly:** README shows all three names
4. **Test:** Verify `pip show cesar` and `python -c "import cesar"` both work

**Phase to address:** Phase 1 (Package Structure) — naming configuration

---

### Pitfall 8: Missing Package Data Files

**What goes wrong:** If the package needs non-Python files (data files, templates, configs), they might not get included in the wheel. The package works in dev but fails after install.

**Why it happens:**
- By default, only `.py` files are included in packages
- `package_data` or `include_package_data` must be configured
- MANIFEST.in for source distributions
- pyproject.toml needs explicit file patterns

**Consequences:**
- `FileNotFoundError` for data files that exist in the repo but not in installed package
- Works in development, fails after pip install

**Warning signs:**
- Tests pass locally but fail in CI
- Features work from git clone but not from pip install

**Prevention:**
1. **Audit data file usage:** Check for any non-`.py` files the code loads at runtime
2. **Configure inclusion:** In pyproject.toml:
   ```toml
   [tool.setuptools.package-data]
   cesar = ["*.yaml", "*.json", "templates/*"]
   ```
3. **Test installed package:** Run tests against pip-installed version, not source

**Phase to address:** Phase 1 (Package Structure) — if data files exist

**For this project:** No obvious data files needed — models download from HuggingFace, no bundled configs. LOW RISK but verify.

---

### Pitfall 9: Subcommand Migration Breaks Existing Usage

**What goes wrong:** Current usage is `python transcribe.py <file> -o <out>`. Target usage is `cesar transcribe <file> -o <out>`. If both patterns need to work during transition, or if the subcommand structure isn't set up correctly, users get confused or scripts break.

**Why it happens:**
- Moving from single command to subcommand group is a structural change
- Click requires different decorators (`@click.group()` vs `@click.command()`)
- Help text and error messages change
- Existing documentation becomes wrong

**Consequences:**
- User muscle memory broken
- Existing scripts using the old pattern fail
- Confusing help output

**Prevention:**
1. **Clear migration path:** Document the change prominently
2. **Group structure from start:**
   ```python
   @click.group()
   def cli():
       """Cesar - Offline audio transcription"""
       pass

   @cli.command()
   def transcribe():
       """Transcribe audio to text"""
       pass
   ```
3. **Test both patterns:** Ensure `cesar transcribe --help` works
4. **Version bump:** Semantic versioning — this is a breaking change (major version if 1.x, otherwise note in changelog)

**Phase to address:** Phase 1 (Package Structure) — CLI restructuring

**Note:** PROJECT.md specifies subcommand structure as a requirement.

---

### Pitfall 10: Test Imports Fail After Restructure

**What goes wrong:** Tests use the same flat import style as the main code. After restructuring to a package, tests can't import the modules they're testing.

**Why it happens:**
- Tests at project root use `from transcriber import AudioTranscriber`
- After package restructure, module is at `cesar.transcriber`
- pytest's discovery works differently than script execution

**Consequences:**
- All tests fail after restructure
- CI breaks
- Development blocked until tests are fixed

**Warning signs:**
- Tests pass before restructure, fail after
- `ModuleNotFoundError` in pytest output

**Prevention:**
1. **Restructure tests too:** Move to `tests/` directory if not already
2. **Update test imports:** Use package-qualified imports
3. **Install package in dev mode:** `pip install -e .` makes package importable
4. **Conftest.py setup:** Can add project root to path if needed (not ideal but works)

**Phase to address:** Phase 1 (Package Structure) — after main restructure, before any other work

**Affected files in this project:**
- `test_cli.py`, `test_transcriber.py`, `test_utils.py`, `test_device_detection.py`
- `tests/` directory contents

---

## Minor Pitfalls

Mistakes that cause annoyance but are easily fixable.

---

### Pitfall 11: README Not Rendered on PyPI

**What goes wrong:** PyPI renders README.md as the package description. If the README uses GitHub-specific markdown features, links are broken, images don't load, badges don't render.

**Why it happens:**
- PyPI markdown renderer is different from GitHub's
- Relative links (`./docs/foo.md`) don't work
- GitHub-specific features (mermaid diagrams, HTML details tags) don't render
- Image paths need absolute URLs

**Prevention:**
1. **Use absolute URLs:** For images and links
2. **Test rendering:** `twine check dist/*` validates README
3. **Keep it simple:** Avoid advanced markdown features
4. **pyproject.toml:** Ensure `readme = "README.md"` is set

**Phase to address:** Phase 4 (Polish) — before first release

---

### Pitfall 12: License File Not Included

**What goes wrong:** License exists in repo but not in wheel. Legal ambiguity for users.

**Prevention:**
1. Add to pyproject.toml:
   ```toml
   license = {file = "LICENSE"}
   ```
2. Or include in package_data

**Phase to address:** Phase 1 (Package Structure) — metadata

**For this project:** No LICENSE file exists. Should add one (MIT typical for tools like this).

---

### Pitfall 13: Python Version Constraint Too Narrow or Too Wide

**What goes wrong:** pyproject.toml says `requires-python = ">=3.14"` but dependencies don't support 3.14 yet, or it says `>=3.8` but code uses 3.10+ features.

**Why it happens:**
- Dependencies have their own Python version support
- Language features added in newer versions used unknowingly
- No CI testing across Python versions

**Consequences:**
- Install fails on older Python versions
- Install succeeds but runtime crashes with SyntaxError
- Users confused about actual requirements

**Prevention:**
1. **Test minimum version:** CI should test against minimum supported Python
2. **Check dependency compatibility:** torch, faster-whisper have specific Python requirements
3. **Be conservative:** Start with `>=3.10` or `>=3.11` for modern ML libraries

**Phase to address:** Phase 2 (Dependencies) — Python version specification

**For this project:** Currently using Python 3.14 (via mise). faster-whisper requires Python 3.8+. torch 2.7 requires Python 3.9+. Recommend `>=3.10` for modern type hints without `from __future__ import annotations`.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Package Structure | Relative imports (P1), Test imports (P10) | Convert all imports first, install in editable mode |
| Entry Points | Function signature (P2), Subcommands (P9) | Test entry point invocation explicitly |
| Dependencies | PyTorch size (P3), Python version (P13) | Document install options, test minimum version |
| External Tools | ffprobe missing (P4) | Add startup check with helpful error |
| First Run | Model download (P5) | Implement download prompt before load |
| Version | Version sync (P6) | Use importlib.metadata, single source of truth |
| Testing | Test failures (P10) | Fix tests immediately after restructure |
| Release | README render (P11), License (P12) | Validate with twine before publish |

---

## Checklist for Each Phase

### Before Starting Package Restructure
- [ ] Document all current imports (done above)
- [ ] Identify data files that need inclusion (none found)
- [ ] Decide on package name and structure
- [ ] Plan test migration

### Before First Test of Packaged CLI
- [ ] Install in fresh venv with `pip install -e .`
- [ ] Verify imports work
- [ ] Verify entry point invocation
- [ ] Verify exit codes on success and failure
- [ ] Verify `--version` shows correct version

### Before Publishing
- [ ] Test `pipx install .` in fresh environment
- [ ] Verify ffprobe error message is helpful
- [ ] Verify model download prompts user
- [ ] Test on both macOS and Linux
- [ ] Validate README rendering with `twine check`

---

*Pitfall research: 2026-01-23*
*Confidence: HIGH — based on established Python packaging patterns and analysis of project-specific code*
