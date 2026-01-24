# Codebase Structure

**Analysis Date:** 2026-01-23

## Directory Layout

```
cesar/
├── transcribe.py       # Main entry point (thin wrapper)
├── cli.py              # Click-based CLI with Rich UI
├── transcriber.py      # Core AudioTranscriber class
├── device_detection.py # Hardware detection and optimization
├── utils.py            # Shared utility functions
├── test_*.py           # Root-level unit tests (main test files)
├── tests/              # Additional integration/feature tests
├── docs/               # Documentation
│   ├── dev/            # Developer documentation
│   └── optimization-guide.md
├── assets/             # Test audio files
├── .tasks/             # Task planning files
├── .planning/          # GSD planning documents
├── requirements.txt    # Python dependencies
├── mise.toml           # mise version manager config
├── README.md           # Project readme
├── CLAUDE.md           # Claude Code instructions
└── prd.md              # Product requirements document
```

## Directory Purposes

**Root Directory:**
- Purpose: Core application code and tests
- Contains: Main Python modules, test files, configuration
- Key files: `transcribe.py`, `cli.py`, `transcriber.py`, `device_detection.py`, `utils.py`

**tests/:**
- Purpose: Additional test modules for specific features
- Contains: Integration tests, feature-specific tests
- Key files: `test_cli.py`, `test_model.py`, `test_parallel_processing.py`, `test_transcription.py`, `test_validation.py`

**docs/:**
- Purpose: User and developer documentation
- Contains: Usage guides, architecture documentation
- Key files: `optimization-guide.md`

**docs/dev/:**
- Purpose: Developer architecture documentation
- Contains: Technical design documents
- Key files: `architecture.md`, `optimization-architecture.md`

**assets/:**
- Purpose: Test audio files for manual and automated testing
- Contains: Sample audio files
- Key files: `testing speech audio file.m4a`

**.tasks/:**
- Purpose: Task and planning documents
- Contains: Optimization plans, feature roadmaps
- Key files: `speed_optimization_plan.md`

## Key File Locations

**Entry Points:**
- `transcribe.py`: CLI entry point (imports and invokes `cli.main()`)

**Configuration:**
- `requirements.txt`: Python package dependencies
- `mise.toml`: Python version management (Python 3.14)

**Core Logic:**
- `cli.py`: Command-line interface, argument handling, progress display
- `transcriber.py`: `AudioTranscriber` class - file validation, model management, transcription
- `device_detection.py`: `DeviceDetector`, `OptimalConfiguration` - hardware detection, optimization
- `utils.py`: Helper functions - `format_time()`, `estimate_processing_time()`, validators

**Testing:**
- `test_transcriber.py`: Main transcriber tests (root-level)
- `test_cli.py`: CLI interface tests (root-level)
- `test_device_detection.py`: Device detection tests (root-level)
- `test_utils.py`: Utility function tests (root-level)
- `tests/`: Additional feature-specific tests

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `device_detection.py`)
- Test files: `test_<module>.py` (e.g., `test_transcriber.py`)
- Documentation: `kebab-case.md` (e.g., `optimization-guide.md`)

**Directories:**
- Lowercase, no separators (e.g., `docs`, `tests`, `assets`)
- Hidden directories: `.` prefix (e.g., `.tasks`, `.planning`)

**Classes:**
- PascalCase (e.g., `AudioTranscriber`, `DeviceDetector`, `OptimalConfiguration`)

**Functions:**
- snake_case (e.g., `validate_input_file`, `get_optimal_device`)

**Constants:**
- UPPER_SNAKE_CASE (e.g., `SUPPORTED_FORMATS`)

## Where to Add New Code

**New Feature:**
- Primary code: Add to existing module if related (e.g., new transcription option in `transcriber.py`)
- New module: Create at root level if distinct concern (e.g., `output_formatter.py`)
- Tests: Create corresponding `test_<module>.py` at root level

**New CLI Option:**
- Implementation: Add `@click.option` decorator in `cli.py` `main()` function
- Transcriber support: Add parameter to `AudioTranscriber.transcribe_file()`
- Tests: Add test cases in `test_cli.py`

**New Utility Function:**
- Implementation: Add to `utils.py`
- Tests: Add test cases in `test_utils.py`

**New Device/Platform Support:**
- Implementation: Add detection method in `device_detection.py` `DeviceDetector`
- Configuration: Update `OptimalConfiguration` methods
- Tests: Add test cases in `test_device_detection.py`

**Documentation:**
- User docs: `docs/` directory
- Developer docs: `docs/dev/` directory
- Architecture decisions: Update `docs/dev/architecture.md`

## Special Directories

**venv/:**
- Purpose: Python virtual environment
- Generated: Yes (via `python -m venv venv`)
- Committed: No (in .gitignore)

**assets/:**
- Purpose: Test audio files for development
- Generated: No (manually added)
- Committed: Yes

**.planning/:**
- Purpose: GSD planning and codebase analysis documents
- Generated: By GSD commands
- Committed: Typically yes

**.tasks/:**
- Purpose: Task and planning documents
- Generated: No (manually created)
- Committed: Yes

**__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No (in .gitignore)

---

*Structure analysis: 2026-01-23*
