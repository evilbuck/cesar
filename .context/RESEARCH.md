# Research: Cesar v2.4 Cache Foundation

## 1. Branch Summary
The current branch `transcript-speaker-formatting` is ~111 commits ahead of `master`. It represents a significant evolution of the project, primarily focused on:
- **WhisperX Migration (v2.3)**: Replacing the previous pyannote-based diarization with a unified WhisperX pipeline, which includes transcription, wav2vec2 alignment, and diarization.
- **Orchestrator Simplification**: Streamlining the transcription pipeline by removing the custom `timestamp_aligner.py` and leveraging WhisperX's internal alignment.
- **Interface Preservation**: Ensuring all CLI and API interfaces remain backward compatible despite the major backend changes.

## 2. Architecture Overview
Cesar follows a modular architecture:
- **CLI (`cesar/cli.py`)**: Click-based interface.
- **API (`cesar/api/`)**: FastAPI server with SQLite job persistence.
- **Orchestrator (`cesar/orchestrator.py`)**: The central pipeline coordinator. It uses `WhisperXPipeline` for transcription/diarization and falls back to `AudioTranscriber` (using `faster-whisper`) if diarization fails.
- **Transcription (`cesar/whisperx_wrapper.py`)**: Encapsulates the WhisperX pipeline.
- **Formatting (`cesar/transcript_formatter.py`)**: Utilities for generating Markdown/text transcripts.
- **YouTube (`cesar/youtube_handler.py`)**: Handles audio extraction using `yt-dlp`.

## 3. v2.4 Context (Phase 17: Cache Foundation)
The goal of Phase 17 is to implement content-addressable storage for intermediate artifacts.
- **Requirements**:
  - Cache directory at `~/.cache/cesar/` (XDG-compliant).
  - Atomic cache writes to prevent corruption on crashes.
  - YouTube audio downloads retrievable by URL.
  - Cache must survive crashes.

## 4. Key Files
- `cesar/orchestrator.py`: Core pipeline logic.
- `cesar/whisperx_wrapper.py`: WhisperX integration.
- `cesar/youtube_handler.py`: YouTube audio download.
- `cesar/cli.py`: CLI entry point.
- `cesar/api/server.py`: API server.
- `cesar/api/worker.py`: Background job worker.
- `cesar/transcript_formatter.py`: Transcript formatting.

## 5. Integration Points for Caching
- **YouTube Downloads**: Cache the extracted audio file based on the YouTube URL (and potentially a time-step for freshness).
- **Transcription Artifacts**: Cache the raw transcription segments (JSON) to skip re-transcription.
- **Diarization Artifacts**: Cache diarization results to skip re-diarization.

## 6. Existing Patterns
- **Configuration**: TOML-based configuration (`~/.config/cesar/config.toml`).
- **Error Handling**: Custom exception classes (e.g., `DiarizationError`, `AuthenticationError`) with structured error messages.
- **Testing**: `pytest` with comprehensive unit and E2E tests in `tests/`.
- **Persistence**: SQLite for job queue management.

## 7. Dependencies
Key dependencies from `pyproject.toml`:
- `faster-whisper>=1.0.0`
- `whisperx>=3.7.6`
- `yt-dlp>=2024.1.0`
- `fastapi>=0.109.0`
- `pydantic>=2.0.0`
- `aiosqlite>=0.22.0`
