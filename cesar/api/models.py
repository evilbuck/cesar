"""
Pydantic models for transcription jobs.

Provides the Job model and JobStatus enum for representing
transcription job lifecycle and state.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JobStatus(str, Enum):
    """Job lifecycle states.

    Flow: queued -> downloading -> processing -> completed | error | partial
    Note: downloading only applies to YouTube URLs
    Note: partial means transcription succeeded but diarization failed
    """

    QUEUED = "queued"
    DOWNLOADING = "downloading"  # YouTube audio extraction
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    PARTIAL = "partial"  # Transcription OK, diarization failed


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

    # Download progress (for YouTube jobs)
    download_progress: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Download progress percentage (0-100) for YouTube jobs. None for non-YouTube jobs."
    )

    # Diarization request parameters
    diarize: bool = Field(
        default=True,
        description="Enable speaker diarization (default: True)"
    )
    min_speakers: Optional[int] = Field(
        default=None,
        ge=1,
        description="Minimum number of speakers to detect"
    )
    max_speakers: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of speakers to detect"
    )

    # Progress tracking
    progress: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Overall progress percentage (0-100)"
    )
    progress_phase: Optional[str] = Field(
        default=None,
        description="Current processing phase: downloading, transcribing, diarizing, formatting"
    )
    progress_phase_pct: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Current phase progress percentage (0-100)"
    )

    # Diarization results
    speaker_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of speakers detected"
    )
    diarized: Optional[bool] = Field(
        default=None,
        description="Whether diarization was applied (explicit flag for fallback detection)"
    )

    # Diarization error fields
    diarization_error: Optional[str] = Field(
        default=None,
        description="Diarization error message if failed"
    )
    diarization_error_code: Optional[str] = Field(
        default=None,
        description="Error code: hf_token_required, hf_token_invalid, diarization_failed"
    )

    @model_validator(mode="after")
    def validate_speaker_range(self) -> "Job":
        """Validate min_speakers <= max_speakers when both are set."""
        if self.min_speakers is not None and self.max_speakers is not None:
            if self.min_speakers > self.max_speakers:
                raise ValueError(
                    f"min_speakers ({self.min_speakers}) cannot be greater than "
                    f"max_speakers ({self.max_speakers})"
                )
        return self

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
