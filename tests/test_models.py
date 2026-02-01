"""
Unit tests for Job model and JobStatus enum.

Tests cover:
- JobStatus enum values and conversions
- Job creation with defaults and explicit values
- Validation (model_size, audio_path, extra fields)
- Optional field handling
- Serialization (model_dump, model_dump_json)
"""
import json
import unittest
import uuid
from datetime import datetime, timedelta

from pydantic import ValidationError

from cesar.api.models import Job, JobStatus


class TestJobStatus(unittest.TestCase):
    """Tests for JobStatus enum."""

    def test_all_status_values_exist(self):
        """All five status values should exist."""
        statuses = list(JobStatus)
        self.assertEqual(len(statuses), 5)
        self.assertIn(JobStatus.QUEUED, statuses)
        self.assertIn(JobStatus.DOWNLOADING, statuses)
        self.assertIn(JobStatus.PROCESSING, statuses)
        self.assertIn(JobStatus.COMPLETED, statuses)
        self.assertIn(JobStatus.ERROR, statuses)

    def test_status_values_are_strings(self):
        """Status values should be lowercase strings."""
        self.assertEqual(JobStatus.QUEUED.value, "queued")
        self.assertEqual(JobStatus.DOWNLOADING.value, "downloading")
        self.assertEqual(JobStatus.PROCESSING.value, "processing")
        self.assertEqual(JobStatus.COMPLETED.value, "completed")
        self.assertEqual(JobStatus.ERROR.value, "error")

    def test_string_to_enum_conversion(self):
        """Should convert string to enum and back."""
        status = JobStatus("queued")
        self.assertEqual(status, JobStatus.QUEUED)
        self.assertEqual(str(status.value), "queued")

    def test_enum_inherits_from_str(self):
        """JobStatus should be usable as a string."""
        self.assertIsInstance(JobStatus.QUEUED, str)
        self.assertEqual(JobStatus.QUEUED, "queued")


class TestJobCreation(unittest.TestCase):
    """Tests for Job model creation."""

    def test_create_with_only_audio_path(self):
        """Job created with only audio_path should get defaults."""
        job = Job(audio_path="/path/to/audio.mp3")

        self.assertEqual(job.audio_path, "/path/to/audio.mp3")
        self.assertEqual(job.status, JobStatus.QUEUED)
        self.assertEqual(job.model_size, "base")
        self.assertIsNotNone(job.id)
        self.assertIsNotNone(job.created_at)

    def test_create_with_all_fields(self):
        """Job created with all fields should preserve values."""
        now = datetime.utcnow()
        job = Job(
            id="custom-id",
            status=JobStatus.COMPLETED,
            audio_path="/path/to/audio.mp3",
            model_size="large",
            created_at=now,
            started_at=now,
            completed_at=now,
            result_text="Hello world",
            detected_language="en",
            error_message=None,
        )

        self.assertEqual(job.id, "custom-id")
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(job.audio_path, "/path/to/audio.mp3")
        self.assertEqual(job.model_size, "large")
        self.assertEqual(job.created_at, now)
        self.assertEqual(job.started_at, now)
        self.assertEqual(job.completed_at, now)
        self.assertEqual(job.result_text, "Hello world")
        self.assertEqual(job.detected_language, "en")
        self.assertIsNone(job.error_message)

    def test_job_id_is_valid_uuid(self):
        """Auto-generated job ID should be a valid UUID."""
        job = Job(audio_path="/test.mp3")
        # Validate UUID format by parsing it
        parsed = uuid.UUID(job.id)
        self.assertEqual(str(parsed), job.id)

    def test_created_at_is_approximately_now(self):
        """created_at should be set to approximately current time."""
        before = datetime.utcnow()
        job = Job(audio_path="/test.mp3")
        after = datetime.utcnow()

        self.assertGreaterEqual(job.created_at, before)
        self.assertLessEqual(job.created_at, after)

    def test_timestamps_are_utc(self):
        """Timestamps should be naive datetime (UTC)."""
        job = Job(audio_path="/test.mp3")
        # datetime.utcnow() returns naive datetime
        self.assertIsNone(job.created_at.tzinfo)


class TestJobValidation(unittest.TestCase):
    """Tests for Job model validation."""

    def test_invalid_model_size_raises_error(self):
        """Invalid model_size should raise ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            Job(audio_path="/test.mp3", model_size="invalid")

        errors = ctx.exception.errors()
        self.assertEqual(len(errors), 1)
        self.assertIn("model_size", str(errors[0]))

    def test_valid_model_sizes(self):
        """All valid model sizes should work."""
        for size in ["tiny", "base", "small", "medium", "large"]:
            job = Job(audio_path="/test.mp3", model_size=size)
            self.assertEqual(job.model_size, size)

    def test_extra_fields_raise_error(self):
        """Extra fields should raise ValidationError (extra='forbid')."""
        with self.assertRaises(ValidationError) as ctx:
            Job(audio_path="/test.mp3", unknown_field="value")

        errors = ctx.exception.errors()
        self.assertEqual(errors[0]["type"], "extra_forbidden")

    def test_empty_audio_path_raises_error(self):
        """Empty audio_path should raise ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            Job(audio_path="")

        errors = ctx.exception.errors()
        self.assertEqual(len(errors), 1)
        self.assertIn("audio_path", str(errors[0]))

    def test_whitespace_audio_path_raises_error(self):
        """Whitespace-only audio_path should raise ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            Job(audio_path="   ")

        errors = ctx.exception.errors()
        self.assertIn("audio_path", str(errors[0]))

    def test_whitespace_stripped_from_audio_path(self):
        """Leading/trailing whitespace should be stripped from audio_path."""
        job = Job(audio_path="  /path/to/file.mp3  ")
        self.assertEqual(job.audio_path, "/path/to/file.mp3")


class TestOptionalFields(unittest.TestCase):
    """Tests for optional field handling."""

    def test_optional_fields_default_to_none(self):
        """Optional fields should default to None."""
        job = Job(audio_path="/test.mp3")

        self.assertIsNone(job.started_at)
        self.assertIsNone(job.completed_at)
        self.assertIsNone(job.result_text)
        self.assertIsNone(job.detected_language)
        self.assertIsNone(job.error_message)

    def test_optional_fields_can_be_set(self):
        """Optional fields should accept values."""
        now = datetime.utcnow()
        job = Job(
            audio_path="/test.mp3",
            started_at=now,
            completed_at=now,
            result_text="Transcribed text",
            detected_language="en",
            error_message="Some error",
        )

        self.assertEqual(job.started_at, now)
        self.assertEqual(job.completed_at, now)
        self.assertEqual(job.result_text, "Transcribed text")
        self.assertEqual(job.detected_language, "en")
        self.assertEqual(job.error_message, "Some error")

    def test_timestamps_accept_datetime_objects(self):
        """Timestamp fields should accept datetime objects."""
        past = datetime.utcnow() - timedelta(hours=1)
        now = datetime.utcnow()

        job = Job(
            audio_path="/test.mp3",
            created_at=past,
            started_at=past,
            completed_at=now,
        )

        self.assertEqual(job.created_at, past)
        self.assertEqual(job.started_at, past)
        self.assertEqual(job.completed_at, now)


class TestSerialization(unittest.TestCase):
    """Tests for Job serialization."""

    def test_model_dump_to_dict(self):
        """Job should serialize to dict via model_dump()."""
        job = Job(audio_path="/test.mp3")
        data = job.model_dump()

        self.assertIsInstance(data, dict)
        self.assertEqual(data["audio_path"], "/test.mp3")
        self.assertEqual(data["status"], JobStatus.QUEUED)
        self.assertEqual(data["model_size"], "base")
        self.assertIn("id", data)
        self.assertIn("created_at", data)

    def test_model_dump_json(self):
        """Job should serialize to JSON via model_dump_json()."""
        job = Job(audio_path="/test.mp3")
        json_str = job.model_dump_json()

        self.assertIsInstance(json_str, str)
        # Verify it's valid JSON
        data = json.loads(json_str)
        self.assertEqual(data["audio_path"], "/test.mp3")
        self.assertEqual(data["status"], "queued")

    def test_recreate_from_dict(self):
        """Job should be recreatable from dict."""
        original = Job(audio_path="/test.mp3", model_size="small")
        data = original.model_dump()

        recreated = Job(**data)

        self.assertEqual(recreated.id, original.id)
        self.assertEqual(recreated.audio_path, original.audio_path)
        self.assertEqual(recreated.model_size, original.model_size)
        self.assertEqual(recreated.status, original.status)
        self.assertEqual(recreated.created_at, original.created_at)

    def test_json_roundtrip(self):
        """Job should survive JSON roundtrip."""
        original = Job(
            audio_path="/test.mp3",
            model_size="medium",
            result_text="Test result",
        )

        json_str = original.model_dump_json()
        data = json.loads(json_str)
        recreated = Job(**data)

        self.assertEqual(recreated.id, original.id)
        self.assertEqual(recreated.audio_path, original.audio_path)
        self.assertEqual(recreated.result_text, original.result_text)


class TestDownloadProgress:
    """Tests for download_progress field validation."""

    def test_download_progress_none_for_regular_jobs(self):
        """Test download_progress defaults to None."""
        job = Job(audio_path="/tmp/test.mp3")
        assert job.download_progress is None

    def test_download_progress_accepts_valid_values(self):
        """Test download_progress accepts 0-100."""
        job = Job(audio_path="/tmp/test.mp3", download_progress=0)
        assert job.download_progress == 0

        job = Job(audio_path="/tmp/test.mp3", download_progress=50)
        assert job.download_progress == 50

        job = Job(audio_path="/tmp/test.mp3", download_progress=100)
        assert job.download_progress == 100

    def test_download_progress_rejects_negative(self):
        """Test download_progress rejects negative values."""
        import pytest

        with pytest.raises(ValidationError):
            Job(audio_path="/tmp/test.mp3", download_progress=-1)

    def test_download_progress_rejects_over_100(self):
        """Test download_progress rejects values over 100."""
        import pytest

        with pytest.raises(ValidationError):
            Job(audio_path="/tmp/test.mp3", download_progress=101)


if __name__ == "__main__":
    unittest.main()
