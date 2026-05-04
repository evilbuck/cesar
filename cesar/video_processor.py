"""
FFmpeg-based video processor for frame extraction and metadata.
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Metadata extracted from a video file."""
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    file_size: int


class VideoProcessor:
    """Handles video file operations using FFmpeg.

    This class provides utilities for:
    - Validating video files
    - Extracting metadata
    - Extracting frames at specific timestamps
    - Checking FFmpeg availability
    """

    # Supported video formats
    SUPPORTED_FORMATS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.wmv', '.flv'}

    # Supported image formats for frame output
    SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.bmp'}

    def __init__(self):
        """Initialize the video processor."""
        self._ffmpeg_available: Optional[bool] = None
        self._ffmpeg_version: Optional[str] = None

    @property
    def ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available on the system.

        Returns:
            True if FFmpeg is installed and executable.
        """
        if self._ffmpeg_available is None:
            self._ffmpeg_available = self._check_ffmpeg()
        return self._ffmpeg_available

    @property
    def ffmpeg_version(self) -> Optional[str]:
        """Get FFmpeg version string.

        Returns:
            Version string if FFmpeg is available, None otherwise.
        """
        if self._ffmpeg_version is None and self.ffmpeg_available:
            try:
                result = subprocess.run(
                    ['ffmpeg', '-version'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                # Extract version from first line: "ffmpeg version X.X.X ..."
                first_line = result.stdout.split('\n')[0]
                self._ffmpeg_version = first_line.replace('ffmpeg version ', '')
            except (subprocess.CalledProcessError, FileNotFoundError):
                self._ffmpeg_version = None
        return self._ffmpeg_version

    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is installed and accessible.

        Returns:
            True if FFmpeg is available.
        """
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def validate_video_file(self, file_path: Path) -> Path:
        """Validate that a file is a supported video format.

        Args:
            file_path: Path to the video file.

        Returns:
            The validated Path object.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is not a supported video format.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported video format: {file_path.suffix}. "
                f"Supported formats: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )

        # Also verify it's readable by FFmpeg (probe the file)
        if self.ffmpeg_available:
            try:
                subprocess.run(
                    [
                        'ffprobe', '-v', 'error',
                        '-select_streams', 'v:0',
                        '-show_entries', 'stream=codec_type',
                        '-of', 'csv=p=0',
                        str(file_path)
                    ],
                    capture_output=True,
                    check=True
                )
            except subprocess.CalledProcessError as e:
                logger.warning(f"FFprobe warning for {file_path}: {e.stderr}")
                # Don't fail - FFmpeg might still work

        return file_path

    def get_video_metadata(self, file_path: Path) -> VideoMetadata:
        """Extract metadata from a video file.

        Args:
            file_path: Path to the video file.

        Returns:
            VideoMetadata object with video properties.

        Raises:
            RuntimeError: If FFmpeg/FFprobe fails.
        """
        if not self.ffmpeg_available:
            raise RuntimeError("FFmpeg is not available. Cannot extract video metadata.")

        file_path = self.validate_video_file(file_path)

        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(file_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            data = json.loads(result.stdout)

            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break

            if not video_stream:
                raise RuntimeError(f"No video stream found in {file_path}")

            format_info = data.get('format', {})

            return VideoMetadata(
                duration=float(format_info.get('duration', 0)),
                width=int(video_stream.get('width', 0)),
                height=int(video_stream.get('height', 0)),
                fps=self._parse_fps(video_stream.get('r_frame_rate', '0/1')),
                codec=video_stream.get('codec_name', 'unknown'),
                file_size=int(format_info.get('size', 0))
            )

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to probe video: {e.stderr}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse FFprobe output: {e}")

    def _parse_fps(self, fps_string: str) -> float:
        """Parse FPS from FFprobe's fraction format (e.g., '30000/1001').

        Args:
            fps_string: FPS as fraction string.

        Returns:
            FPS as float.
        """
        try:
            if '/' in fps_string:
                num, denom = fps_string.split('/')
                return float(num) / float(denom)
            return float(fps_string)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def extract_frame(
        self,
        file_path: Path,
        timestamp: float,
        output_path: Path,
        image_format: str = 'png'
    ) -> Path:
        """Extract a single frame from a video at a specific timestamp.

        Args:
            file_path: Path to the video file.
            timestamp: Timestamp in seconds to extract frame from.
            output_path: Path where the frame image will be saved.
            image_format: Image format ('png', 'jpg', etc.). Default: 'png'.

        Returns:
            Path to the extracted frame image.

        Raises:
            RuntimeError: If FFmpeg fails.
            ValueError: If image_format is not supported.
        """
        if not self.ffmpeg_available:
            raise RuntimeError("FFmpeg is not available. Cannot extract frames.")

        if f'.{image_format}' not in self.SUPPORTED_IMAGE_FORMATS:
            raise ValueError(
                f"Unsupported image format: {image_format}. "
                f"Supported: {', '.join(self.SUPPORTED_IMAGE_FORMATS)}"
            )

        file_path = self.validate_video_file(file_path)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # FFmpeg extracts frames at the specified timestamp
        # -ss before -i is faster (input seeking)
        # -frames:v 1 extracts exactly one frame
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output without asking
            '-ss', str(timestamp),
            '-i', str(file_path),
            '-frames:v', '1',
            '-q:v', '2',  # Quality (2 is good for PNG, lower is better quality)
            '-f', 'image2',
            str(output_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(f"Extracted frame at {timestamp}s to {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to extract frame at {timestamp}s: {e.stderr}"
            )

    def extract_frames_batch(
        self,
        file_path: Path,
        timestamps: list[float],
        output_dir: Path,
        name_prefix: str,
        image_format: str = 'png'
    ) -> list[Path]:
        """Extract multiple frames from a video at specified timestamps.

        Args:
            file_path: Path to the video file.
            timestamps: List of timestamps in seconds to extract frames from.
            output_dir: Directory where frame images will be saved.
            name_prefix: Prefix for the output filenames.
            image_format: Image format ('png', 'jpg', etc.). Default: 'png'.

        Returns:
            List of paths to the extracted frame images.

        Raises:
            RuntimeError: If FFmpeg fails for any frame.
        """
        if not self.ffmpeg_available:
            raise RuntimeError("FFmpeg is not available. Cannot extract frames.")

        file_path = self.validate_video_file(file_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted_paths = []
        errors = []

        for timestamp in sorted(timestamps):
            # Format: {prefix}_{HH-MM-SS}.{format}
            hours = int(timestamp // 3600)
            minutes = int((timestamp % 3600) // 60)
            seconds = int(timestamp % 60)
            filename = f"{name_prefix}_{hours:02d}-{minutes:02d}-{seconds:02d}.{image_format}"
            output_path = output_dir / filename

            try:
                path = self.extract_frame(
                    file_path, timestamp, output_path, image_format
                )
                extracted_paths.append(path)
            except RuntimeError as e:
                errors.append(f"Timestamp {timestamp}s: {e}")
                logger.warning(f"Failed to extract frame at {timestamp}s: {e}")

        if errors and not extracted_paths:
            raise RuntimeError(
                f"Failed to extract any frames. Errors:\n" + "\n".join(errors)
            )

        return extracted_paths
