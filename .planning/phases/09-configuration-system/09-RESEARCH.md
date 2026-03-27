# Phase 9: Configuration System - Research

**Researched:** 2026-02-01
**Domain:** Python TOML configuration with Pydantic validation
**Confidence:** HIGH

## Summary

This phase implements a configuration system for cesar that loads user preferences from TOML files, validates them with Pydantic, and merges with CLI arguments (CLI always wins). The standard approach uses Python 3.11+'s built-in `tomllib` for reading TOML files and Pydantic v2 models for validation.

The research confirms that pydantic-settings with its `TomlConfigSettingsSource` is overkill for this use case. The simpler approach is to use `tomllib` (stdlib) for parsing and a plain Pydantic `BaseModel` for validation. This aligns with the project's existing Pydantic v2 patterns (seen in `cesar/api/models.py`).

For generating config files with inline comments (a decision from CONTEXT.md), the stdlib `tomllib` cannot write TOML. However, since the config structure is simple and static (only 3 settings), a template string approach is preferred over adding a dependency like `tomlkit`.

**Primary recommendation:** Use stdlib `tomllib` for parsing, Pydantic `BaseModel` for validation, and a hardcoded template string for generating the default config file with comments.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tomllib | stdlib (3.11+) | TOML parsing | Python standard library, no external dependency, TOML 1.0.0 compliant |
| pydantic | >=2.0.0 | Config validation | Already in project, type-safe validation with clear error messages |
| pathlib | stdlib | Path handling | Cross-platform path manipulation, already used throughout codebase |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| platformdirs | 4.5.x | Cross-platform config paths | If needing Windows/macOS support beyond `~/.config` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tomllib | pydantic-settings[toml] | Heavier dependency, more complex; use only if need env var merging |
| template string | tomlkit | Preserves comments when round-tripping; overkill for write-once config generation |
| `~/.config` hardcoded | platformdirs | Cross-platform; but project targets Linux/macOS where `~/.config` is standard |

**Installation:**
```bash
# No new dependencies needed - tomllib is stdlib, pydantic already installed
# Already in pyproject.toml: pydantic>=2.0.0
```

## Architecture Patterns

### Recommended Project Structure
```
cesar/
├── config.py           # Config loading, validation, defaults
├── cli.py              # CLI commands (import from config.py)
├── api/
│   └── server.py       # API server (import from config.py)
└── ...
```

### Pattern 1: Simple Config Model with Pydantic
**What:** Define a Pydantic model for config structure, parse TOML to dict, validate with model
**When to use:** Simple config needs without environment variable merging
**Example:**
```python
# Source: Pydantic v2 docs + stdlib tomllib
import tomllib
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, ValidationError

class CesarConfig(BaseModel):
    """Configuration for cesar transcription settings."""

    # Diarization defaults (v2.2 scope)
    diarize: bool = False
    min_speakers: int | None = None
    max_speakers: int | None = None

    @field_validator('min_speakers', 'max_speakers')
    @classmethod
    def validate_speaker_count(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError('must be >= 1')
        return v

    @model_validator(mode='after')
    def validate_speaker_range(self) -> 'CesarConfig':
        if (self.min_speakers is not None and
            self.max_speakers is not None and
            self.min_speakers > self.max_speakers):
            raise ValueError('min_speakers must be <= max_speakers')
        return self

def load_config(config_path: Path) -> CesarConfig:
    """Load and validate config from TOML file."""
    if not config_path.exists():
        return CesarConfig()  # Return defaults

    with open(config_path, 'rb') as f:
        data = tomllib.load(f)

    return CesarConfig.model_validate(data)
```

### Pattern 2: CLI Override Merging
**What:** Merge config file defaults with CLI arguments, CLI wins
**When to use:** When CLI arguments should override config file values
**Example:**
```python
# Source: Click docs + project patterns
def get_effective_config(
    config: CesarConfig,
    cli_diarize: bool | None,
    cli_min_speakers: int | None,
    cli_max_speakers: int | None,
) -> dict:
    """Merge config with CLI overrides. CLI always wins."""
    return {
        'diarize': cli_diarize if cli_diarize is not None else config.diarize,
        'min_speakers': cli_min_speakers if cli_min_speakers is not None else config.min_speakers,
        'max_speakers': cli_max_speakers if cli_max_speakers is not None else config.max_speakers,
    }
```

### Pattern 3: Config File Generation with Template
**What:** Generate config file with inline comments using f-string template
**When to use:** Creating initial config file with documentation
**Example:**
```python
# Source: Project decision - template string for simplicity
DEFAULT_CONFIG_TEMPLATE = """\
# Cesar Configuration File
# Location: ~/.config/cesar/config.toml
#
# These settings provide defaults for cesar commands.
# CLI arguments always override these values.

# Speaker diarization (identify different speakers)
# Set to true to enable speaker identification by default
diarize = false

# Minimum number of speakers to detect
# Uncomment and set if you know the minimum speaker count
# min_speakers = 2

# Maximum number of speakers to detect
# Uncomment and set if you know the maximum speaker count
# max_speakers = 4
"""

def create_default_config(config_path: Path) -> None:
    """Create config file with documented defaults."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
```

### Pattern 4: Fail-Fast Validation with User-Friendly Errors
**What:** Catch Pydantic ValidationError, format for CLI users
**When to use:** Config loading at startup
**Example:**
```python
# Source: Pydantic docs + CONTEXT.md decision on error messages
def load_config_with_errors(config_path: Path) -> CesarConfig:
    """Load config, exit with clear error on validation failure."""
    if not config_path.exists():
        return CesarConfig()

    try:
        with open(config_path, 'rb') as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        # TOML syntax error
        raise ConfigError(
            f"Invalid TOML syntax in {config_path}:\n"
            f"  Line {e.lineno}, column {e.colno}: {e.msg}"
        )

    try:
        return CesarConfig.model_validate(data)
    except ValidationError as e:
        # Validation error - format user-friendly
        errors = []
        for err in e.errors():
            field = '.'.join(str(x) for x in err['loc'])
            msg = err['msg']
            errors.append(f"  {field}: {msg}")
        raise ConfigError(
            f"Invalid configuration in {config_path}:\n" +
            '\n'.join(errors)
        )
```

### Anti-Patterns to Avoid
- **Global mutable config singleton:** Don't use module-level mutable state; pass config explicitly
- **Silent config file errors:** Don't ignore malformed config; fail fast with clear message
- **CLI default values that shadow config:** Don't set Click defaults that prevent detecting "user didn't specify"
- **Validating after use:** Don't validate lazily; validate at load time

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TOML parsing | Custom parser | `tomllib` (stdlib) | TOML 1.0.0 spec is complex, edge cases abound |
| Type validation | Manual `isinstance()` checks | Pydantic model | Type coercion, nested validation, clear errors |
| Path expansion | Manual `os.path.expanduser()` | `pathlib.Path.expanduser()` | Already in use, handles edge cases |
| Error message formatting | Manual string building | Pydantic `ValidationError.errors()` | Structured, consistent, includes context |

**Key insight:** The config system is deceptively simple. Edge cases include: malformed TOML, wrong types, missing keys, extra keys, cross-field validation (min <= max). Pydantic handles all of these.

## Common Pitfalls

### Pitfall 1: Click Default Values Hide "Not Specified"
**What goes wrong:** Setting `default=False` on a Click option means you can't tell if user passed `--no-diarize` or didn't specify anything
**Why it happens:** Click collapses "not specified" and "specified as default" into the same value
**How to avoid:** Use `default=None` and `is_flag=True` pattern, or use `flag_value` option
**Warning signs:** Config file values never take effect because CLI "defaults" always win

```python
# WRONG: Can't distinguish "user said no" from "user said nothing"
@click.option('--diarize/--no-diarize', default=False)

# RIGHT: None means "not specified", let config take over
@click.option('--diarize', is_flag=True, default=None, flag_value=True)
@click.option('--no-diarize', is_flag=True, default=None, flag_value=False)
```

### Pitfall 2: TOML File Must Be Opened in Binary Mode
**What goes wrong:** `tomllib.load()` raises error when file opened with `'r'` instead of `'rb'`
**Why it happens:** TOML spec requires UTF-8, tomllib enforces binary mode to prevent encoding issues
**How to avoid:** Always use `open(path, 'rb')` with tomllib
**Warning signs:** `TypeError: File must be opened in binary mode`

### Pitfall 3: Config Path Expansion
**What goes wrong:** `~/.config/cesar/config.toml` doesn't expand when passed as string
**Why it happens:** Python doesn't auto-expand `~` in paths
**How to avoid:** Use `Path(path).expanduser()` before any file operations
**Warning signs:** FileNotFoundError when config file exists at `~/.config/...`

### Pitfall 4: Extra Fields in Config File
**What goes wrong:** User adds typo'd key like `diarzie = true`, silently ignored
**Why it happens:** Pydantic default behavior allows extra fields
**How to avoid:** Use `model_config = ConfigDict(extra='forbid')` or warn on unknown keys
**Warning signs:** User thinks they configured something but it has no effect

### Pitfall 5: API vs CLI Config Locations
**What goes wrong:** API server looks for config in wrong location
**Why it happens:** Decision says CLI uses `~/.config/cesar/config.toml`, API uses local `config.toml`
**How to avoid:** Separate config loading functions with explicit paths
**Warning signs:** API ignores user's home config, CLI ignores local config

## Code Examples

Verified patterns from official sources:

### Loading TOML with tomllib (Python 3.11+)
```python
# Source: https://docs.python.org/3/library/tomllib.html
import tomllib
from pathlib import Path

config_path = Path.home() / '.config' / 'cesar' / 'config.toml'

with open(config_path, 'rb') as f:
    data = tomllib.load(f)  # Returns dict

# Access values
diarize = data.get('diarize', False)
```

### Pydantic Model Validation
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from pydantic import BaseModel, ConfigDict, field_validator

class CesarConfig(BaseModel):
    model_config = ConfigDict(
        extra='forbid',  # Reject unknown keys
        str_strip_whitespace=True,
    )

    diarize: bool = False
    min_speakers: int | None = None
    max_speakers: int | None = None

# Validate dict from TOML
config = CesarConfig.model_validate(data)
```

### User-Friendly Validation Errors
```python
# Source: https://docs.pydantic.dev/latest/errors/validation_errors/
from pydantic import ValidationError

try:
    config = CesarConfig.model_validate({'min_speakers': 'auto'})
except ValidationError as e:
    for error in e.errors():
        field = error['loc'][0]  # e.g., 'min_speakers'
        msg = error['msg']       # e.g., 'Input should be a valid integer'
        input_val = error['input']  # e.g., 'auto'
        print(f"Invalid value for '{field}': {msg}. Got: {input_val}")
        # Output: Invalid value for 'min_speakers': Input should be a valid integer. Got: auto
```

### Cross-Field Validation
```python
# Source: https://docs.pydantic.dev/latest/concepts/validators/
from pydantic import model_validator

class CesarConfig(BaseModel):
    min_speakers: int | None = None
    max_speakers: int | None = None

    @model_validator(mode='after')
    def validate_speaker_range(self) -> 'CesarConfig':
        if (self.min_speakers is not None and
            self.max_speakers is not None and
            self.min_speakers > self.max_speakers):
            raise ValueError(
                f'min_speakers ({self.min_speakers}) must be <= '
                f'max_speakers ({self.max_speakers})'
            )
        return self
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tomli` external package | `tomllib` stdlib | Python 3.11 (Oct 2022) | No external dependency needed |
| Pydantic v1 `Config` class | Pydantic v2 `ConfigDict` | Pydantic 2.0 (Jul 2023) | New syntax for model config |
| `appdirs` | `platformdirs` | 2021 | Actively maintained replacement |
| Manual type checking | Pydantic models | Ongoing | Type-safe validation built-in |

**Deprecated/outdated:**
- `tomli`: Use `tomllib` (stdlib) for Python 3.11+
- `configparser`: INI format, not as readable as TOML for nested structures
- Pydantic v1 syntax: Use v2 `model_config = ConfigDict(...)` pattern

## Open Questions

Things that couldn't be fully resolved:

1. **Click tri-state flag pattern**
   - What we know: Click's `is_flag=True` with `default=None` should work for detecting "not specified"
   - What's unclear: Exact syntax for `--diarize/--no-diarize` that allows None default
   - Recommendation: Test in implementation; may need separate `--diarize` and `--no-diarize` options

2. **First-run config prompt UX**
   - What we know: CONTEXT.md says "prompt to create config on first run"
   - What's unclear: Should this be interactive (y/n prompt) or just informational message?
   - Recommendation: Informational message + command suggestion (`cesar config init`)

## Sources

### Primary (HIGH confidence)
- [Python tomllib documentation](https://docs.python.org/3/library/tomllib.html) - Complete API, examples, error handling
- [Pydantic v2 documentation](https://docs.pydantic.dev/latest/concepts/models/) - Model validation, ConfigDict, validators
- [Pydantic validation errors](https://docs.pydantic.dev/latest/errors/validation_errors/) - Error message formatting

### Secondary (MEDIUM confidence)
- [pydantic-settings TOML support](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Alternative approach with TomlConfigSettingsSource
- [platformdirs API](https://platformdirs.readthedocs.io/en/latest/api.html) - Cross-platform config directories

### Tertiary (LOW confidence)
- [tomlkit documentation](https://tomlkit.readthedocs.io/) - Style-preserving TOML (not needed for this phase)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib tomllib + existing Pydantic patterns
- Architecture: HIGH - patterns align with existing codebase structure
- Pitfalls: HIGH - documented in official sources, common Click issues well-known

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (stable libraries, unlikely to change)
