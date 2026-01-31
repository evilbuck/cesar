"""
Pydantic models for transcription jobs.

Provides the Job model and JobStatus enum for representing
transcription job lifecycle and state.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobStatus(str, Enum):
    """Job lifecycle states.

    Flow: queued -> processing -> completed | error
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class Job(BaseModel):
    """Transcription job data model.

    Represents an audio transcription job with its lifecycle state,
    input parameters, and results.

    Attributes:
        id: Unique job identifier (UUID v4)
        status: Current job status
        audio_path: Path to the audio file to transcribe
        model_size: Whisper model size to use
        created_at: Job creation timestamp (UTC)
        started_at: Processing start timestamp (UTC)
        completed_at: Completion timestamp (UTC)
        result_text: Transcription result text
        detected_language: Detected audio language
        error_message: Error message if job failed
    """

    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM-style attribute access
        str_strip_whitespace=True,
        extra="forbid",  # Fail fast on unknown fields
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.QUEUED

    # Input
    audio_path: str
    model_size: str = "base"

    # Timestamps (UTC)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results (populated on completion)
    result_text: Optional[str] = None
    detected_language: Optional[str] = None

    # Error (populated on failure)
    error_message: Optional[str] = None

    @field_validator("model_size")
    @classmethod
    def validate_model_size(cls, v: str) -> str:
        """Validate model_size is a known Whisper model size."""
        valid = {"tiny", "base", "small", "medium", "large"}
        if v not in valid:
            raise ValueError(f"model_size must be one of {valid}")
        return v

    @field_validator("audio_path")
    @classmethod
    def validate_audio_path(cls, v: str) -> str:
        """Validate audio_path is not empty."""
        if not v or not v.strip():
            raise ValueError("audio_path cannot be empty")
        return v
