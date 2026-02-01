# Phase 12: CLI Integration - Research

**Researched:** 2026-02-01
**Domain:** Click CLI flag design, Rich progress display, and output path handling
**Confidence:** HIGH

## Summary

This phase adds a user-facing CLI flag to enable/disable speaker diarization, integrates with the orchestrator from Phase 11, and enhances the CLI experience with proper progress display and output formatting. The orchestration layer is complete and working — this phase focuses on exposing it through the CLI interface with excellent UX.

The standard approach uses Click's boolean flag pattern with `--flag/--no-flag` syntax to provide explicit enable/disable options. Rich's Progress class supports multiple sequential tasks, ideal for showing transcription → diarization → formatting steps. Output path handling uses pathlib's `.with_suffix()` method to auto-correct extensions based on diarization mode, with clear warnings when paths are changed.

User experience best practices emphasize human-readable output over machine logs, warnings that explain actionable fixes, and progress indicators that show meaningful step names rather than technical jargon.

**Primary recommendation:** Use Click's `--diarize/--no-diarize` boolean flag pattern with default=True, extend the existing ProgressTracker class to support multiple sequential tasks, implement pathlib-based extension validation with warning messages, and add rich summary output showing per-step timing and speaker statistics.

## Standard Stack

The established libraries/tools for CLI integration:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Click | 8.0+ | CLI framework | Already used project-wide, supports boolean flags with --no- prefix natively |
| Rich | 14.1.0+ | Progress bars and formatting | Already used for all CLI output, supports multiple sequential task IDs |
| pathlib | Built-in | Path manipulation | Standard library, with_suffix() method for extension handling |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | Built-in | Warning and debug logging | Log fallback events, extension changes |
| os.environ | Built-in | Environment variables | HF_TOKEN environment variable reading |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Click | Typer | Typer has better type hints but adds dependency, Click already used project-wide |
| Rich Progress | tqdm | tqdm is simpler but less flexible, Rich already project standard |
| Argparse | Click/Typer | Argparse is stdlib but more verbose, Click already chosen |

**Installation:**
No new dependencies required - all tools are already project dependencies or stdlib.

## Architecture Patterns

### Recommended CLI Structure
```
cesar/cli.py modifications:
├── Add --diarize/--no-diarize flag to transcribe command
├── Extend ProgressTracker for multi-step progress
├── Add output extension validation with warnings
├── Add diarization summary output
└── Integrate with TranscriptionOrchestrator from Phase 11
```

### Pattern 1: Click Boolean Flags with Default True
**What:** Use Click's native `--flag/--no-flag` pattern for boolean options with default true
**When to use:** When you want explicit enable/disable flags that are self-documenting

**Example:**
```python
# Source: Click Documentation - Options
# https://click.palletsprojects.com/en/stable/options/

@click.option('--diarize/--no-diarize', default=True, show_default=True,
              help='Enable speaker identification (disable with --no-diarize)')
def transcribe(diarize, ...):
    """Transcribe audio with optional speaker diarization."""
    if diarize:
        # Run with diarization
        pass
    else:
        # Plain transcription only
        pass
```

**Key behaviors:**
- When slash `/` is in option string, Click automatically treats as boolean flag
- Both flags are shown in `--help` output
- `default=True` means diarization is on by default
- `show_default=True` makes the default visible in help text
- No `is_flag=True` needed when using slash syntax

### Pattern 2: Rich Multi-Step Progress Display
**What:** Use Rich Progress with multiple task IDs for sequential pipeline steps
**When to use:** Sequential operations where user needs to see which step is running

**Example:**
```python
# Source: Rich Documentation - Progress Display
# https://rich.readthedocs.io/en/stable/progress.html

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

class MultiStepProgressTracker:
    """Track progress across multiple pipeline steps."""

    def __init__(self, show_progress: bool = True):
        self.show_progress = show_progress
        self.progress = None
        self.current_task_id = None

    def __enter__(self):
        if self.show_progress:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console
            )
            self.progress.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update_step(self, step_name: str, percentage: float):
        """Update current step progress."""
        if self.progress:
            # Create new task for each step or update existing
            if self.current_task_id is None:
                self.current_task_id = self.progress.add_task(
                    step_name, total=100
                )
            else:
                # Update description and progress
                self.progress.update(
                    self.current_task_id,
                    description=step_name,
                    completed=percentage
                )
```

**Best practices:**
- Use context manager for automatic start/stop
- Update description to show current step name
- Use percentage-based progress (0-100) for consistency
- Support quiet mode by checking show_progress flag
- Buffer updates to avoid excessive rendering (0.5s minimum between updates)

### Pattern 3: Pathlib Extension Validation with Warnings
**What:** Use pathlib's `.with_suffix()` to change file extensions, warn user when auto-correcting
**When to use:** When output format depends on processing mode and user might provide wrong extension

**Example:**
```python
# Source: pathlib documentation and CLI best practices
# https://docs.python.org/3/library/pathlib.html

from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def validate_output_extension(
    output_path: Path,
    diarize: bool,
    quiet: bool = False
) -> Path:
    """Validate and correct output file extension based on mode.

    Args:
        output_path: User-provided output path
        diarize: Whether diarization is enabled
        quiet: Whether to suppress warnings

    Returns:
        Corrected output path with appropriate extension
    """
    expected_ext = '.md' if diarize else '.txt'
    current_ext = output_path.suffix

    if current_ext != expected_ext:
        corrected_path = output_path.with_suffix(expected_ext)

        # Warn user about auto-correction
        if not quiet:
            if diarize and current_ext == '.txt':
                console.print(
                    f"[yellow]Note: Changed output to {expected_ext} "
                    f"for speaker-labeled transcript[/yellow]"
                )
            elif not diarize and current_ext == '.md':
                console.print(
                    f"[yellow]Note: Changed output to {expected_ext} "
                    f"for plain transcript[/yellow]"
                )

        logger.info(
            f"Auto-corrected extension: {current_ext} → {expected_ext} "
            f"(diarize={diarize})"
        )
        return corrected_path

    return output_path
```

**Key behaviors:**
- `.with_suffix()` returns new Path with changed extension
- Original path object is not modified (immutable)
- Works correctly with compound extensions (.tar.gz replaces only .gz)
- Warnings are human-friendly, not technical logs
- Logging captures change for debugging without cluttering user output

### Pattern 4: Environment Variable Token Reading
**What:** Read HuggingFace token from environment variable as fallback
**When to use:** Sensitive credentials that shouldn't be CLI arguments

**Example:**
```python
# Source: Python os.environ documentation
import os
from cesar.config import CesarConfig

def get_hf_token(config: CesarConfig) -> Optional[str]:
    """Get HuggingFace token from config or environment.

    Priority:
    1. Config file value
    2. HF_TOKEN environment variable
    3. None (will use cached token)

    Args:
        config: Loaded configuration

    Returns:
        HF token or None
    """
    if config.hf_token:
        return config.hf_token

    return os.environ.get('HF_TOKEN')
```

**Best practices:**
- Never expose tokens in CLI flags or help text
- Document environment variable in error messages
- Config file > environment > cached token hierarchy
- Silent fallback to cached token (no warning if HF_TOKEN unset)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Boolean CLI flags | Custom --enable/--disable parsing | Click's `--flag/--no-flag` | Click handles all edge cases, auto-generates help text |
| Multi-step progress bars | Sequential print statements | Rich Progress with task IDs | Rich handles timing, rendering, terminal size automatically |
| Path extension changes | String manipulation on path strings | pathlib.Path.with_suffix() | Handles edge cases like compound extensions, no-extension files |
| Time formatting | Custom MM:SS string building | Existing utils.format_time() | Already handles seconds, minutes, hours with proper formatting |
| Environment variable reading | Custom env parsing | os.environ.get() with default | Stdlib handles encoding, missing vars correctly |

**Key insight:** CLI frameworks and pathlib exist specifically to handle the edge cases you won't think of until users hit them. String manipulation on paths breaks on Windows; custom time formatting doesn't handle edge cases like negative times or extreme durations.

## Common Pitfalls

### Pitfall 1: Boolean Flag Default Not Shown in Help
**What goes wrong:** User can't tell if diarization is on or off by default without trying it
**Why it happens:** Forgetting `show_default=True` on Click option decorator
**How to avoid:** Always use `show_default=True` for boolean flags
**Warning signs:** Help text doesn't show `[default: True]` or `[default: False]`

**Example:**
```python
# BAD: Default is invisible
@click.option('--diarize/--no-diarize', default=True)

# GOOD: Default is explicit
@click.option('--diarize/--no-diarize', default=True, show_default=True)
```

### Pitfall 2: Progress Bar Flickering from Too-Frequent Updates
**What goes wrong:** Progress bar updates so fast it flickers or slows down processing
**Why it happens:** Updating Rich Progress on every segment without throttling
**How to avoid:** Throttle updates to max once per 0.5 seconds
**Warning signs:** Progress bar looks jittery, processing slower than expected

**Example:**
```python
# Already implemented correctly in cli.py ProgressTracker:
def update(self, progress_percentage: float, segment_count: int, elapsed_time: float):
    """Update progress display"""
    if self.progress and self.task_id is not None:
        # Update only every 0.5 seconds to avoid too frequent updates
        current_time = time.time()
        if current_time - self.last_update >= 0.5:
            self.progress.update(...)
            self.last_update = current_time
```

### Pitfall 3: Silent Extension Changes Confuse Users
**What goes wrong:** User specifies `output.txt`, gets `output.md`, doesn't know why
**Why it happens:** Auto-correcting extension without warning message
**How to avoid:** Print warning when changing extension, explain why
**Warning signs:** GitHub issues asking "why is my output file named differently?"

**Example:**
```python
# BAD: Silent change
output_path = output_path.with_suffix('.md')

# GOOD: Explained change
if output_path.suffix != '.md':
    console.print("[yellow]Note: Changed output to .md for speaker-labeled transcript[/yellow]")
    output_path = output_path.with_suffix('.md')
```

### Pitfall 4: Progress Steps Don't Match Actual Work
**What goes wrong:** Progress shows "60% complete" but visibly stuck for minutes
**Why it happens:** Progress allocation doesn't match actual time distribution
**How to avoid:** Use Phase 11 timing allocations: 0-60% transcription, 60-90% diarization, 90-100% formatting
**Warning signs:** Progress jumps forward or hangs at certain percentages

**Reference from STATE.md:**
```
v2.4: Progress allocation 0-60% transcription, 60-90% diarization, 90-100% formatting
```

### Pitfall 5: Verbose Mode Showing Too Much Technical Detail
**What goes wrong:** Verbose output overwhelms user with internal state, not helpful info
**Why it happens:** Dumping debug logs instead of curated detailed info
**How to avoid:** Verbose means "more detail about what's happening", not "show all logs"
**Warning signs:** Verbose output includes stack traces, memory addresses, internal variable names

**Example from CONTEXT.md:**
```python
# GOOD: Verbose adds useful user-facing detail
if verbose:
    console.print("  Speaker 1: 4:23 (35%)")
    console.print("  Speaker 2: 5:11 (42%)")

# BAD: Verbose dumps technical internals
if verbose:
    console.print(f"  Diarizer pipeline object: {repr(self.diarizer)}")
    console.print(f"  Memory usage: {sys.getsizeof(segments)} bytes")
```

## Code Examples

Verified patterns from official sources:

### Integrating Orchestrator with CLI Progress
```python
# Based on existing cli.py ProgressTracker and Phase 11 orchestrator.py

from cesar.orchestrator import TranscriptionOrchestrator
from cesar.diarization import SpeakerDiarizer

# In transcribe command:
if diarize and config.hf_token:
    # Create diarizer
    diarizer = SpeakerDiarizer(
        hf_token=get_hf_token(config),
        min_speakers=config.min_speakers,
        max_speakers=config.max_speakers
    )

    # Create orchestrator
    orchestrator = TranscriptionOrchestrator(
        transcriber=transcriber,
        diarizer=diarizer
    )

    # Callback that updates progress with step name
    def progress_callback(step_name: str, percentage: float):
        if not quiet:
            progress_tracker.update_step(step_name, percentage)

    # Run orchestration
    result = orchestrator.orchestrate(
        audio_path=input_file,
        output_path=output,
        enable_diarization=True,
        progress_callback=progress_callback
    )

    # Show results
    if not quiet:
        console.print(f"\n[bold green]Transcription completed![/bold green]")
        console.print(f"  Speakers detected: [cyan]{result.speakers_detected}[/cyan]")
        console.print(f"  Transcription time: [blue]{format_time(result.transcription_time)}[/blue]")
        if result.diarization_succeeded:
            console.print(f"  Diarization time: [blue]{format_time(result.diarization_time)}[/blue]")
        console.print(f"  Total time: [blue]{format_time(result.total_processing_time)}[/blue]")
```

### Summary Output with Per-Speaker Stats
```python
# Based on CONTEXT.md specifications

def show_summary(result: OrchestrationResult, verbose: bool, quiet: bool):
    """Display transcription summary with optional per-speaker breakdown."""
    if quiet:
        # Minimal output
        console.print(f"Transcription completed: {result.output_path}")
        return

    # Standard summary
    console.print(f"\n[bold green]Transcription completed![/bold green]")

    if result.diarization_succeeded:
        console.print(
            f"  {result.speakers_detected} speakers, "
            f"{result.segment_count} segments, "
            f"{format_time(result.audio_duration)} duration"
        )
    else:
        console.print(
            f"  {result.segment_count} segments, "
            f"{format_time(result.audio_duration)} duration"
        )
        console.print("[yellow]  (Speaker detection unavailable)[/yellow]")

    # Timing breakdown
    console.print(f"  Transcription: [blue]{format_time(result.transcription_time)}[/blue]")
    if result.diarization_time:
        console.print(f"  Diarization: [blue]{format_time(result.diarization_time)}[/blue]")
    console.print(f"  Total: [blue]{format_time(result.total_processing_time)}[/blue]")

    # Verbose: per-speaker stats
    if verbose and result.speaker_stats:
        console.print("\n[bold]Per-speaker breakdown:[/bold]")
        for speaker, stats in result.speaker_stats.items():
            duration = stats['duration']
            percentage = stats['percentage']
            console.print(f"  {speaker}: {format_time(duration)} ({percentage}%)")

    console.print(f"  Output saved to: [green]{result.output_path}[/green]")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single is_flag boolean | --flag/--no-flag pattern | Click 7.x+ | More explicit, better UX for default=True flags |
| Print statements for progress | Rich Progress library | 2020+ | Professional UI, automatic terminal handling |
| os.path string manipulation | pathlib.Path objects | Python 3.4+ | Type-safe, cross-platform, cleaner API |
| Manual time formatting | utils.format_time() helper | Project v1.0 | Consistent formatting, handles edge cases |
| Config only in files | Config + environment variables | Modern pattern | Easier CI/CD, Docker deployment |

**Deprecated/outdated:**
- Manual string concatenation for paths: Use pathlib.Path / operator
- Custom progress bar implementations: Use Rich or tqdm
- Boolean flags without --no- prefix: Hard to disable defaults

## Open Questions

Things that couldn't be fully resolved:

1. **Per-speaker statistics calculation**
   - What we know: OrchestrationResult doesn't currently track per-speaker durations
   - What's unclear: Should this be calculated in formatter, orchestrator, or new component?
   - Recommendation: Add to TranscriptFormatter if verbose mode needed, otherwise defer to future phase

2. **Segment count in diarized output**
   - What we know: Aligned segments may differ from transcription segment count
   - What's unclear: Should we report transcription segments, aligned segments, or both?
   - Recommendation: Report aligned segment count when diarized, transcription count when plain

3. **Fallback warning message timing**
   - What we know: Diarization can fail after transcription succeeds
   - What's unclear: Should warning show during processing or only in summary?
   - Recommendation: Show immediately when fallback occurs (user knows diarization failed), repeat in summary

## Sources

### Primary (HIGH confidence)
- [Click Options Documentation](https://click.palletsprojects.com/en/stable/options/) - Boolean flag patterns
- [Rich Progress Documentation](https://rich.readthedocs.io/en/stable/progress.html) - Multi-step progress
- [pathlib Documentation](https://docs.python.org/3/library/pathlib.html) - Path.with_suffix() behavior
- Existing codebase: cesar/cli.py, cesar/orchestrator.py, cesar/utils.py

### Secondary (MEDIUM confidence)
- [Command Line Interface Guidelines](https://clig.dev/) - UX best practices
- [Real Python - Click Guide](https://realpython.com/python-click/) - Click patterns
- Existing patterns from Phase 11 research (orchestrator, progress allocation)

### Tertiary (LOW confidence)
- None - all findings verified against official documentation or existing codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use, verified with official docs
- Architecture: HIGH - Patterns match existing codebase style, verified with Click/Rich docs
- Pitfalls: HIGH - Based on existing code review and official documentation warnings

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (30 days - stable technology stack)
