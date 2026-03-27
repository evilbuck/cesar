"""
Unit tests for configuration management.

Tests the CesarConfig model, TOML loading, validation, and path helpers.
"""
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from cesar.config import (
    CesarConfig,
    ConfigError,
    load_config,
    get_cli_config_path,
    get_api_config_path,
    create_default_config,
)


class TestCesarConfigModel(unittest.TestCase):
    """Tests for CesarConfig Pydantic model."""

    def test_default_values(self):
        """Default config has diarize=False and None for speaker counts."""
        config = CesarConfig()
        self.assertEqual(config.diarize, False)
        self.assertIsNone(config.min_speakers)
        self.assertIsNone(config.max_speakers)

    def test_valid_diarize_true(self):
        """Config accepts diarize=True."""
        config = CesarConfig(diarize=True)
        self.assertEqual(config.diarize, True)

    def test_valid_min_speakers(self):
        """Config accepts valid min_speakers >= 1."""
        config = CesarConfig(min_speakers=2)
        self.assertEqual(config.min_speakers, 2)

    def test_valid_max_speakers(self):
        """Config accepts valid max_speakers >= 1."""
        config = CesarConfig(max_speakers=4)
        self.assertEqual(config.max_speakers, 4)

    def test_invalid_min_speakers_zero(self):
        """Config rejects min_speakers=0."""
        with self.assertRaises(ValidationError) as ctx:
            CesarConfig(min_speakers=0)

        error = str(ctx.exception)
        self.assertIn("min_speakers", error)
        self.assertIn("expected integer >= 1", error)

    def test_invalid_min_speakers_negative(self):
        """Config rejects negative min_speakers."""
        with self.assertRaises(ValidationError) as ctx:
            CesarConfig(min_speakers=-1)

        error = str(ctx.exception)
        self.assertIn("min_speakers", error)
        self.assertIn("expected integer >= 1", error)

    def test_invalid_max_speakers_zero(self):
        """Config rejects max_speakers=0."""
        with self.assertRaises(ValidationError) as ctx:
            CesarConfig(max_speakers=0)

        error = str(ctx.exception)
        self.assertIn("max_speakers", error)
        self.assertIn("expected integer >= 1", error)

    def test_invalid_min_speakers_string(self):
        """Config rejects non-integer min_speakers with clear message."""
        with self.assertRaises(ValidationError) as ctx:
            CesarConfig(min_speakers="auto")

        error = str(ctx.exception)
        self.assertIn("min_speakers", error)

    def test_min_greater_than_max(self):
        """Config rejects min_speakers > max_speakers."""
        with self.assertRaises(ValidationError) as ctx:
            CesarConfig(min_speakers=5, max_speakers=2)

        error = str(ctx.exception)
        self.assertIn("min_speakers", error)
        self.assertIn("max_speakers", error)
        self.assertIn("cannot be greater than", error)

    def test_extra_field_rejected(self):
        """Config rejects unknown fields (typos)."""
        with self.assertRaises(ValidationError) as ctx:
            CesarConfig(diarzie=True)  # typo: diarzie instead of diarize

        error = str(ctx.exception)
        self.assertIn("Extra inputs are not permitted", error)


class TestLoadConfig(unittest.TestCase):
    """Tests for load_config function."""

    def test_load_missing_file(self):
        """load_config returns defaults when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.toml"
            config = load_config(config_path)

            self.assertEqual(config.diarize, False)
            self.assertIsNone(config.min_speakers)
            self.assertIsNone(config.max_speakers)

    def test_load_valid_config(self):
        """load_config parses valid TOML correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
diarize = true
min_speakers = 2
max_speakers = 5
""")

            config = load_config(config_path)

            self.assertEqual(config.diarize, True)
            self.assertEqual(config.min_speakers, 2)
            self.assertEqual(config.max_speakers, 5)

    def test_load_invalid_toml_syntax(self):
        """load_config raises ConfigError on invalid TOML syntax."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
diarize = [invalid syntax
""")

            with self.assertRaises(ConfigError) as ctx:
                load_config(config_path)

            error = str(ctx.exception)
            self.assertIn("Invalid TOML syntax", error)
            self.assertIn("line", error)

    def test_load_invalid_value(self):
        """load_config raises ConfigError on invalid field values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
min_speakers = 0
""")

            with self.assertRaises(ConfigError) as ctx:
                load_config(config_path)

            error = str(ctx.exception)
            self.assertIn("Configuration validation failed", error)
            self.assertIn("min_speakers", error)

    def test_load_unknown_key(self):
        """load_config raises ConfigError on unknown keys (extra='forbid')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
diarzie = true
""")

            with self.assertRaises(ConfigError) as ctx:
                load_config(config_path)

            error = str(ctx.exception)
            self.assertIn("Configuration validation failed", error)

    def test_load_cross_field_validation(self):
        """load_config catches min_speakers > max_speakers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
min_speakers = 5
max_speakers = 2
""")

            with self.assertRaises(ConfigError) as ctx:
                load_config(config_path)

            error = str(ctx.exception)
            self.assertIn("Configuration validation failed", error)


class TestPathHelpers(unittest.TestCase):
    """Tests for path helper functions."""

    def test_cli_config_path(self):
        """get_cli_config_path returns ~/.config/cesar/config.toml."""
        path = get_cli_config_path()

        # Should be absolute path
        self.assertTrue(path.is_absolute())

        # Should end with .config/cesar/config.toml
        self.assertEqual(path.name, "config.toml")
        self.assertEqual(path.parent.name, "cesar")
        self.assertEqual(path.parent.parent.name, ".config")

        # Should be in home directory
        self.assertTrue(str(path).startswith(str(Path.home())))

    def test_api_config_path(self):
        """get_api_config_path returns cwd/config.toml."""
        path = get_api_config_path()

        # Should be in current working directory
        expected = Path.cwd() / "config.toml"
        self.assertEqual(path, expected)


class TestCreateDefaultConfig(unittest.TestCase):
    """Tests for create_default_config function."""

    def test_creates_file(self):
        """create_default_config creates the config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            self.assertTrue(config_path.exists())
            self.assertTrue(config_path.is_file())

    def test_creates_directories(self):
        """create_default_config creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested" / "path" / "config.toml"
            create_default_config(config_path)

            self.assertTrue(config_path.exists())
            self.assertTrue(config_path.parent.exists())

    def test_file_contents(self):
        """create_default_config writes expected settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            contents = config_path.read_text()

            # Should contain settings
            self.assertIn("diarize", contents)
            self.assertIn("min_speakers", contents)
            self.assertIn("max_speakers", contents)

            # Should contain documentation
            self.assertIn("speaker identification", contents)
            self.assertIn("Example:", contents)

            # Should be valid TOML that loads successfully
            config = load_config(config_path)
            self.assertIsNotNone(config)

    def test_generated_config_is_valid(self):
        """Generated default config can be loaded successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            # Should load without errors
            config = load_config(config_path)

            # Should have default values (since template has diarize = false)
            self.assertEqual(config.diarize, False)


if __name__ == '__main__':
    unittest.main()
