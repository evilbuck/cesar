# Plan: Cesar review transcription with screenshots

## What we might build

A Cesar feature that takes a screen recording with voiceover narration and produces an agent-readable review document combining transcript segments with referenced screenshots.

## Core concept

User records a screen + voiceover reviewing an app/website (identifying issues, desired changes). Cesar:
1. Extracts audio from video
2. Transcribes via Cesar CLI (with timestamps)
3. Extracts key frames/screenshots via FFmpeg
4. Associates transcript segments with corresponding screenshots using metadata
5. Outputs structured Markdown that an agent can parse to make a change plan

## Why it matters

- Eliminates manual note-taking during review videos
- Turns narrated visual feedback into structured implementation input
- Keeps the responsibility in the tool already handling transcription

## Constraints / preferences

- **Home**: This should live in Cesar, likely as a new `cesar transcribe` capability/flag
- **Transcription tool**: Cesar CLI (`cesar transcribe`)
- **Screenshots**: FFmpeg for frame extraction
- **Output container**: Markdown with local image references
- **Project location**: `~/projects/cesar` and GitHub
- **No burned-in timestamps** on images
- **Prefer metadata** on screenshots / associations instead of altering image pixels
- **Future-friendly**: allow screenshot-to-transcript ranges later, since the screen may stay static while narration continues

## Brainstorm notes

- Likely UX:
  ```bash
  cesar transcribe review.mp4 -o review.md --screenshots
  ```
- Cesar may need a richer artifact model than plain transcript text so screenshots and transcript sections can be associated cleanly
- Screenshot references should probably live in Markdown as normal image links, with timing/association metadata stored alongside or emitted in a structured section
- A later agent can read the combined artifact and turn it into a scoped implementation plan
- Cesar outputs Markdown with speaker labels and `[MM:SS]` timestamps
- FFmpeg can extract frames at specific timestamps: `ffmpeg -ss HH:MM:SS -i video.mp4 -frames:v 1 screenshot.png`
- Could use semantic cues in speech to find key frames (words like "here", "this", "look at", "notice", "issue")

## Open questions

- What exact metadata shape should bind screenshots to transcript sections? (single timestamp, start/end range, section id, JSON sidecar, frontmatter block)
- Should screenshot capture be driven first by transcript cues, visual scene changes, or a simpler initial heuristic?
- Should Cesar emit one Markdown file plus an images folder only, or also emit a machine-readable sidecar for agents?
- Should this first version target local video files only, even though Cesar already supports URLs/YouTube?
- How much of the transcript should be preserved in the final review artifact versus summarized into issue-oriented sections?
