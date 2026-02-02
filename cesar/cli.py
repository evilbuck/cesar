"""
Click-based command line interface for audio transcription
"""
import logging
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import click
import uvicorn
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn
)

from cesar.config import (
    CesarConfig,
    ConfigError,
    load_config,
    get_cli_config_path,
)
from cesar.transcriber import AudioTranscriber
from cesar.utils import format_time, estimate_processing_time
from cesar.orchestrator import TranscriptionOrchestrator, OrchestrationResult
from cesar.diarization import DiarizationError, AuthenticationError
from cesar.whisperx_wrapper import WhisperXPipeline
from cesar.youtube_handler import (
    is_youtube_url,
    download_youtube_audio,
    cleanup_youtube_temp_dir,
    YouTubeDownloadError,
    YouTubeURLError,
    YouTubeUnavailableError,
    YouTubeRateLimitError,
    YouTubeAgeRestrictedError,
    YouTubeNetworkError,
    FFmpegNotFoundError,
)

try:
    from importlib.metadata import version
    __version__ = version("cesar")
except Exception:
    __version__ = "0.0.0"


# Create console for rich output
console = Console()

# Set up logger
logger = logging.getLogger(__name__)


@contextmanager
def download_progress(quiet: bool):
    """Show download progress spinner unless quiet mode."""
    if quiet:
        yield
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Downloading YouTube audio...", total=None)
        yield


class ProgressTracker:
    """Track and display transcription progress"""

    def __init__(self, show_progress: bool = True):
        self.show_progress = show_progress
        self.progress = None
        self.task_id = None
        self.last_update = time.time()

    def __enter__(self):
        if self.show_progress:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console
            )
            self.progress.__enter__()
            self.task_id = self.progress.add_task("Transcribing audio...", total=100)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, progress_percentage: float, segment_count: int, elapsed_time: float):
        """Update progress display (legacy callback for direct transcription)."""
        if self.progress and self.task_id is not None:
            # Update only every 0.5 seconds to avoid too frequent updates
            current_time = time.time()
            if current_time - self.last_update >= 0.5:
                self.progress.update(
                    self.task_id,
                    completed=progress_percentage,
                    description=f"Transcribing audio... ({segment_count} segments)"
                )
                self.last_update = current_time

    def update_step(self, step_name: str, percentage: float):
        """Update progress with step name and overall percentage (0-100).

        Args:
            step_name: Current step name ("Transcribing...", "Identifying speakers...", "Formatting...")
            percentage: Overall progress percentage (0-100)
        """
        if self.progress and self.task_id is not None:
            current_time = time.time()
            if current_time - self.last_update >= 0.5:
                self.progress.update(
                    self.task_id,
                    completed=percentage,
                    description=step_name
                )
                self.last_update = current_time


def get_hf_token(config: CesarConfig) -> Optional[str]:
    """Get HuggingFace token from config or environment.

    Priority: config file > HF_TOKEN env var > None (cached)
    """
    import os
    if config.hf_token:
        return config.hf_token
    return os.environ.get('HF_TOKEN')


def validate_output_extension(output_path: Path, diarize: bool, quiet: bool = False) -> Path:
    """Validate and correct output file extension based on diarization mode.

    Args:
        output_path: User-provided output path
        diarize: Whether diarization is enabled
        quiet: Whether to suppress warnings

    Returns:
        Corrected output path with appropriate extension (.md or .txt)
    """
    expected_ext = '.md' if diarize else '.txt'
    current_ext = output_path.suffix.lower()

    if current_ext != expected_ext:
        corrected_path = output_path.with_suffix(expected_ext)
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
        logger.info(f"Auto-corrected extension: {current_ext} -> {expected_ext}")
        return corrected_path
    return output_path


def show_diarization_summary(result: OrchestrationResult, verbose: bool, quiet: bool):
    """Display transcription summary with diarization details.

    Args:
        result: OrchestrationResult from orchestrator
        verbose: Whether to show per-speaker breakdown
        quiet: Whether to suppress non-essential output
    """
    if quiet:
        # Minimal output
        console.print(f"Transcription completed: {result.output_path}")
        return

    console.print(f"\n[bold green]Transcription completed![/bold green]")

    # Main summary line
    if result.diarization_succeeded:
        console.print(
            f"  {result.speakers_detected} speaker{'s' if result.speakers_detected != 1 else ''}, "
            f"{format_time(result.audio_duration)} duration"
        )
    else:
        console.print(f"  {format_time(result.audio_duration)} duration")
        console.print("[yellow]  (Speaker detection unavailable)[/yellow]")

    # Timing breakdown
    console.print(f"  Transcription: [blue]{format_time(result.transcription_time)}[/blue]")
    if result.diarization_time is not None:
        console.print(f"  Diarization: [blue]{format_time(result.diarization_time)}[/blue]")
    console.print(f"  Total: [blue]{format_time(result.total_processing_time)}[/blue]")
    console.print(f"  Speed ratio: [yellow]{result.speed_ratio:.1f}x[/yellow] faster than real-time")

    console.print(f"  Output saved to: [green]{result.output_path}[/green]")


@click.group()
@click.version_option(version=__version__, prog_name="cesar")
@click.pass_context
def cli(ctx):
    """Cesar: Offline audio transcription using faster-whisper"""
    # Clean up orphaned temp files from previous sessions on startup
    cleanup_youtube_temp_dir()

    # Load configuration
    config_path = get_cli_config_path()
    try:
        config = load_config(config_path)
        ctx.ensure_object(dict)
        ctx.obj['config'] = config
    except ConfigError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        sys.exit(1)

    # Show informational message if config file doesn't exist (not blocking)
    if not config_path.exists():
        # Check if we're in quiet mode by looking ahead at arguments
        quiet_mode = '-q' in sys.argv or '--quiet' in sys.argv
        if not quiet_mode:
            console.print(f"[dim]Config: {config_path} not found (using defaults)[/dim]")


@cli.command(name="transcribe")
@click.argument(
    'input_source',
    type=click.STRING,
    metavar='INPUT'
)
@click.option(
    '-o', '--output',
    required=True,
    type=click.Path(path_type=Path),
    help='Path for the output text file'
)
@click.option(
    '--model',
    type=click.Choice(['tiny', 'base', 'small', 'medium', 'large'], case_sensitive=False),
    default='base',
    show_default=True,
    help='Whisper model size to use'
)
@click.option(
    '--device',
    type=click.Choice(['auto', 'cpu', 'cuda', 'mps'], case_sensitive=False),
    default='auto',
    show_default=True,
    help='Force specific device for inference'
)
@click.option(
    '--compute-type',
    type=click.Choice(['auto', 'float32', 'float16', 'int8', 'int8_float16'], case_sensitive=False),
    default='auto',
    show_default=True,
    help='Force specific compute type'
)
@click.option(
    '--batch-size',
    type=click.IntRange(min=1, max=64),
    help='Batch size for processing (auto-detected if not specified)'
)
@click.option(
    '--num-workers',
    type=click.IntRange(min=1, max=32),
    help='Number of worker threads (auto-detected if not specified)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Show detailed system information and optimization hints'
)
@click.option(
    '--quiet', '-q',
    is_flag=True,
    help='Suppress progress display and non-essential output'
)
@click.option(
    '--max-duration',
    type=click.IntRange(min=1),
    help='Limit transcription to N minutes (from start or --start-time)'
)
@click.option(
    '--start-time',
    type=click.FloatRange(min=0),
    help='Start transcription at N seconds'
)
@click.option(
    '--end-time',
    type=click.FloatRange(min=0),
    help='End transcription at N seconds'
)
@click.option(
    '--diarize/--no-diarize',
    default=True,
    show_default=True,
    help='Enable speaker identification (disable with --no-diarize)'
)
@click.pass_context
def transcribe(ctx, input_source, output, model, device, compute_type, batch_size, num_workers, verbose, quiet, max_duration, start_time, end_time, diarize):
    """
    Transcribe audio files or YouTube videos to text using faster-whisper (offline)

    INPUT: Path to audio file or YouTube URL

    Supported audio formats: MP3, WAV, M4A, OGG, FLAC, AAC, WMA
    Supported URLs: YouTube videos (requires FFmpeg)
    """
    # Get config from context (config.diarize will be used in Phase 12)
    config = ctx.obj.get('config', CesarConfig())

    # Validate time parameter combinations first, before any operations
    if max_duration and end_time is not None:
        error_msg = "Error: --max-duration cannot be used with --end-time"
        console.print(f"[red]{error_msg}[/red]")
        click.echo(error_msg, err=True)
        sys.exit(1)

    # Calculate end time if start-time and max-duration are both provided
    if start_time is not None and max_duration is not None:
        calculated_end_time = start_time + (max_duration * 60)
        end_time = calculated_end_time

    if start_time is not None and end_time is not None and start_time >= end_time:
        error_msg = "Error: --start-time must be less than --end-time"
        console.print(f"[red]{error_msg}[/red]")
        click.echo(error_msg, err=True)
        sys.exit(1)

    # Track temp file for cleanup
    temp_audio_path = None

    try:
        # Set console quiet mode
        if quiet:
            console.quiet = True

        # Handle YouTube URLs vs file paths
        if input_source.startswith('http://') or input_source.startswith('https://'):
            # It's a URL
            if is_youtube_url(input_source):
                if not quiet:
                    console.print(f"[blue]Detected YouTube URL[/blue]")

                # Download will be handled with progress display in next section
                input_file = None  # Will be set after download
            else:
                # Non-YouTube URLs not supported in CLI
                error_msg = "Error: Only YouTube URLs are supported in CLI. For other URLs, use the API."
                console.print(f"[red]{error_msg}[/red]")
                click.echo(error_msg, err=True)
                sys.exit(1)
        else:
            # It's a file path - validate exists
            input_file = Path(input_source)
            if not input_file.exists():
                error_msg = f"Error: File not found: {input_source}"
                console.print(f"[red]{error_msg}[/red]")
                click.echo(error_msg, err=True)
                sys.exit(1)

        # Create transcriber instance
        transcriber = AudioTranscriber(
            model_size=model.lower(),
            device=device.lower() if device != 'auto' else None,
            compute_type=compute_type.lower() if compute_type != 'auto' else None,
            batch_size=batch_size,
            num_workers=num_workers
        )

        # Download YouTube audio if needed
        if input_file is None:
            # Must be a YouTube URL
            with download_progress(quiet):
                audio_path = download_youtube_audio(input_source)

            temp_audio_path = audio_path  # Mark for cleanup
            input_file = audio_path
            if not quiet:
                console.print(f"[green]Downloaded audio:[/green] {audio_path.name}")

        # Validate inputs and get basic info
        if input_file and not quiet:
            console.print(f"[green]Input file validated:[/green] {input_file}")

        # Get audio duration for estimation
        try:
            duration = transcriber.get_audio_duration(str(input_file))
            if not quiet:
                console.print(f"[blue]Audio duration:[/blue] {format_time(duration)}")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not determine audio duration: {e}[/yellow]")
            duration = 0

        # Show model information if verbose
        if verbose:
            model_info = transcriber.get_model_info()
            console.print("\n[bold]Model Configuration:[/bold]")
            console.print(f"  Model size: [cyan]{model_info['model_size']}[/cyan]")
            console.print(f"  Device: [cyan]{model_info['device']}[/cyan]")
            console.print(f"  Compute type: [cyan]{model_info['compute_type']}[/cyan]")
            console.print(f"  Batch size: [cyan]{model_info['batch_size']}[/cyan]")
            console.print(f"  Worker threads: [cyan]{model_info['num_workers']}[/cyan]")

            # Show device capabilities
            caps = model_info['capabilities']
            console.print("\n[bold]Device Capabilities:[/bold]")
            console.print(f"  CUDA available: [cyan]{caps['has_cuda']}[/cyan]")
            if caps['cuda_version']:
                console.print(f"  CUDA version: [cyan]{caps['cuda_version']}[/cyan]")
            if caps['gpu_memory_mb']:
                console.print(f"  GPU memory: [cyan]{caps['gpu_memory_mb']} MB[/cyan]")
            console.print(f"  Apple MPS available: [cyan]{caps['has_mps']}[/cyan]")
            console.print(f"  CPU cores: [cyan]{caps['cpu_cores']}[/cyan]")

            if duration > 0:
                estimated_time = estimate_processing_time(duration, model_info['model_size'])
                console.print(f"\n  Estimated processing time: [yellow]{format_time(estimated_time)}[/yellow]")
            console.print()

        # Validate output extension based on diarization mode
        output = validate_output_extension(output, diarize, quiet)

        # Validate output path
        transcriber.validate_output_path(str(output))
        if not quiet:
            console.print(f"[green]Output path validated:[/green] {output}")

        # Create pipeline if diarization enabled
        pipeline = None
        if diarize:
            hf_token = get_hf_token(config)
            # WhisperXPipeline handles token resolution internally (env, cache)
            # Create pipeline with model size passed through
            pipeline = WhisperXPipeline(
                model_name=model,
                hf_token=hf_token
            )

        # Set up progress tracking
        progress_tracker = ProgressTracker(show_progress=not quiet)

        # Start transcription
        if not quiet:
            console.print(f"\n[bold]Loading Whisper model '{model}'...[/bold]")

        transcription_start_time = time.time()

        with progress_tracker:
            if diarize and pipeline is not None:
                # Use orchestrator for diarized transcription
                orchestrator = TranscriptionOrchestrator(
                    pipeline=pipeline,
                    transcriber=transcriber  # Kept for fallback when diarization fails
                )

                # Pass min/max_speakers from config to orchestrate()
                result = orchestrator.orchestrate(
                    audio_path=input_file,
                    output_path=output,
                    enable_diarization=True,
                    min_speakers=config.min_speakers,
                    max_speakers=config.max_speakers,
                    progress_callback=lambda step, pct: progress_tracker.update_step(step, pct) if not quiet else None
                )

                # Show results with diarization info
                show_diarization_summary(result, verbose, quiet)
            else:
                # Use direct transcription (existing logic)
                result = transcriber.transcribe_file(
                    str(input_file),
                    str(output),
                    progress_callback=progress_tracker.update if not quiet else None,
                    max_duration_minutes=max_duration,
                    start_time_seconds=start_time,
                    end_time_seconds=end_time
                )

                # Show results (existing logic)
                if not quiet:
                    console.print(f"\n[bold green]Transcription completed![/bold green]")
                    console.print(f"  Language: [cyan]{result['language']}[/cyan] (probability: {result['language_probability']:.2f})")
                    console.print(f"  Audio duration: [blue]{format_time(result['audio_duration'])}[/blue]")
                    console.print(f"  Processing time: [blue]{format_time(result['processing_time'])}[/blue]")
                    console.print(f"  Speed ratio: [yellow]{result['speed_ratio']:.1f}x[/yellow] faster than real-time")
                    console.print(f"  Total segments: [cyan]{result['segment_count']}[/cyan]")
                    console.print(f"  Output saved to: [green]{result['output_path']}[/green]")
                else:
                    console.print(f"Transcription completed: {result['output_path']}")

        return 0

    except FFmpegNotFoundError as e:
        error_msg = str(e)
        console.print(f"[red]Error:[/red] {error_msg}")
        click.echo(f"Error: {error_msg}", err=True)
        sys.exit(1)
    except YouTubeDownloadError as e:
        error_msg = str(e)
        console.print(f"[red]YouTube Error:[/red] {error_msg}")
        click.echo(f"YouTube Error: {error_msg}", err=True)

        # Show cleaned underlying cause in verbose mode
        if verbose and e.__cause__:
            cause = str(e.__cause__).split('\n')[0]  # First line only
            console.print(f"[dim]  Cause: {cause}[/dim]")
            click.echo(f"  Cause: {cause}", err=True)

        sys.exit(1)
    except FileNotFoundError as e:
        error_msg = f"Error: {e}"
        console.print(f"[red]{error_msg}[/red]")
        click.echo(error_msg, err=True)  # Also output plain text for testing
        return 1
    except ValueError as e:
        error_msg = f"Error: {e}"
        console.print(f"[red]{error_msg}[/red]")
        click.echo(error_msg, err=True)
        return 1
    except PermissionError as e:
        error_msg = f"Error: {e}"
        console.print(f"[red]{error_msg}[/red]")
        click.echo(error_msg, err=True)
        return 1
    except ImportError as e:
        error_msg = f"Error: {e}"
        console.print(f"[red]{error_msg}[/red]")
        console.print("[yellow]Hint: Install faster-whisper with: pip install faster-whisper[/yellow]")
        click.echo(error_msg, err=True)
        click.echo("Hint: Install faster-whisper with: pip install faster-whisper", err=True)
        return 1
    except RuntimeError as e:
        error_msg = f"Error: {e}"
        console.print(f"[red]{error_msg}[/red]")
        click.echo(error_msg, err=True)
        return 1
    except KeyboardInterrupt:
        error_msg = "Transcription interrupted by user"
        console.print(f"\n[yellow]{error_msg}[/yellow]")
        click.echo(error_msg, err=True)
        return 1
    except AuthenticationError as e:
        # HuggingFace authentication failed - show helpful guidance
        error_msg = str(e)
        console.print(f"[red]Authentication Error:[/red] {error_msg}")
        click.echo(f"Authentication Error: {error_msg}", err=True)
        return 1
    except DiarizationError as e:
        # Diarization failed but orchestrator couldn't fall back (no transcriber)
        error_msg = str(e)
        console.print(f"[red]Speaker detection failed:[/red] {error_msg}")
        click.echo(f"Speaker detection failed: {error_msg}", err=True)
        return 1
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        console.print(f"[red]{error_msg}[/red]")
        click.echo(error_msg, err=True)
        if verbose:
            import traceback
            trace = traceback.format_exc()
            console.print(f"[dim]{trace}[/dim]")
            click.echo(trace, err=True)
        return 1
    finally:
        # Clean up temporary YouTube download if it exists
        if temp_audio_path and temp_audio_path.exists():
            try:
                temp_audio_path.unlink()
                logger.debug(f"Cleaned up temporary audio file: {temp_audio_path}")
            except Exception:
                pass  # Best effort cleanup


@cli.command(name="serve")
@click.option('--port', '-p', type=int, default=5000, show_default=True, help='Port to bind to')
@click.option('--host', '-h', default='127.0.0.1', show_default=True, help='Host to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
@click.option('--workers', type=int, default=1, show_default=True, help='Number of uvicorn workers')
def serve(port, host, reload, workers):
    """Start the Cesar HTTP API server."""
    # Print startup message (minimal per CONTEXT.md)
    console.print(f"Listening on http://{host}:{port}")

    # Start server (blocks until shutdown)
    uvicorn.run(
        "cesar.api.server:app",  # Import string required for reload
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level="info",
        access_log=True,
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    sys.exit(cli())
