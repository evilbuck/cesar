# Phase 11: Orchestration & Formatting - Research

**Researched:** 2026-02-01
**Domain:** Multi-step pipeline orchestration with progress reporting and Markdown transcript formatting
**Confidence:** HIGH

## Summary

This phase coordinates transcription with diarization and formats speaker-labeled output. The core challenge is orchestrating three sequential operations (transcribe → diarize → format) with unified progress reporting, graceful error handling, and clean Markdown output formatting.

The orchestrator pattern is the industry-standard approach for coordinating multi-step operations in Python. It uses a central controller that manages execution flow, handles errors with fallback mechanisms, and delegates work to specialized components. For progress reporting, Rich's Progress class supports multiple sequential tasks with individual task IDs, enabling a unified progress bar across all steps.

Output formatting uses standard Markdown with section headers for speakers and timestamp annotations. The industry standard for speaker diarization output combines speaker labels (Speaker A, Speaker B, etc.) with precise timestamps, typically in MM:SS or HH:MM:SS format.

**Primary recommendation:** Implement an orchestrator class that coordinates existing transcriber and diarizer components, use Rich Progress with multiple task IDs for step-by-step progress, implement try-except fallback for graceful degradation when diarization fails, and generate clean Markdown with section headers and timestamp annotations.

## Standard Stack

The established libraries/tools for pipeline orchestration and formatting:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Rich | 14.1.0+ | Progress bars and formatting | Project already uses Rich for all UI, supports multiple sequential tasks |
| Python dataclasses | Built-in | Immutable result objects | Standard library, frozen dataclasses for result objects prevent mutation |
| contextlib | Built-in | Context managers | Standard pattern for resource management and cleanup |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tempfile | Built-in | Temporary file management | For intermediate files with conditional cleanup based on debug flag |
| pathlib | Built-in | Path manipulation | File path handling, already used throughout project |
| logging | Built-in | Error and warning logging | Track alignment issues, fallback events |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Simple orchestrator class | Apache Airflow/Dagster | Airflow/Dagster are overkill for single-machine sequential pipeline, add significant complexity |
| Rich Progress | tqdm | Rich already used project-wide, provides better UI control and theming |
| Markdown string building | markdown-strings library | Direct string building is simpler and more transparent for simple format |

**Installation:**
No new dependencies required - all tools are either in the standard library or already project dependencies.

## Architecture Patterns

### Recommended Module Structure
```
cesar/
├── orchestrator.py          # NEW: Pipeline orchestration class
├── transcript_formatter.py  # NEW: Markdown formatting for speaker-labeled output
├── transcriber.py           # EXISTING: AudioTranscriber (unchanged)
├── diarization.py           # EXISTING: SpeakerDiarizer (unchanged)
├── timestamp_aligner.py     # EXISTING: Alignment logic (unchanged)
└── cli.py                   # MODIFIED: Add diarization orchestration call
```

### Pattern 1: Orchestrator Class with Sequential Steps
**What:** Central coordinator that manages execution flow, delegates to specialized components, handles errors with fallback
**When to use:** Multi-step pipelines where steps must execute sequentially and have dependencies

**Example:**
```python
# Source: Medium article on Orchestrator Pattern (2026)
# https://ronie.medium.com/the-orchestrator-pattern-managing-ai-work-at-scale-a0f798d7d0fb

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class OrchestrationResult:
    """Immutable result object for orchestration."""
    output_path: Path
    speakers_detected: int
    transcription_time: float
    diarization_time: Optional[float] = None
    formatting_time: Optional[float] = None
    diarization_succeeded: bool = True

class TranscriptionOrchestrator:
    """Coordinates transcription, diarization, and formatting."""

    def __init__(self, transcriber, diarizer, formatter):
        self.transcriber = transcriber
        self.diarizer = diarizer
        self.formatter = formatter

    def orchestrate(
        self,
        audio_path: Path,
        output_path: Path,
        enable_diarization: bool = True,
        keep_intermediate: bool = False
    ) -> OrchestrationResult:
        """Run full pipeline with error handling and fallback."""

        # Step 1: Transcribe (required)
        transcription_result = self.transcriber.transcribe(audio_path)

        if not enable_diarization:
            # Save plain transcript and return
            self._save_plain_transcript(transcription_result, output_path)
            return OrchestrationResult(
                output_path=output_path,
                speakers_detected=1,
                transcription_time=transcription_result.processing_time,
                diarization_succeeded=False
            )

        # Step 2: Diarize (optional, can fail gracefully)
        try:
            diarization_result = self.diarizer.diarize(audio_path)

            # Step 3: Format with speaker labels
            formatted_output = self.formatter.format_with_speakers(
                transcription_result,
                diarization_result
            )

            self._save_formatted_transcript(formatted_output, output_path)

            return OrchestrationResult(
                output_path=output_path,
                speakers_detected=diarization_result.speaker_count,
                transcription_time=transcription_result.processing_time,
                diarization_time=diarization_result.processing_time,
                diarization_succeeded=True
            )

        except Exception as e:
            # Fallback: Save plain transcript if diarization fails
            logger.warning(f"Diarization failed, falling back to plain transcript: {e}")
            self._save_plain_transcript(transcription_result, output_path)

            return OrchestrationResult(
                output_path=output_path,
                speakers_detected=1,
                transcription_time=transcription_result.processing_time,
                diarization_succeeded=False
            )
```

### Pattern 2: Rich Progress with Multiple Sequential Tasks
**What:** Use Rich Progress with multiple task IDs to show unified progress across sequential steps
**When to use:** Sequential operations where each step has different duration and you want single progress bar

**Example:**
```python
# Source: Rich documentation - Progress Display
# https://rich.readthedocs.io/en/latest/progress.html

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

def orchestrate_with_progress(self, audio_path, output_path):
    """Run orchestration with unified progress reporting."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:

        # Create task IDs for each step
        # Allocate progress: transcribe 60%, diarize 30%, format 10%
        overall_task = progress.add_task("Overall progress", total=100)

        # Step 1: Transcription (0-60%)
        progress.update(overall_task, description="Transcribing audio...")
        transcription_result = self.transcriber.transcribe(
            audio_path,
            progress_callback=lambda pct: progress.update(overall_task, completed=pct * 0.6)
        )
        progress.update(overall_task, completed=60)

        # Step 2: Diarization (60-90%)
        progress.update(overall_task, description="Detecting speakers...")
        diarization_result = self.diarizer.diarize(audio_path)
        progress.update(overall_task, completed=90)

        # Step 3: Formatting (90-100%)
        progress.update(overall_task, description="Formatting output...")
        formatted = self.formatter.format_with_speakers(
            transcription_result,
            diarization_result
        )
        progress.update(overall_task, completed=100)

        return formatted
```

### Pattern 3: Markdown Speaker Transcript Formatting
**What:** Generate clean Markdown with speaker section headers, timestamps, and metadata header
**When to use:** Formatting speaker-labeled transcripts for human readability

**Example:**
```python
# Based on CONTEXT decisions and industry patterns from AssemblyAI/pyannote

from datetime import datetime
from cesar.timestamp_aligner import format_timestamp

class TranscriptFormatter:
    """Format speaker-labeled transcripts as Markdown."""

    def format_with_speakers(
        self,
        aligned_segments,
        speaker_count,
        audio_duration,
        min_segment_duration=1.0
    ) -> str:
        """Generate Markdown transcript with speaker labels."""

        lines = []

        # Metadata header
        lines.append("# Transcript\n")
        lines.append(f"**Speakers:** {speaker_count} detected")
        lines.append(f"**Duration:** {self._format_duration(audio_duration)}")
        lines.append(f"**Created:** {datetime.now().strftime('%Y-%m-%d')}\n")
        lines.append("---\n")

        # Segments grouped by speaker
        current_speaker = None

        for segment in aligned_segments:
            # Skip very short segments if below threshold
            if (segment.end - segment.start) < min_segment_duration:
                continue

            # New speaker section
            if segment.speaker != current_speaker:
                current_speaker = segment.speaker
                lines.append(f"### {segment.speaker}")

            # Timestamp and text
            timestamp = f"[{format_timestamp(segment.start)} - {format_timestamp(segment.end)}]"
            lines.append(timestamp)
            lines.append(f"{segment.text}\n")

        return "\n".join(lines)

    def _format_duration(self, seconds: float) -> str:
        """Format duration as MM:SS or HH:MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)

        if minutes >= 60:
            hours = minutes // 60
            minutes = minutes % 60
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
```

### Pattern 4: Temporary Files with Conditional Cleanup
**What:** Use tempfile with conditional cleanup based on debug flag
**When to use:** Intermediate files that should be kept for debugging but cleaned up in production

**Example:**
```python
# Source: Python tempfile documentation and debugging best practices (2026)
# https://docs.python.org/3/library/tempfile.html

from tempfile import TemporaryDirectory
from pathlib import Path

def orchestrate_with_debug(
    self,
    audio_path: Path,
    output_path: Path,
    keep_intermediate: bool = False
) -> OrchestrationResult:
    """Run orchestration with optional intermediate file retention."""

    # Create temp directory with conditional cleanup
    with TemporaryDirectory(delete=not keep_intermediate) as tmpdir:
        temp_path = Path(tmpdir)

        # Save intermediate files with clear naming
        transcription_file = temp_path / "01-transcription.txt"
        diarization_file = temp_path / "02-diarization.json"

        # Run steps
        transcription = self.transcriber.transcribe(audio_path)
        if keep_intermediate:
            self._save_transcription(transcription, transcription_file)

        diarization = self.diarizer.diarize(audio_path)
        if keep_intermediate:
            self._save_diarization(diarization, diarization_file)

        # Final output (always saved)
        formatted = self.formatter.format_with_speakers(transcription, diarization)
        self._save_formatted(formatted, output_path)

        if keep_intermediate:
            logger.info(f"Intermediate files saved to: {tmpdir}")

        # Directory is auto-cleaned unless keep_intermediate=True
        return OrchestrationResult(output_path=output_path)
```

### Anti-Patterns to Avoid
- **Tight coupling**: Don't call transcriber/diarizer methods directly in CLI - use orchestrator for separation of concerns
- **Silent failures**: Don't catch exceptions without logging - user needs to know why diarization failed
- **Progress jumps**: Don't update progress bar discontinuously - allocate percentage ranges for smooth updates
- **Mutable results**: Don't use mutable dictionaries for results - use frozen dataclasses for immutability

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress bars | Custom print() statements | Rich Progress | Rich handles terminal size, colors, transient display, parallel tasks |
| Temporary files | Manual os.path logic | tempfile module | Handles cleanup, permissions, race conditions, platform differences |
| Timestamp formatting | Manual string manipulation | format_timestamp() function | Already implemented in timestamp_aligner.py with decisecond precision |
| Error logging | print() to stderr | logging module | Levels, formatting, filtering already configured project-wide |
| Path handling | String concatenation | pathlib.Path | Handles platform differences, safer operations, clearer code |

**Key insight:** Python's standard library provides robust solutions for file management and error handling. Use them instead of reimplementing. Rich is already a project dependency and handles all terminal UI concerns better than custom solutions.

## Common Pitfalls

### Pitfall 1: Progress Allocation Mismatch
**What goes wrong:** Allocating progress percentages that don't match actual step durations causes progress bar to move unevenly (fast then slow, or stuck then jump)
**Why it happens:** Transcription and diarization have very different performance characteristics depending on model size and audio length
**How to avoid:**
- Test with real audio files to determine typical time ratios
- Use conservative estimates (transcription: 60%, diarization: 30%, formatting: 10%)
- Consider making allocation configurable for different model sizes
**Warning signs:** Progress bar stays at 60% for extended time, or jumps from 90% to 100% instantly

### Pitfall 2: Silent Fallback Confusion
**What goes wrong:** User gets plain transcript when expecting speaker labels, doesn't know diarization failed
**Why it happens:** Fallback mechanism catches all exceptions and silently saves alternative output
**How to avoid:**
- Log warning message when falling back: "Diarization failed, saving plain transcript"
- Include note in output file: "# Transcript (speaker detection unavailable)"
- Return result object with diarization_succeeded flag for CLI to display warning
**Warning signs:** User reports "speaker labels not working" without seeing error messages

### Pitfall 3: File Extension Confusion
**What goes wrong:** Saving .md file with plain text content, or .txt file with Markdown formatting
**Why it happens:** Output path and content format get out of sync in fallback logic
**How to avoid:**
- Orchestrator should control output file extension based on format
- If diarization succeeds: use .md extension for Markdown
- If diarization fails: use .txt extension for plain text
- Document this behavior clearly in help text
**Warning signs:** User opens .md file and sees no formatting, or .txt file displays raw Markdown

### Pitfall 4: Segment Duration Threshold Confusion
**What goes wrong:** Too many tiny segments clutter output, or legitimate segments get filtered out
**Why it happens:** Threshold is hardcoded without considering different use cases (lectures vs conversations)
**How to avoid:**
- Make threshold configurable with sensible default (1.0 seconds recommended)
- Document in help text: "Minimum segment duration to include (default: 1s)"
- Log count of filtered segments: "Filtered 12 segments below 1.0s threshold"
**Warning signs:** Output missing obviously spoken content, or cluttered with many single-word segments

### Pitfall 5: Progress Callback Compatibility
**What goes wrong:** Orchestrator expects progress callback but underlying components don't support it consistently
**Why it happens:** transcriber.py has progress_callback but diarization.py might use different mechanism
**How to avoid:**
- Standardize on callback signature: `Callable[[float], None]` where float is 0-100 percentage
- Wrap components that use different mechanisms (like pyannote's ProgressHook)
- Allow None callback and check before calling
**Warning signs:** TypeError when calling progress_callback, diarization step shows no progress

### Pitfall 6: Intermediate File Naming Conflicts
**What goes wrong:** Multiple concurrent orchestrations overwrite each other's intermediate files
**Why it happens:** Using fixed filenames in shared temp directory
**How to avoid:**
- Use TemporaryDirectory which creates unique directory per orchestration
- If using shared directory, include timestamp or UUID in filenames
- Let tempfile module handle uniqueness automatically
**Warning signs:** Corrupted intermediate files, race conditions in testing

## Code Examples

Verified patterns from existing codebase and documentation:

### Example 1: Integration with Existing ProgressTracker
```python
# Source: cesar/cli.py (existing pattern)

class OrchestrationProgressTracker:
    """Adapt orchestrator to existing ProgressTracker pattern."""

    def __init__(self, progress_tracker):
        self.progress = progress_tracker

    def update_transcription_progress(self, percentage: float):
        """Update progress during transcription (0-60% of overall)."""
        if self.progress:
            overall_percentage = percentage * 0.6
            self.progress.update(overall_percentage)

    def update_diarization_progress(self, stage: str):
        """Update progress during diarization (60-90% of overall)."""
        if self.progress:
            # Diarization stages: embedding, clustering, resegmentation
            stage_map = {
                "embedding": 70,
                "clustering": 80,
                "resegmentation": 90
            }
            self.progress.update(stage_map.get(stage, 60))

    def update_formatting_progress(self):
        """Update progress during formatting (90-100% of overall)."""
        if self.progress:
            self.progress.update(95)
```

### Example 2: Graceful Fallback with Logging
```python
# Source: Python error handling best practices (2026)
# Based on: https://medium.com/@RampantLions/robust-error-handling-in-python

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def save_with_fallback(
    self,
    transcription_result,
    diarization_result,
    output_path: Path
) -> tuple[Path, bool]:
    """Save transcript with fallback to plain text on diarization failure."""

    try:
        # Attempt speaker-labeled Markdown format
        formatted = self.formatter.format_with_speakers(
            transcription_result.segments,
            diarization_result.speaker_count,
            transcription_result.audio_duration
        )

        # Use .md extension for Markdown
        output_path = output_path.with_suffix('.md')
        output_path.write_text(formatted, encoding='utf-8')

        logger.info(f"Speaker-labeled transcript saved to {output_path}")
        return output_path, True

    except Exception as e:
        # Fallback to plain text
        logger.warning(
            f"Failed to create speaker-labeled transcript: {e}. "
            f"Falling back to plain text format."
        )

        # Use .txt extension for plain text
        output_path = output_path.with_suffix('.txt')

        # Write plain transcript with note
        lines = [
            "# Transcript",
            "# (Speaker detection unavailable)",
            "",
            transcription_result.text
        ]
        output_path.write_text("\n".join(lines), encoding='utf-8')

        logger.info(f"Plain transcript saved to {output_path}")
        return output_path, False
```

### Example 3: Frozen Result Object
```python
# Source: Python dataclasses documentation
# https://docs.python.org/3/library/dataclasses.html

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class OrchestrationResult:
    """Immutable result from orchestration pipeline.

    Using frozen=True prevents accidental modification after creation.
    Use dataclasses.replace() to create modified copies if needed.
    """
    output_path: Path
    speakers_detected: int
    audio_duration: float
    transcription_time: float
    diarization_time: Optional[float]
    formatting_time: float
    diarization_succeeded: bool

    @property
    def total_processing_time(self) -> float:
        """Calculate total time across all steps."""
        base = self.transcription_time + self.formatting_time
        if self.diarization_time:
            base += self.diarization_time
        return base

    @property
    def speed_ratio(self) -> float:
        """Calculate processing speed vs real-time."""
        return self.audio_duration / self.total_processing_time
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tqdm for progress | Rich Progress | 2023-2024 | Better terminal integration, colors, multiple tasks, transient displays |
| Mutable dicts for results | frozen dataclasses | Python 3.7+ | Type safety, immutability, IDE support |
| Manual temp file cleanup | tempfile context managers | Always available but better used now | Safer cleanup, no leftover files |
| print() error messages | logging with levels | Standard practice but underused | Filterable, configurable, professional |
| String path manipulation | pathlib.Path | Python 3.4+ but widely adopted 2020+ | Cross-platform, safer, more readable |

**Deprecated/outdated:**
- Direct exception catching without logging: Modern practice is to log all exceptions for debugging
- Hardcoded progress percentages: Should be based on measured performance or configurable
- Single-format output: Industry moving toward format selection (plain/markdown/json/srt)

## Open Questions

1. **Progress percentage allocation**
   - What we know: Transcription typically takes 60-70% of total time, diarization 20-30%, formatting <10%
   - What's unclear: Exact ratios vary by model size, audio length, hardware
   - Recommendation: Use 60/30/10 split as default, measure actual times in testing, consider making configurable

2. **Minimum segment duration default**
   - What we know: Industry standard is 0.5-10 seconds per utterance, user decided "likely 1s" default
   - What's unclear: Optimal threshold for different use cases (lecture vs conversation vs podcast)
   - Recommendation: Start with 1.0 seconds, make configurable, add documentation about when to adjust

3. **Intermediate file formats**
   - What we know: Need to save transcription and diarization results for debugging
   - What's unclear: Best format for intermediate files (JSON, pickle, plain text)
   - Recommendation: Use JSON for diarization (serializable), plain text for transcription, include timestamps in filenames

4. **Metadata header fields**
   - What we know: Need speakers detected, duration, creation date (from CONTEXT decisions)
   - What's unclear: Whether to include model info, confidence scores, other metadata
   - Recommendation: Keep minimal for readability (speakers, duration, date), consider adding model info in comments

5. **File extension handling in fallback**
   - What we know: Should use .md for Markdown, .txt for plain text
   - What's unclear: What if user explicitly specifies .md but diarization fails?
   - Recommendation: Override user extension in fallback, log the change, document behavior

## Sources

### Primary (HIGH confidence)
- [Rich Progress Display Documentation](https://rich.readthedocs.io/en/latest/progress.html) - Official docs on multiple task progress tracking
- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) - Frozen dataclasses for immutable results
- [Python tempfile documentation](https://docs.python.org/3/library/tempfile.html) - Temporary file management with conditional cleanup
- Existing codebase: cesar/cli.py, cesar/transcriber.py, cesar/diarization.py, cesar/timestamp_aligner.py

### Secondary (MEDIUM confidence)
- [The Orchestrator Pattern: Managing AI Work at Scale](https://ronie.medium.com/the-orchestrator-pattern-managing-ai-work-at-scale-a0f798d7d0fb) - Medium article (Jan 2026) on orchestrator pattern
- [Robust Error Handling in Python: Graceful Degradation](https://medium.com/@RampantLions/robust-error-handling-in-python-tracebacks-graceful-degradation-and-suppression-11f7a140720b) - Error handling patterns
- [AssemblyAI: What is Speaker Diarization (2026 Guide)](https://www.assemblyai.com/blog/what-is-speaker-diarization-and-how-does-it-work) - Industry standard output formats
- [Data Pipeline Orchestration Tools: Top 6 Solutions in 2026](https://dagster.io/learn/data-pipeline-orchestration-tools) - Comparison of orchestration approaches

### Tertiary (LOW confidence)
- [Error Handling in Data Pipelines](https://medium.com/towards-data-engineering/error-handling-and-logging-in-data-pipelines-ensuring-data-reliability-227df82ba782) - General patterns, not Python-specific
- [Why and How to Write Frozen Dataclasses](https://plainenglish.io/blog/why-and-how-to-write-frozen-dataclasses-in-python-69050ad5c9d4) - Blog post with examples

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All recommendations use standard library or existing project dependencies
- Architecture: HIGH - Orchestrator pattern well-established, Rich Progress documented, existing codebase patterns verified
- Pitfalls: MEDIUM - Based on general Python/pipeline experience and existing codebase issues, not specific to this exact use case
- Output format: HIGH - User decisions in CONTEXT.md are clear, Markdown formatting is straightforward

**Research date:** 2026-02-01
**Valid until:** 30 days (stable domain - orchestration patterns and standard library don't change rapidly)
