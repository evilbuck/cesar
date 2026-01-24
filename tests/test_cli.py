#!/usr/bin/env python3
"""
Tests for CLI argument parsing and commands
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from click.testing import CliRunner

from cesar.cli import cli, transcribe


class TestCLI(unittest.TestCase):
    """Test CLI commands and argument parsing"""

    def setUp(self):
        """Set up test environment"""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        # Create a test audio file
        self.test_audio = Path(self.temp_dir) / "test.mp3"
        self.test_audio.touch()
        self.output_file = Path(self.temp_dir) / "output.txt"

    def tearDown(self):
        """Clean up test files"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_cli_help(self):
        """Test CLI help command"""
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('cesar', result.output.lower())

    def test_cli_version(self):
        """Test CLI version command"""
        result = self.runner.invoke(cli, ['--version'])
        self.assertEqual(result.exit_code, 0)
        # Should show version number
        self.assertIn('cesar', result.output.lower())

    def test_transcribe_help(self):
        """Test transcribe subcommand help"""
        result = self.runner.invoke(cli, ['transcribe', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('INPUT_FILE', result.output)
        self.assertIn('--output', result.output)
        self.assertIn('--model', result.output)

    def test_transcribe_missing_input(self):
        """Test transcribe with missing input file"""
        result = self.runner.invoke(cli, ['transcribe', '-o', 'output.txt'])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('missing argument', result.output.lower())

    def test_transcribe_missing_output(self):
        """Test transcribe with missing output option"""
        result = self.runner.invoke(cli, ['transcribe', str(self.test_audio)])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('--output', result.output.lower())

    def test_transcribe_nonexistent_input(self):
        """Test transcribe with non-existent input file"""
        result = self.runner.invoke(cli, ['transcribe', 'nonexistent.mp3', '-o', 'output.txt'])
        self.assertNotEqual(result.exit_code, 0)

    def test_model_choices(self):
        """Test valid model choices are accepted"""
        # Just test that the help shows valid choices
        result = self.runner.invoke(cli, ['transcribe', '--help'])
        self.assertEqual(result.exit_code, 0)
        for model in ['tiny', 'base', 'small', 'medium', 'large']:
            self.assertIn(model, result.output.lower())

    def test_device_choices(self):
        """Test valid device choices are shown"""
        result = self.runner.invoke(cli, ['transcribe', '--help'])
        self.assertEqual(result.exit_code, 0)
        for device in ['auto', 'cpu', 'cuda', 'mps']:
            self.assertIn(device, result.output.lower())


if __name__ == "__main__":
    unittest.main()
