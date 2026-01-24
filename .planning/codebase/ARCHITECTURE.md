# Architecture

**Analysis Date:** 2026-01-23

## Pattern Overview

**Overall:** Layered CLI Application with Modular Components

**Key Characteristics:**
- Clean separation between CLI interface and core transcription logic
- Device-agnostic abstraction layer for hardware optimization
- Streaming-based processing for memory efficiency
- Dependency injection pattern for device detection and configuration

## Layers

**Presentation Layer (CLI):**
- Purpose: Handle user interaction, argument parsing, progress display
- Location: `cli.py`
- Contains: Click command definitions, Rich progress bars, user feedback
- Depends on: Core Layer (transcriber.py), Utility Layer (utils.py)
- Used by: Entry point (transcribe.py)

**Core Layer (Transcription):**
- Purpose: Audio transcription logic, model management, file validation
- Location: `transcriber.py`
- Contains: `AudioTranscriber` class with transcription workflow
- Depends on: Infrastructure Layer (device_detection.py), faster-whisper library
- Used by: CLI Layer

**Infrastructure Layer (Device Detection):**
- Purpose: Hardware capability detection, optimal configuration determination
- Location: `device_detection.py`
- Contains: `DeviceDetector`, `OptimalConfiguration`, `DeviceCapabilities` dataclass
- Depends on: System libraries (torch, subprocess for nvidia-smi)
- Used by: Core Layer

**Utility Layer:**
- Purpose: Shared helper functions for formatting and validation
- Location: `utils.py`
- Contains: Time formatting, model/device validation, processing time estimation
- Depends on: Standard library only
- Used by: CLI Layer, Core Layer

## Data Flow

**Transcription Request Flow:**

1. User invokes CLI with audio file path and options
2. CLI parses arguments, validates time parameters
3. `AudioTranscriber` instantiated with model/device preferences
4. `OptimalConfiguration` detects hardware, determines optimal settings
5. Input file validated (format, existence)
6. Output path validated (directory created if needed)
7. Audio duration retrieved via ffprobe
8. Whisper model lazy-loaded with optimal device/compute type
9. Transcription streams segments, writes to output file
10. Progress callback updates CLI display
11. Results returned with metrics (duration, speed ratio, language)

**State Management:**
- Model loaded lazily on first transcription (stored in `AudioTranscriber.model`)
- Device capabilities cached in `DeviceDetector._capabilities`
- No persistent state between CLI invocations

## Key Abstractions

**AudioTranscriber:**
- Purpose: Central orchestrator for transcription workflow
- Examples: `transcriber.py` lines 13-277
- Pattern: Facade pattern - hides complexity of model loading, device selection, file handling

**OptimalConfiguration:**
- Purpose: Strategy for determining optimal processing parameters
- Examples: `device_detection.py` lines 113-235
- Pattern: Strategy pattern - encapsulates hardware-specific optimization logic

**DeviceCapabilities:**
- Purpose: Value object representing system hardware capabilities
- Examples: `device_detection.py` lines 11-19
- Pattern: Dataclass - immutable representation of system state

**ProgressTracker:**
- Purpose: Manage progress display with throttling
- Examples: `cli.py` lines 28-67
- Pattern: Context manager with callback interface

## Entry Points

**Main Entry Point:**
- Location: `transcribe.py`
- Triggers: Direct CLI invocation (`python transcribe.py`)
- Responsibilities: Import and execute CLI main function

**CLI Command:**
- Location: `cli.py` function `main()` (lines 139-299)
- Triggers: Click framework routing
- Responsibilities: Parse arguments, validate inputs, invoke transcription, display results

**Programmatic API:**
- Location: `transcriber.py` class `AudioTranscriber`
- Triggers: Direct import and instantiation
- Responsibilities: Provide reusable transcription functionality without CLI

## Error Handling

**Strategy:** Exception-based with specific types for different failure modes

**Patterns:**
- `FileNotFoundError`: Input file missing
- `ValueError`: Invalid format, invalid parameter combinations
- `PermissionError`: Cannot create output directory or file
- `ImportError`: Missing faster-whisper dependency
- `RuntimeError`: ffprobe failure, transcription failure
- Model loading fallback: If GPU fails, falls back to CPU with float32

**Error Flow:**
```
CLI catches all exceptions -> Displays rich-formatted error -> Outputs plain text to stderr -> Returns exit code 1
```

## Cross-Cutting Concerns

**Logging:** No formal logging framework. Uses Rich console for user-facing output. Debug info available via `--verbose` flag.

**Validation:**
- Input validation in `AudioTranscriber.validate_input_file()` - checks existence, is-file, format
- Output validation in `AudioTranscriber.validate_output_path()` - checks/creates parent directory, write permission
- Time parameter validation in CLI `main()` - mutually exclusive options, range checks

**Authentication:** Not applicable - fully offline tool after model download

**Configuration:**
- Runtime: CLI arguments with Click type validation
- Environment: `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` set by `setup_environment()`
- Model caching: HuggingFace default at `~/.cache/huggingface/hub/`

---

*Architecture analysis: 2026-01-23*
