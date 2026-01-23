# Roadmap: Cesar Installer

## Overview

Transform Cesar from a flat Python script into a pipx-installable CLI tool with proper packaging, subcommand structure, and user-friendly first-run experience. The journey moves from package structure (foundation) through user experience improvements (prompts, error messages) to final cross-platform validation.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Package & CLI Structure** - Installable package with cesar command and subcommands
- [ ] **Phase 2: User Experience** - Model download prompts and dependency error messages
- [ ] **Phase 3: Cross-Platform Validation** - Verify installation works on macOS and Linux

## Phase Details

### Phase 1: Package & CLI Structure
**Goal**: Users can install cesar via pipx and run commands
**Depends on**: Nothing (first phase)
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, CLI-01, CLI-02, CLI-03, CLI-04
**Success Criteria** (what must be TRUE):
  1. User can run `pipx install .` from project root and get a working cesar command
  2. User can run `cesar transcribe <file> -o <output>` to transcribe audio
  3. User can run `cesar --version` and see correct version number
  4. User can run `cesar --help` and see available commands
  5. User can run `cesar transcribe --help` and see transcribe options
**Plans**: TBD

Plans:
- [ ] 01-01: TBD

### Phase 2: User Experience
**Goal**: Users get helpful prompts and error messages for external dependencies
**Depends on**: Phase 1
**Requirements**: UX-01, UX-02, UX-03, UX-04
**Success Criteria** (what must be TRUE):
  1. User is prompted before model downloads with size estimate shown
  2. User sees clear error message if ffprobe is not installed
  3. Error message suggests platform-appropriate install command (brew/apt)
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Cross-Platform Validation
**Goal**: Users can install and use cesar on macOS and Linux
**Depends on**: Phase 2
**Requirements**: VAL-01, VAL-02, VAL-03
**Success Criteria** (what must be TRUE):
  1. User can install via `pipx install git+<repo-url>` on macOS (Intel and Apple Silicon)
  2. User can install via `pipx install git+<repo-url>` on Linux x86_64
  3. All existing transcription features work after package restructure
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Package & CLI Structure | 0/? | Not started | - |
| 2. User Experience | 0/? | Not started | - |
| 3. Cross-Platform Validation | 0/? | Not started | - |
