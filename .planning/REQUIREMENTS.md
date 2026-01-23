# Requirements: Cesar Installer

**Defined:** 2026-01-23
**Core Value:** Transcribe audio to text anywhere, offline, with a single command

## v1 Requirements

Requirements for pip/pipx installable CLI.

### Packaging

- [x] **PKG-01**: Package installable via `pipx install git+<repo-url>`
- [x] **PKG-02**: Global `cesar` command available after install
- [x] **PKG-03**: pyproject.toml with setuptools build system and dependencies
- [x] **PKG-04**: Entry point registered via `[project.scripts]`
- [x] **PKG-05**: Python version constraint (>=3.10) specified

### CLI Structure

- [x] **CLI-01**: Subcommand structure: `cesar transcribe <file> -o <output>`
- [x] **CLI-02**: `cesar --version` shows correct version
- [x] **CLI-03**: `cesar --help` shows available commands
- [x] **CLI-04**: `cesar transcribe --help` shows transcribe options

### User Experience

- [ ] **UX-01**: Prompt user before downloading models on first run
- [ ] **UX-02**: Show model size estimate in download prompt
- [ ] **UX-03**: Clear error message if ffprobe/ffmpeg not installed
- [ ] **UX-04**: Suggest installation command for ffmpeg (brew/apt)

### Validation

- [ ] **VAL-01**: Works on macOS (Intel and Apple Silicon)
- [ ] **VAL-02**: Works on Linux x86_64
- [ ] **VAL-03**: All existing transcription features work after restructure

## v2 Requirements

Deferred to future release.

### Enhanced CLI

- **CLI-05**: Shell completion for bash/zsh/fish
- **CLI-06**: `cesar models` subcommand to list/download/remove models
- **CLI-07**: `cesar config` subcommand for defaults

### AI Features

- **AI-01**: `cesar summarize` subcommand for AI-powered summaries
- **AI-02**: Configurable AI provider (Claude, OpenAI, local LLM)
- **AI-03**: Action item extraction from transcripts

## Out of Scope

| Feature | Reason |
|---------|--------|
| PyPI publishing | Not needed for git+url install |
| Windows support | Focus on Mac/Linux first |
| CI/CD install validation | Manual testing sufficient for now |
| Config file support | CLI args sufficient for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PKG-01 | Phase 1 | Complete |
| PKG-02 | Phase 1 | Complete |
| PKG-03 | Phase 1 | Complete |
| PKG-04 | Phase 1 | Complete |
| PKG-05 | Phase 1 | Complete |
| CLI-01 | Phase 1 | Complete |
| CLI-02 | Phase 1 | Complete |
| CLI-03 | Phase 1 | Complete |
| CLI-04 | Phase 1 | Complete |
| UX-01 | Phase 2 | Pending |
| UX-02 | Phase 2 | Pending |
| UX-03 | Phase 2 | Pending |
| UX-04 | Phase 2 | Pending |
| VAL-01 | Phase 3 | Pending |
| VAL-02 | Phase 3 | Pending |
| VAL-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-01-23*
*Last updated: 2026-01-23 after roadmap creation*
