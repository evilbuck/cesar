"""
Configuration management for Cesar transcription tool.

Provides validated configuration loading from TOML files with clear error
messages. Supports hierarchical configuration: CLI and API can use different
config files with CLI arguments always overriding config values.
"""
from pathlib import Path
from typing import Optional
import tomllib

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator


class ConfigError(Exception):
    """Exception raised for configuration errors."""
    pass


class CesarConfig(BaseModel):
    """Configuration model for Cesar transcription settings.

    Attributes:
        diarize: Enable speaker identification (speaker labels in output)
        min_speakers: Minimum number of speakers to detect (must be >= 1 if set)
        max_speakers: Maximum number of speakers to detect (must be >= 1 if set)
    """

    model_config = ConfigDict(
        extra='forbid',  # Reject unknown keys to catch typos
        str_strip_whitespace=True,
    )

    diarize: bool = False
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None

    @field_validator('min_speakers', 'max_speakers')
    @classmethod
    def validate_speaker_count(cls, v: Optional[int], info) -> Optional[int]:
        """Validate speaker counts are >= 1 if set."""
        if v is not None and v < 1:
            raise ValueError(
                f"Invalid value for '{info.field_name}': expected integer >= 1, got {v}. "
                f"Example: {info.field_name} = 2"
            )
        return v

    @model_validator(mode='after')
    def validate_speaker_range(self) -> 'CesarConfig':
        """Ensure min_speakers <= max_speakers when both are set."""
        if (self.min_speakers is not None and
            self.max_speakers is not None and
            self.min_speakers > self.max_speakers):
            raise ValueError(
                f"Invalid speaker range: min_speakers ({self.min_speakers}) "
                f"cannot be greater than max_speakers ({self.max_speakers}). "
                f"Example: min_speakers = 2, max_speakers = 4"
            )
        return self


def get_cli_config_path() -> Path:
    """Get the CLI configuration file path.

    Returns:
        Path to ~/.config/cesar/config.toml (expanded to absolute path)
    """
    return Path.home() / ".config" / "cesar" / "config.toml"


def get_api_config_path() -> Path:
    """Get the API configuration file path.

    Returns:
        Path to config.toml in current working directory
    """
    return Path.cwd() / "config.toml"


def load_config(config_path: Path) -> CesarConfig:
    """Load and validate configuration from TOML file.

    Args:
        config_path: Path to the TOML configuration file

    Returns:
        Validated CesarConfig instance

    Raises:
        ConfigError: If config file has invalid TOML syntax or validation errors

    Note:
        If the config file doesn't exist, returns default configuration.
    """
    # Return defaults if file doesn't exist
    if not config_path.exists():
        return CesarConfig()

    # Load and parse TOML
    try:
        with open(config_path, 'rb') as f:
            config_data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(
            f"Invalid TOML syntax in {config_path} at line {e.lineno}, column {e.colno}: {e.msg}"
        ) from e

    # Validate with Pydantic
    try:
        return CesarConfig(**config_data)
    except ValidationError as e:
        # Format validation errors user-friendly
        errors = []
        for error in e.errors():
            field = error['loc'][0] if error['loc'] else 'unknown'
            msg = error['msg']
            errors.append(f"  - {field}: {msg}")

        raise ConfigError(
            f"Configuration validation failed in {config_path}:\n" +
            "\n".join(errors)
        ) from e


# Default configuration template with inline documentation
DEFAULT_CONFIG_TEMPLATE = """# Cesar Audio Transcription Configuration
#
# This file configures default behavior for the Cesar transcription tool.
#
# Location:
#   - CLI: ~/.config/cesar/config.toml
#   - API: config.toml in the API project directory
#
# CLI arguments always override these settings.

# Enable speaker identification (diarization)
# When true, output includes speaker labels like "[SPEAKER_00]"
# Default: false
diarize = false

# Minimum number of speakers to detect during diarization
# Only used when diarize = true
# Must be >= 1 if specified
# Default: auto-detect (leave commented)
# Example: min_speakers = 2

# Maximum number of speakers to detect during diarization
# Only used when diarize = true
# Must be >= 1 if specified, and >= min_speakers
# Default: auto-detect (leave commented)
# Example: max_speakers = 4
"""


def create_default_config(config_path: Path) -> None:
    """Create a default configuration file with inline documentation.

    Args:
        config_path: Path where the config file should be created

    Note:
        Creates parent directories if they don't exist.
    """
    # Create parent directories
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write template
    config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
