"""
Click-based command line interface for audio transcription
"""

import inspect
import json
import logging
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from cesar.config import (
    CesarConfig,
    ConfigError,
    load_config,
    get_cli_config_path,
)
from cesar.transcriber import AudioTranscriber
from cesar.utils import format_time, estimate_processing_time
from cesar.orchestrator import TranscriptionOrchestrator, OrchestrationResult, AgentReviewOrchestrator, AgentReviewResult
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

CLI_CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "max_content_width": 100,
}

CLI_WORKFLOWS = [
    "cesar transcribe meeting.mp3 -o meeting.md",
    "cesar transcribe note.m4a -o note.txt --no-diarize --quiet",
    'cesar transcribe "https://youtube.com/watch?v=VIDEO_ID" -o transcript.txt',
    "cesar serve --host 0.0.0.0 --port 5000",
    "cesar commands --json",
]

CLI_AGENT_TIPS = [
    "--quiet reduces progress UI noise",
    "--no-diarize produces plain text output",
    "serve is better for async or multi-job integrations",
    "commands --json emits a machine-readable CLI manifest",
]

COMMAND_METADATA = {
    "commands": {
        "best_for": ["agent discovery", "automation bootstrap", "capability inspection"],
        "examples": [
            "cesar commands",
            "cesar commands --json",
        ],
    },
    "transcribe": {
        "best_for": ["one-shot transcription", "batch scripting", "YouTube-to-text"],
        "examples": [
            "cesar transcribe audio.mp3 -o transcript.md",
            "cesar transcribe audio.mp3 -o transcript.txt --no-diarize --quiet",
            'cesar transcribe "https://youtube.com/watch?v=VIDEO_ID" -o transcript.txt',
        ],
    },
    "serve": {
        "best_for": ["HTTP integrations", "async job submission", "multi-client workflows"],
        "examples": [
            "cesar serve",
            "cesar serve --port 8080 --reload",
            "cesar serve --host 0.0.0.0 --workers 4",
        ],
    },
    "skill": {
        "best_for": ["agent skill deployment", "IDE integration setup"],
        "examples": [
            "cesar skill install",
            "cesar skill install --path ~/projects/my-app",
        ],
    },
}


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
                console=console,
            )
            self.progress.__enter__()
            self.task_id = self.progress.add_task("Transcribing audio...", total=100)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            self.progress.__exit__(exc_type, exc_val, exc_tb)

    def update(
        self, progress_percentage: float, segment_count: int, elapsed_time: float
    ):
        """Update progress display (legacy callback for direct transcription)."""
        if self.progress and self.task_id is not None:
            # Update only every 0.5 seconds to avoid too frequent updates
            current_time = time.time()
            if current_time - self.last_update >= 0.5:
                self.progress.update(
                    self.task_id,
                    completed=progress_percentage,
                    description=f"Transcribing audio... ({segment_count} segments)",
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
                    self.task_id, completed=percentage, description=step_name
                )
                self.last_update = current_time


def get_hf_token(config: CesarConfig) -> Optional[str]:
    """Get HuggingFace token from config or environment.

    Priority: config file > HF_TOKEN env var > None (cached)
    """
    import os

    if config.hf_token:
        return config.hf_token
    return os.environ.get("HF_TOKEN")


def validate_output_extension(
    output_path: Path, diarize: bool, quiet: bool = False
) -> Path:
    """Validate and correct output file extension based on diarization mode.

    Args:
        output_path: User-provided output path
        diarize: Whether diarization is enabled
        quiet: Whether to suppress warnings

    Returns:
        Corrected output path with appropriate extension (.md or .txt)
    """
    expected_ext = ".md" if diarize else ".txt"
    current_ext = output_path.suffix.lower()

    if current_ext != expected_ext:
        corrected_path = output_path.with_suffix(expected_ext)
        if not quiet:
            if diarize and current_ext == ".txt":
                console.print(
                    f"[yellow]Note: Changed output to {expected_ext} "
                    f"for speaker-labeled transcript[/yellow]"
                )
            elif not diarize and current_ext == ".md":
                console.print(
                    f"[yellow]Note: Changed output to {expected_ext} "
                    f"for plain transcript[/yellow]"
                )
        logger.info(f"Auto-corrected extension: {current_ext} -> {expected_ext}")
        return corrected_path
    return output_path


def _clean_help_text(text: Optional[str]) -> str:
    """Normalize Click doc/help text for display and JSON output."""
    if not text:
        return ""

    return inspect.cleandoc(text).replace("``", "").replace("\b", "")


def _serialize_param(param: click.Parameter) -> dict:
    """Serialize a Click parameter into JSON-safe metadata."""
    param_type = getattr(param.type, "name", param.type.__class__.__name__.lower())
    param_name = param.name
    if isinstance(param, click.Option):
        long_flag = next((opt for opt in param.opts if opt.startswith("--")), None)
        if long_flag is not None:
            param_name = long_flag.lstrip("-").replace("-", "_")

    data = {
        "name": param_name,
        "kind": "option" if isinstance(param, click.Option) else "argument",
        "required": param.required,
        "type": param_type,
    }

    if isinstance(param.type, click.Choice):
        data["choices"] = list(param.type.choices)

    if isinstance(param, click.Option):
        data["flags"] = [*param.opts, *param.secondary_opts]
        data["help"] = (param.help or "").strip()
        data["is_flag"] = param.is_flag
        if param.default is not None and param.default != ():
            data["default"] = param.default
        if param.multiple:
            data["multiple"] = True
        if param.nargs != 1:
            data["nargs"] = param.nargs
    else:
        data["metavar"] = param.metavar or param.human_readable_name.upper()
        if param.nargs != 1:
            data["nargs"] = param.nargs

    return data


def build_cli_manifest() -> dict:
    """Build a machine-readable manifest of the CLI surface."""
    commands = []
    for command_name, command in cli.commands.items():
        metadata = COMMAND_METADATA.get(command_name, {})
        params = [_serialize_param(param) for param in command.params]
        commands.append(
            {
                "name": command_name,
                "summary": (command.short_help or "").strip(),
                "description": _clean_help_text(command.help),
                "best_for": metadata.get("best_for", []),
                "examples": metadata.get("examples", []),
                "arguments": [param for param in params if param["kind"] == "argument"],
                "options": [param for param in params if param["kind"] == "option"],
            }
        )

    return {
        "schema_version": "1",
        "name": "cesar",
        "version": __version__,
        "summary": "Offline audio transcription for local files and YouTube URLs.",
        "workflows": CLI_WORKFLOWS,
        "automation_tips": CLI_AGENT_TIPS,
        "commands": commands,
    }


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
    console.print(
        f"  Transcription: [blue]{format_time(result.transcription_time)}[/blue]"
    )
    if result.diarization_time is not None:
        console.print(
            f"  Diarization: [blue]{format_time(result.diarization_time)}[/blue]"
        )
    console.print(f"  Total: [blue]{format_time(result.total_processing_time)}[/blue]")
    console.print(
        f"  Speed ratio: [yellow]{result.speed_ratio:.1f}x[/yellow] faster than real-time"
    )

    console.print(f"  Output saved to: [green]{result.output_path}[/green]")


@click.group(context_settings=CLI_CONTEXT_SETTINGS, no_args_is_help=True)
@click.version_option(version=__version__, prog_name="cesar")
@click.pass_context
def cli(ctx):
    """Offline audio transcription for local files and YouTube URLs.

    Use ``transcribe`` for one-shot CLI runs and ``serve`` for the HTTP API.

    \b
    Common workflows:
      cesar transcribe meeting.mp3 -o meeting.md
      cesar transcribe note.m4a -o note.txt --no-diarize --quiet
      cesar transcribe "https://youtube.com/watch?v=VIDEO_ID" -o transcript.txt
      cesar serve --host 0.0.0.0 --port 5000
      cesar commands --json

    \b
    Agent / automation tips:
      - ``--quiet`` reduces progress UI noise
      - ``--no-diarize`` produces plain text output
      - ``serve`` is better for async or multi-job integrations
      - ``commands --json`` emits a machine-readable CLI manifest
    """
    # Clean up orphaned temp files from previous sessions on startup
    cleanup_youtube_temp_dir()

    # Load configuration
    config_path = get_cli_config_path()
    try:
        config = load_config(config_path)
        ctx.ensure_object(dict)
        ctx.obj["config"] = config
    except ConfigError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        sys.exit(1)

    # Show informational message if config file doesn't exist (not blocking)
    # Suppress during --help or --version to keep discovery output clean
    if not config_path.exists():
        help_mode = "--help" in sys.argv or "-h" in sys.argv
        quiet_mode = "-q" in sys.argv or "--quiet" in sys.argv
        discovery_mode = "commands" in sys.argv[1:]
        if not quiet_mode and not help_mode and not discovery_mode:
            console.print(
                f"[dim]Config: {config_path} not found (using defaults)[/dim]"
            )


@cli.command(
    name="commands",
    short_help="Describe CLI commands in text or JSON.",
    context_settings=CLI_CONTEXT_SETTINGS,
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON discovery data")
def commands(as_json):
    """Describe Cesar's CLI surface for humans or automation.

    Use ``--json`` to emit a machine-readable manifest with commands, arguments,
    options, examples, and recommended usage.

    \b
    Examples:
      cesar commands
      cesar commands --json
    """
    manifest = build_cli_manifest()

    if as_json:
        click.echo(json.dumps(manifest, indent=2))
        return 0

    click.echo(f"Cesar CLI discovery (v{manifest['version']})")
    click.echo("Use 'cesar commands --json' for machine-readable output.\n")
    for command in manifest["commands"]:
        click.echo(f"- {command['name']}: {command['summary']}")
        if command["best_for"]:
            click.echo(f"  best for: {', '.join(command['best_for'])}")
        if command["examples"]:
            click.echo(f"  example: {command['examples'][0]}")
    return 0


@cli.command(
    name="skill",
    short_help="Manage agent skills for IDE integration.",
    context_settings=CLI_CONTEXT_SETTINGS,
)
@click.argument("action", type=click.Choice(["install"]))
@click.option(
    "--path", "target_path",
    type=click.Path(path_type=Path),
    default=".",
    show_default="current directory",
    help="Project directory to install the skill into",
)
@click.option(
    "--global", "global_install",
    is_flag=True,
    help="Install globally for all agent platforms (Pi, Claude Code, OpenCode, Codex)",
)
@click.option(
    "--platform", "platforms",
    multiple=True,
    type=click.Choice(["pi", "claude", "opencode", "codex", "agents"]),
    help="Install to specific platform(s). Can be repeated. Default: all platforms.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing skill if it already exists",
)
def skill(action, target_path, global_install, platforms, force):
    """Deploy the Cesar agent skill for AI agent integration.

    By default, installs into ``<path>/.agents/skills/`` for the current project.
    Use ``--global`` to install across all agent platforms globally.

    \b
    Examples:
      cesar skill install                 # Install into current project
      cesar skill install --path ~/proj   # Install into a specific project
      cesar skill install --global        # Install globally for all platforms
      cesar skill install --global --platform pi --platform claude  # Specific platforms
      cesar skill install --force         # Overwrite existing skill
    """
    if action == "install":
        if global_install:
            _install_skill_global(platforms, force)
        else:
            _install_skill(target_path, force)


# Global skill directories for each agent platform
_GLOBAL_SKILL_DIRS = {
    "pi": Path.home() / ".pi" / "agent" / "skills",
    "claude": Path.home() / ".claude" / "skills",
    "opencode": Path.home() / ".config" / "opencode" / "skills",
    "codex": Path.home() / ".codex" / "skills",
    "agents": Path.home() / ".agents" / "skills",
}


def _get_source_skill() -> Path:
    """Locate the bundled skill directory in the package."""
    package_dir = Path(__file__).parent
    source_skill = package_dir / "skills" / "cesar-transcribe"
    if not source_skill.is_dir():
        raise click.ClickException(
            "Agent skill not found in package. "
            "Reinstall cesar to get the bundled skill."
        )
    return source_skill


def _copy_skill(source: Path, dest: Path, force: bool = False) -> bool:
    """Copy skill files from source to dest. Returns True if installed."""
    skill_dest = dest / "cesar-transcribe"

    if skill_dest.exists() and not force:
        console.print(f"[yellow]⊘[/yellow] Already exists at {skill_dest} (use --force to overwrite)")
        return False

    skill_dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        dest_file = skill_dest / item.name
        if item.is_file():
            shutil.copy2(item, dest_file)
        elif item.is_dir():
            if dest_file.exists():
                shutil.rmtree(dest_file)
            shutil.copytree(item, dest_file)

    console.print(f"[green]✓[/green] Installed cesar-transcribe skill to {skill_dest}")
    return True


def _install_skill(target_path: Path, force: bool = False) -> None:
    """Copy bundled skill files into the target project's .agents/skills/ directory."""
    source_skill = _get_source_skill()
    skill_dir = target_path.resolve() / ".agents" / "skills"
    installed = _copy_skill(source_skill, skill_dir, force)
    if installed:
        console.print(
            "[dim]Agents in this project can now transcribe audio using Cesar.[/dim]"
        )


def _install_skill_global(platforms: tuple, force: bool = False) -> None:
    """Install skill globally for one or more agent platforms."""
    source_skill = _get_source_skill()

    # Default to all platforms if none specified
    target_platforms = dict(_GLOBAL_SKILL_DIRS)
    if platforms:
        target_platforms = {
            name: path for name, path in target_platforms.items()
            if name in platforms
        }

    installed_count = 0
    for name, skill_dir in target_platforms.items():
        console.print(f"[dim]Installing for {name}...[/dim]")
        if _copy_skill(source_skill, skill_dir, force):
            installed_count += 1

    if installed_count > 0:
        platform_names = ", ".join(target_platforms.keys())
        console.print(
            f"\n[green]✓[/green] Installed cesar-transcribe skill globally "
            f"({installed_count}/{len(target_platforms)} platforms: {platform_names})"
        )
        console.print(
            "[dim]Agents on this machine can now transcribe audio using Cesar.[/dim]"
        )
    else:
        console.print(
            "[yellow]No new installations. Use --force to overwrite existing skills.[/yellow]"
        )


@cli.command(
    name="transcribe",
    short_help="Transcribe a local audio file or YouTube URL.",
    context_settings=CLI_CONTEXT_SETTINGS,
)
@click.argument("input_source", type=click.STRING, metavar="INPUT")
@click.option(
    "-o",
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Path for the output text file",
)
@click.option(
    "--model",
    type=click.Choice(
        ["tiny", "base", "small", "medium", "large"], case_sensitive=False
    ),
    default="base",
    show_default=True,
    help="Whisper model size to use",
)
@click.option(
    "--device",
    type=click.Choice(["auto", "cpu", "cuda", "mps"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Force specific device for inference",
)
@click.option(
    "--compute-type",
    type=click.Choice(
        ["auto", "float32", "float16", "int8", "int8_float16"], case_sensitive=False
    ),
    default="auto",
    show_default=True,
    help="Force specific compute type",
)
@click.option(
    "--batch-size",
    type=click.IntRange(min=1, max=64),
    help="Batch size for processing (auto-detected if not specified)",
)
@click.option(
    "--num-workers",
    type=click.IntRange(min=1, max=32),
    help="Number of worker threads (auto-detected if not specified)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed system information and optimization hints",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress progress display and non-essential output",
)
@click.option(
    "--max-duration",
    type=click.IntRange(min=1),
    help="Limit transcription to N minutes (from start or --start-time)",
)
@click.option(
    "--start-time",
    type=click.FloatRange(min=0),
    help="Start transcription at N seconds",
)
@click.option(
    "--end-time", type=click.FloatRange(min=0), help="End transcription at N seconds"
)
@click.option(
    "--diarize/--no-diarize",
    default=True,
    show_default=True,
    help="Enable speaker identification (disable with --no-diarize)",
)
@click.option(
    "--mode",
    "transcription_mode",
    type=click.Choice(["transcription", "agent-review"], case_sensitive=False),
    default="transcription",
    show_default=True,
    help="Transcription mode: 'transcription' for text output, 'agent-review' for screenshots and metadata",
)
@click.option(
    "--screenshots-interval",
    "screenshots_interval",
    type=click.IntRange(min=5),
    default=30,
    show_default=True,
    help="Time interval (seconds) between time-based screenshots in agent-review mode",
)
@click.option(
    "--speech-cues",
    "speech_cues",
    type=str,
    default="this,here,that,look at,notice,pay attention,see how,issue,problem,bug,wrong,broken",
    show_default="default list",
    help="Comma-separated trigger words that prompt screenshot capture in agent-review mode",
)
@click.option(
    "--scene-threshold",
    "scene_threshold",
    type=click.FloatRange(min=0.0, max=1.0),
    default=0.3,
    show_default=True,
    help="Scene change detection sensitivity threshold (0.0-1.0) in agent-review mode",
)
@click.option(
    "--no-scene-detection",
    "enable_scene_detection",
    is_flag=True,
    default=False,
    help="Disable scene change detection in agent-review mode",
)
@click.pass_context
def transcribe(
    ctx,
    input_source,
    output,
    model,
    device,
    compute_type,
    batch_size,
    num_workers,
    verbose,
    quiet,
    max_duration,
    start_time,
    end_time,
    diarize,
    transcription_mode,
    screenshots_interval,
    speech_cues,
    scene_threshold,
    enable_scene_detection,
):
    """Transcribe a local audio file or YouTube URL.

    INPUT may be a filesystem path or a YouTube URL.

    \b
    Accepted input:
      - local audio file: mp3, wav, m4a, ogg, flac, aac, wma
      - local video file: mp4, mkv, avi, mov, webm (in agent-review mode)
      - YouTube URL (requires FFmpeg)

    \b
    Output behavior:
      - diarized transcripts default to Markdown (.md)
      - --no-diarize outputs plain text (.txt)
      - output extensions are auto-corrected when needed

    \b
    Modes:
      - 'transcription' (default): Standard text transcription
      - 'agent-review': Captures screenshots from video with transcript segments

    \b
    Agent-review mode (--mode agent-review):
      - Requires a video file as input (not YouTube URLs)
      - Extracts screenshots at intervals, scene changes, and speech cues
      - Generates: transcript.md, sidecar.json, images/ folder
      - Customizable via --screenshots-interval, --speech-cues, --scene-threshold

    \b
    Automation tips:
      - use --quiet for cleaner machine-readable logs
      - use --no-diarize when plain text is easier to consume
      - use --start-time / --end-time to transcribe a clip
      - use --mode agent-review for screen recording analysis

    \b
    Examples:
      cesar transcribe audio.mp3 -o transcript.md
      cesar transcribe audio.mp3 -o transcript.txt --no-diarize --quiet
      cesar transcribe interview.wav -o interview.md --model large
      cesar transcribe "https://youtube.com/watch?v=VIDEO_ID" -o transcript.txt
      cesar transcribe recording.mp4 -o review.md --mode agent-review
      cesar transcribe recording.mp4 -o review.md --mode agent-review --screenshots-interval 60
    """
    # Get config from context
    config = ctx.obj.get("config", CesarConfig())

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

    # Validate agent-review mode requirements
    if transcription_mode == "agent-review":
        # Import here to avoid circular imports and to check availability
        from cesar.video_processor import VideoProcessor

        video_processor = VideoProcessor()

        # Check if input is a URL (not supported for agent-review)
        if input_source.startswith("http://") or input_source.startswith("https://"):
            error_msg = "Error: agent-review mode requires a local video file (YouTube URLs not supported)"
            console.print(f"[red]{error_msg}[/red]")
            click.echo(error_msg, err=True)
            sys.exit(1)

        # Check if FFmpeg is available
        if not video_processor.ffmpeg_available:
            error_msg = "Error: FFmpeg is required for agent-review mode. Install FFmpeg and ensure it's in your PATH."
            console.print(f"[red]{error_msg}[/red]")
            click.echo(error_msg, err=True)
            sys.exit(1)

        # Parse speech cues into a list
        parsed_speech_cues = [cue.strip() for cue in speech_cues.split(",") if cue.strip()]

    # Track temp file for cleanup
    temp_audio_path = None

    try:
        # Set console quiet mode
        if quiet:
            console.quiet = True

        # Handle YouTube URLs vs file paths
        if input_source.startswith("http://") or input_source.startswith("https://"):
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
            device=device.lower() if device != "auto" else None,
            compute_type=compute_type.lower() if compute_type != "auto" else None,
            batch_size=batch_size,
            num_workers=num_workers,
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
            console.print(
                f"[yellow]Warning: Could not determine audio duration: {e}[/yellow]"
            )
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
            caps = model_info["capabilities"]
            console.print("\n[bold]Device Capabilities:[/bold]")
            console.print(f"  CUDA available: [cyan]{caps['has_cuda']}[/cyan]")
            if caps["cuda_version"]:
                console.print(f"  CUDA version: [cyan]{caps['cuda_version']}[/cyan]")
            if caps["gpu_memory_mb"]:
                console.print(f"  GPU memory: [cyan]{caps['gpu_memory_mb']} MB[/cyan]")
            console.print(f"  Apple MPS available: [cyan]{caps['has_mps']}[/cyan]")
            console.print(f"  CPU cores: [cyan]{caps['cpu_cores']}[/cyan]")

            if duration > 0:
                estimated_time = estimate_processing_time(
                    duration, model_info["model_size"]
                )
                console.print(
                    f"\n  Estimated processing time: [yellow]{format_time(estimated_time)}[/yellow]"
                )
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
            pipeline = WhisperXPipeline(model_name=model, hf_token=hf_token)

        # Set up progress tracking
        progress_tracker = ProgressTracker(show_progress=not quiet)

        # Start transcription
        if not quiet:
            console.print(f"\n[bold]Loading Whisper model '{model}'...[/bold]")

        transcription_start_time = time.time()

        with progress_tracker:
            # Check for agent-review mode (full pipeline with screenshots)
            if transcription_mode == "agent-review":
                from cesar.speech_cue_detector import SpeechCueDetector
                
                # Parse speech cues from CLI argument
                parsed_speech_cues = [cue.strip() for cue in speech_cues.split(",") if cue.strip()]
                
                # Create agent-review orchestrator
                agent_orchestrator = AgentReviewOrchestrator(
                    pipeline=pipeline,
                    transcriber=transcriber,
                )
                
                if not quiet:
                    console.print(f"\n[bold]Running agent-review mode...[/bold]")
                
                # Run agent-review pipeline
                result = agent_orchestrator.orchestrate(
                    video_path=input_file,
                    output_path=output,
                    screenshots_interval=screenshots_interval,
                    speech_cues=parsed_speech_cues if parsed_speech_cues else None,
                    scene_threshold=scene_threshold,
                    enable_scene_detection=not enable_scene_detection,
                    progress_callback=lambda step, pct: progress_tracker.update_step(
                        step, pct
                    )
                    if not quiet
                    else None,
                )
                
                # Show agent-review results
                if not quiet:
                    console.print(f"\n[bold green]Agent-review completed![/bold green]")
                    console.print(f"  Screenshots: [cyan]{result.screenshots_count}[/cyan]")
                    console.print(f"  Segments: [cyan]{result.segments_count}[/cyan]")
                    console.print(f"  Speakers: [cyan]{result.speakers_detected}[/cyan]")
                    console.print(f"  Duration: [blue]{format_time(result.audio_duration)}[/blue]")
                    console.print(f"\n  Output files:")
                    console.print(f"    Markdown: [green]{result.output_path}[/green]")
                    console.print(f"    Sidecar: [green]{result.sidecar_path}[/green]")
                    console.print(f"    Images: [green]{result.images_dir}/[/green]")
                    console.print(f"\n  Processing time breakdown:")
                    console.print(f"    Transcription: [blue]{format_time(result.transcription_time)}[/blue]")
                    console.print(f"    Screenshots: [blue]{format_time(result.screenshot_time)}[/blue]")
                    console.print(f"    Formatting: [blue]{format_time(result.formatting_time)}[/blue]")
                else:
                    console.print(f"Agent-review completed: {result.output_path}")
                
                return 0

            elif diarize and pipeline is not None:
                # Use orchestrator for diarized transcription
                orchestrator = TranscriptionOrchestrator(
                    pipeline=pipeline,
                    transcriber=transcriber,  # Kept for fallback when diarization fails
                )

                # Pass min/max_speakers from config to orchestrate()
                result = orchestrator.orchestrate(
                    audio_path=input_file,
                    output_path=output,
                    enable_diarization=True,
                    min_speakers=config.min_speakers,
                    max_speakers=config.max_speakers,
                    progress_callback=lambda step, pct: progress_tracker.update_step(
                        step, pct
                    )
                    if not quiet
                    else None,
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
                    end_time_seconds=end_time,
                )

                # Show results (existing logic)
                if not quiet:
                    console.print(
                        f"\n[bold green]Transcription completed![/bold green]"
                    )
                    console.print(
                        f"  Language: [cyan]{result['language']}[/cyan] (probability: {result['language_probability']:.2f})"
                    )
                    console.print(
                        f"  Audio duration: [blue]{format_time(result['audio_duration'])}[/blue]"
                    )
                    console.print(
                        f"  Processing time: [blue]{format_time(result['processing_time'])}[/blue]"
                    )
                    console.print(
                        f"  Speed ratio: [yellow]{result['speed_ratio']:.1f}x[/yellow] faster than real-time"
                    )
                    console.print(
                        f"  Total segments: [cyan]{result['segment_count']}[/cyan]"
                    )
                    console.print(
                        f"  Output saved to: [green]{result['output_path']}[/green]"
                    )
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
            cause = str(e.__cause__).split("\n")[0]  # First line only
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
        console.print(
            "[yellow]Hint: Install faster-whisper with: pip install faster-whisper[/yellow]"
        )
        click.echo(error_msg, err=True)
        click.echo(
            "Hint: Install faster-whisper with: pip install faster-whisper", err=True
        )
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


@cli.command(
    name="serve",
    short_help="Run the HTTP API server for async transcription jobs.",
    context_settings=CLI_CONTEXT_SETTINGS,
)
@click.option(
    "--port", "-p", type=int, default=5000, show_default=True, help="Port to bind to"
)
@click.option(
    "--host", "-H", default="127.0.0.1", show_default=True, help="Host to bind to"
)
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option(
    "--workers",
    type=int,
    default=1,
    show_default=True,
    help="Number of uvicorn workers",
)
def serve(port, host, reload, workers):
    """Run the Cesar HTTP API server for programmatic transcription.

    Use this for long-running integrations that submit jobs over HTTP instead of invoking the
    one-shot ``transcribe`` command.

    The API exposes file upload and URL transcription endpoints plus interactive docs at
    ``/docs`` once the server is running.

    \b
    Examples:
      cesar serve
      cesar serve --port 8080 --reload
      cesar serve --host 0.0.0.0 --workers 4
    """
    try:
        import uvicorn
    except ImportError as exc:
        raise click.ClickException(
            "The API server requires uvicorn. Install Cesar with API dependencies and retry."
        ) from exc

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
