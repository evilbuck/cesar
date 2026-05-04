---
status: active
date: 2026-05-03
subject: 2026-05-03.agent-review-output-folder
topics: [agent-review, output-folder, audio-extraction, file-layout]
research: []
spec:
memory: []
---

# Plan: Consolidate Agent-Review Output to Single Folder

## Goal
Change agent-review mode so all output artifacts go into one folder instead of being scattered alongside the output file.

## Current Layout
```
/path/to/
├── review.md              # Markdown transcript
├── review.sidecar.json    # JSON sidecar
└── review/                # Subfolder (only images)
    └── images/
        ├── screenshot_00-00-30.png
        └── ...
```

## New Layout
```
/path/to/review/           # Single output folder
├── review.md              # Markdown transcript
├── review.sidecar.json    # JSON sidecar
├── audio.mp3              # Extracted audio track (from video input)
└── images/
    ├── screenshot_00-00-30.png
    └── ...
```

## Scope

### In Scope
- Change `AgentReviewOrchestrator.orchestrate()` to create single output directory
- Update `SidecarGenerator` to place sidecar inside output directory
- Update `AgentReviewMarkdownFormatter` image paths (already relative to `images/`)
- Add `extract_audio()` method to `VideoProcessor`
- Call audio extraction from orchestrator when input is video
- Update CLI output messages
- Update tests

### Out of Scope
- Changes to non-agent-review transcription mode
- API server changes
- Changes to the CLI `-o` flag semantics (still accepts path, we derive folder name)

## Affected Files
1. `cesar/orchestrator.py` — Main output structure logic + audio extraction call
2. `cesar/video_processor.py` — New `extract_audio()` method
3. `cesar/sidecar_generator.py` — Sidecar path now inside output folder
4. `cesar/transcript_formatter.py` — Frontmatter `images_dir` path update
5. `cesar/cli.py` — Output messages update
6. `tests/test_orchestrator.py` — Update assertions
7. `tests/test_sidecar.py` — Update assertions
8. `tests/test_formatter.py` — Update assertions
9. `tests/test_video_processor.py` — Add audio extraction test

## Implementation Steps

### Step 1: Add `extract_audio()` to `VideoProcessor`
- Use FFmpeg to extract audio track from video
- Save as `.mp3` (or match source extension) into output directory
- Return path to extracted audio file

### Step 2: Update `AgentReviewOrchestrator.orchestrate()`
- Derive output directory from `output_path`:
  - If `output_path` has `.md` extension → folder = stem
  - Otherwise → folder = `output_path` name
- Create single output directory: `output_dir`
- Place all artifacts inside:
  - `output_dir / "{stem}.md"`
  - `output_dir / "{stem}.sidecar.json"`
  - `output_dir / "images/"`
  - `output_dir / "audio.mp3"` (extracted from video)
- Add audio extraction step between transcription and screenshot phases

### Step 3: Update `SidecarGenerator`
- Accept output directory instead of deriving from output_path
- Sidecar goes into output directory

### Step 4: Update `AgentReviewMarkdownFormatter`
- Image paths already relative to `images_dir`
- Update frontmatter to reflect new layout

### Step 5: Update CLI
- Update output messages to show single folder

### Step 6: Update tests
- Fix path assertions
- Add audio extraction test

## Verification
- [ ] All existing tests pass
- [ ] Agent-review mode creates single output folder with all artifacts
- [ ] Audio extracted from video into output folder
- [ ] CLI messages reflect new structure
