# Phase 13: API Integration - Research

**Researched:** 2026-02-01
**Domain:** FastAPI diarization API endpoints, Pydantic union types, job progress tracking
**Confidence:** HIGH

## Summary

This phase exposes speaker diarization through the existing FastAPI transcription API. The core work involves: (1) extending request models to accept diarization parameters with bool-or-object flexibility, (2) adding new job status fields for diarization progress and partial failure, (3) integrating the orchestrator into the background worker, and (4) adding a retry endpoint for failed diarization.

The standard approach uses Pydantic's smart union validation for the `diarize` parameter (accepts `true` boolean or `{enabled: true, min_speakers: 2}` object), extends the Job model with new fields for diarization state, and modifies the worker to use `TranscriptionOrchestrator` instead of direct transcription. The existing polling pattern (`GET /jobs/{id}`) is retained with enhanced progress reporting.

Key integration point: The worker currently calls `transcriber.transcribe_file()` directly. This must change to use `TranscriptionOrchestrator.orchestrate()` which handles transcription + diarization + formatting in sequence with proper fallback handling.

**Primary recommendation:** Use Pydantic `bool | DiarizeOptions` union with smart mode for the `diarize` parameter, add `PARTIAL` to JobStatus enum for graceful degradation, extend Job model with diarization-specific fields, and modify worker to use orchestrator with progress callbacks.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.100+ | HTTP API framework | Already used, native Pydantic integration |
| Pydantic | 2.0+ | Request/response validation | Already used, smart union mode handles bool\|object |
| aiosqlite | 0.19+ | Async SQLite | Already used for job persistence |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.to_thread | Built-in | Run sync code in thread pool | Worker running orchestrator (blocking) |
| logging | Built-in | Progress and error logging | API-level logging for diarization events |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Bool\|Object union | Separate endpoints | Union is more flexible, single endpoint is simpler API |
| Polling | WebSocket/SSE | Polling is simpler, already established pattern in codebase |
| SQLite fields | Separate table | Single table is simpler, fields are sparse but manageable |

**Installation:**
No new dependencies required - all libraries already in use.

## Architecture Patterns

### Recommended Model Structure
```
cesar/api/
├── models.py           # Add DiarizeOptions, extend Job
├── server.py           # Extend TranscribeURLRequest, add retry endpoint
├── worker.py           # Use TranscriptionOrchestrator instead of AudioTranscriber
├── repository.py       # Handle new Job fields
└── database.py         # Schema migration for new columns
```

### Pattern 1: Pydantic Union for Diarize Parameter
**What:** Accept either boolean or object for `diarize` field using Pydantic smart union
**When to use:** API flexibility where shorthand and full options both make sense

**Example:**
```python
# Source: Pydantic Union documentation + existing codebase patterns
# https://docs.pydantic.dev/latest/concepts/unions/

from typing import Optional, Union
from pydantic import BaseModel, field_validator

class DiarizeOptions(BaseModel):
    """Diarization options when enabled."""
    enabled: bool = True
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None

    @field_validator('min_speakers', 'max_speakers')
    @classmethod
    def validate_speaker_counts(cls, v: Optional[int], info) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError(f"{info.field_name} must be >= 1")
        return v

class TranscribeURLRequest(BaseModel):
    """Request body for URL-based transcription with diarization."""
    url: str
    model: str = "base"
    diarize: Union[bool, DiarizeOptions] = True  # Smart union handles both

    def get_diarize_enabled(self) -> bool:
        """Normalize diarize to boolean."""
        if isinstance(self.diarize, bool):
            return self.diarize
        return self.diarize.enabled

    def get_speaker_range(self) -> tuple[Optional[int], Optional[int]]:
        """Extract min/max speakers (None if boolean or not set)."""
        if isinstance(self.diarize, DiarizeOptions):
            return (self.diarize.min_speakers, self.diarize.max_speakers)
        return (None, None)
```

**Key behaviors:**
- Pydantic smart mode: `true` matches bool exactly, `{enabled: true}` matches DiarizeOptions
- No discriminator needed - types are distinct (bool vs object)
- Validation for min/max_speakers happens in DiarizeOptions
- Helper methods normalize access in endpoint code

### Pattern 2: Extended Job Model with Diarization Fields
**What:** Add fields to Job model for diarization state without breaking existing API
**When to use:** Extending existing models for new features

**Example:**
```python
# Source: Existing cesar/api/models.py patterns

class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"  # NEW: Transcription OK, diarization failed
    ERROR = "error"

class Job(BaseModel):
    # ... existing fields ...

    # Diarization request params (stored for retry)
    diarize: bool = True  # Default matches CLI behavior
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None

    # Progress tracking
    progress: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Overall progress percentage (0-100)"
    )
    progress_phase: Optional[str] = Field(
        default=None,
        description="Current phase: downloading, transcribing, diarizing, formatting"
    )
    progress_phase_pct: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Current phase progress (0-100)"
    )

    # Results (extended)
    speaker_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of speakers detected (None if diarization disabled/failed)"
    )
    diarized: Optional[bool] = Field(
        default=None,
        description="Whether output includes speaker labels (explicit flag for fallback detection)"
    )

    # Partial failure
    diarization_error: Optional[str] = Field(
        default=None,
        description="Error message if diarization failed but transcription succeeded"
    )
```

**Key behaviors:**
- PARTIAL status distinguishes "diarization failed, transcript available" from ERROR
- `diarized` flag is explicit - even when diarize=True, result might have diarized=False (fallback)
- Request params stored on job enable retry with same settings
- Progress fields map to orchestrator callback (step_name, percentage)

### Pattern 3: Structured Progress Response
**What:** Nested progress object in job status response
**When to use:** Multi-phase processing with granular progress

**Example:**
```python
# Source: CONTEXT.md decisions
# progress: {overall: 75, phase: "diarizing", phase_progress: 50}

class ProgressInfo(BaseModel):
    """Progress breakdown for job status."""
    overall: int = Field(ge=0, le=100, description="Overall progress (0-100)")
    phase: str = Field(description="Current phase: downloading, transcribing, diarizing, formatting")
    phase_progress: int = Field(ge=0, le=100, description="Current phase progress (0-100)")

class JobResponse(BaseModel):
    """Job with computed progress object."""
    # ... all Job fields ...

    @computed_field
    @property
    def progress(self) -> Optional[ProgressInfo]:
        """Build progress object from flat fields."""
        if self.progress_overall is None:
            return None
        return ProgressInfo(
            overall=self.progress_overall,
            phase=self.progress_phase or "unknown",
            phase_progress=self.progress_phase_pct or 0
        )
```

**Alternative (simpler):** Store flat fields, compute nested object in response serialization.

### Pattern 4: Worker with Orchestrator Integration
**What:** Replace direct transcription with orchestrator pipeline
**When to use:** When background processing needs to run multi-step pipeline

**Example:**
```python
# Source: Existing cesar/api/worker.py + orchestrator.py patterns

async def _process_job(self, job) -> None:
    """Process job with orchestrator for diarization support."""
    # ... existing download handling ...

    # Create components
    transcriber = AudioTranscriber(model_size=job.model_size)

    diarizer = None
    if job.diarize:
        hf_token = self._get_hf_token()  # From config/env
        if hf_token:
            from cesar.diarization import SpeakerDiarizer
            diarizer = SpeakerDiarizer(hf_token=hf_token)

    orchestrator = TranscriptionOrchestrator(
        transcriber=transcriber,
        diarizer=diarizer
    )

    # Progress callback that updates job in DB
    def progress_callback(step_name: str, percentage: float):
        # Map step names to phase names
        phase_map = {
            "Transcribing...": "transcribing",
            "Detecting speakers...": "diarizing",
            "Formatting...": "formatting",
        }
        phase = phase_map.get(step_name, "processing")

        # Calculate phase progress (reverse from overall)
        # 0-60 = transcribing, 60-90 = diarizing, 90-100 = formatting
        if phase == "transcribing":
            phase_pct = int(percentage / 0.6)
        elif phase == "diarizing":
            phase_pct = int((percentage - 60) / 0.3)
        else:
            phase_pct = int((percentage - 90) / 0.1)

        # Update job (non-blocking via asyncio.to_thread callback)
        job.progress = int(percentage)
        job.progress_phase = phase
        job.progress_phase_pct = phase_pct
        # Note: Actual DB update needs careful async handling

    # Run orchestration in thread pool
    result = await asyncio.to_thread(
        orchestrator.orchestrate,
        audio_path=Path(job.audio_path),
        output_path=temp_output,
        enable_diarization=job.diarize,
        min_speakers=job.min_speakers,
        max_speakers=job.max_speakers,
        progress_callback=progress_callback
    )

    # Update job with results
    if result.diarization_succeeded:
        job.status = JobStatus.COMPLETED
        job.speaker_count = result.speakers_detected
        job.diarized = True
    elif job.diarize and not result.diarization_succeeded:
        job.status = JobStatus.PARTIAL
        job.diarization_error = "Diarization failed, transcript available without speaker labels"
        job.diarized = False
    else:
        job.status = JobStatus.COMPLETED
        job.diarized = False
```

### Pattern 5: Retry Endpoint for Partial Failures
**What:** POST endpoint to re-run failed diarization on existing transcript
**When to use:** When diarization fails but transcript exists

**Example:**
```python
# Source: CONTEXT.md decision - POST /jobs/{id}/retry

@app.post("/jobs/{job_id}/retry", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
async def retry_diarization(job_id: str = PathParam(...)):
    """Retry diarization on a job with partial failure.

    Only works on jobs with status='partial' (transcription succeeded,
    diarization failed). Re-queues the job for diarization-only processing.
    """
    job = await app.state.repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.status != JobStatus.PARTIAL:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry jobs with status 'partial'. Current status: {job.status.value}"
        )

    # Re-queue for diarization retry
    job.status = JobStatus.QUEUED
    job.diarization_error = None
    job.started_at = None
    job.completed_at = None
    await app.state.repo.update(job)

    return job
```

### Anti-Patterns to Avoid
- **Accepting HF token as request parameter:** Security risk - tokens should come from config/env only
- **WebSocket for progress:** Over-engineered - polling is sufficient for batch transcription
- **Separate endpoints for diarize=true/false:** Unnecessary complexity - union type handles both
- **Storing formatted transcript in DB:** Large text bloat - store path to output file instead

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bool/object parameter parsing | Custom request parsing | Pydantic Union[bool, Model] | Pydantic handles validation, errors, OpenAPI schema |
| Multi-step progress | Custom percentage math | Orchestrator progress_callback | Already maps 0-60-90-100 allocation |
| Diarization fallback | Try/except in endpoint | Orchestrator handles internally | TranscriptionOrchestrator catches DiarizationError and falls back |
| Output file paths | String manipulation | orchestrator.output_path | OrchestrationResult returns correct .md or .txt path |
| Speaker validation | Manual min <= max check | Config model validator | CesarConfig already validates speaker range |

**Key insight:** The orchestrator was designed specifically to handle the diarization pipeline with fallback. The worker should delegate to it rather than reimplementing the pipeline logic.

## Common Pitfalls

### Pitfall 1: Progress Updates from Sync Code
**What goes wrong:** Worker runs orchestrator in thread pool, but progress callback tries to await DB update
**Why it happens:** Mixing sync callbacks with async repository methods
**How to avoid:** Use sync progress tracking (update job object), batch DB updates, or use thread-safe queue
**Warning signs:** RuntimeError about event loop, or progress never updates in DB

**Solution approaches:**
```python
# Option A: Batch update after completion
# Progress is tracked in-memory, written to DB only at status changes

# Option B: Thread-safe queue
import queue
progress_queue = queue.Queue()

def progress_callback(step, pct):
    progress_queue.put((step, pct))

# Separate async task reads queue and updates DB
```

### Pitfall 2: Union Type Validation Order Issues
**What goes wrong:** Object like `{enabled: true}` incorrectly matches bool first
**Why it happens:** Pydantic left-to-right mode or incorrect type ordering
**How to avoid:** Use smart union mode (default), put more specific type first if needed
**Warning signs:** Valid objects rejected with "expected bool" error

**Note:** Pydantic 2.x smart mode handles this well by default - bool won't match dict.

### Pitfall 3: Missing HF Token Error Handling
**What goes wrong:** Diarization fails silently or with cryptic pyannote error
**Why it happens:** No explicit check for missing token before attempting diarization
**How to avoid:** Check token availability before creating SpeakerDiarizer, set clear error message
**Warning signs:** Jobs stuck in processing, or AuthenticationError from pyannote

**Example check:**
```python
if job.diarize:
    hf_token = self._get_hf_token()
    if not hf_token:
        job.status = JobStatus.PARTIAL
        job.diarization_error = "hf_token_required: No HuggingFace token configured"
        job.diarized = False
        # Continue with transcription only
```

### Pitfall 4: Retry Endpoint Doesn't Actually Retry Diarization
**What goes wrong:** Retry re-runs full transcription instead of just diarization
**Why it happens:** Worker doesn't distinguish "retry diarization" from "fresh job"
**How to avoid:** Store transcript path separately, check if transcript exists before re-transcribing
**Warning signs:** Retry takes as long as original job

**Solution:** Store intermediate transcript path, worker checks if already transcribed:
```python
if job.result_text and job.diarization_error:
    # This is a retry - skip transcription, run diarization only
    pass
```

### Pitfall 5: Database Schema Migration Breaks Existing Jobs
**What goes wrong:** New columns without defaults cause INSERT failures for existing code
**Why it happens:** Adding NOT NULL columns to existing table
**How to avoid:** All new columns must have DEFAULT or allow NULL
**Warning signs:** "NOT NULL constraint failed" errors after upgrade

## Code Examples

Verified patterns from official sources:

### Complete Request Model with Union
```python
# Based on Pydantic docs and existing codebase patterns

from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

class DiarizeOptions(BaseModel):
    """Diarization configuration when using object form."""
    enabled: bool = True
    min_speakers: Optional[int] = Field(default=None, ge=1)
    max_speakers: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode='after')
    def validate_speaker_range(self) -> 'DiarizeOptions':
        if (self.min_speakers is not None and
            self.max_speakers is not None and
            self.min_speakers > self.max_speakers):
            raise ValueError(
                f"min_speakers ({self.min_speakers}) cannot exceed "
                f"max_speakers ({self.max_speakers})"
            )
        return self

class TranscribeRequest(BaseModel):
    """Base request for transcription with diarization."""
    model: str = "base"
    diarize: Union[bool, DiarizeOptions] = True

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str) -> str:
        valid = {'tiny', 'base', 'small', 'medium', 'large'}
        if v not in valid:
            raise ValueError(f"model must be one of {valid}")
        return v

class TranscribeFileRequest(TranscribeRequest):
    """File upload doesn't need additional fields - file comes via Form."""
    pass

class TranscribeURLRequest(TranscribeRequest):
    """URL-based transcription."""
    url: str
```

### Error Response Models
```python
# Based on existing youtube_handler error patterns

class DiarizationErrorCodes:
    """Error codes for diarization-specific failures."""
    HF_TOKEN_REQUIRED = "hf_token_required"
    HF_TOKEN_INVALID = "hf_token_invalid"
    DIARIZATION_FAILED = "diarization_failed"
    PARTIAL_FAILURE = "partial_failure"

# In Job model
diarization_error_code: Optional[str] = Field(
    default=None,
    description="Error code for diarization failure (hf_token_required, hf_token_invalid, diarization_failed)"
)
```

### Database Schema Migration
```sql
-- New columns for diarization support
-- All nullable or with defaults to maintain compatibility

ALTER TABLE jobs ADD COLUMN diarize INTEGER DEFAULT 1;
ALTER TABLE jobs ADD COLUMN min_speakers INTEGER;
ALTER TABLE jobs ADD COLUMN max_speakers INTEGER;
ALTER TABLE jobs ADD COLUMN progress INTEGER CHECK(progress >= 0 AND progress <= 100);
ALTER TABLE jobs ADD COLUMN progress_phase TEXT;
ALTER TABLE jobs ADD COLUMN progress_phase_pct INTEGER CHECK(progress_phase_pct >= 0 AND progress_phase_pct <= 100);
ALTER TABLE jobs ADD COLUMN speaker_count INTEGER CHECK(speaker_count >= 0);
ALTER TABLE jobs ADD COLUMN diarized INTEGER;
ALTER TABLE jobs ADD COLUMN diarization_error TEXT;
ALTER TABLE jobs ADD COLUMN diarization_error_code TEXT;
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate bool/object endpoints | Union type single endpoint | Pydantic 2.0 | Cleaner API, OpenAPI schema handles both |
| Transcriber-only worker | Orchestrator-based worker | Phase 11 | Full diarization pipeline support |
| Simple error/completed | Partial status enum | This phase | Graceful degradation when diarization fails |
| Flat progress percentage | Phased progress object | This phase | Better UX for multi-step processing |

**Deprecated/outdated:**
- Direct `transcriber.transcribe_file()` in worker: Use orchestrator for diarization support
- `result_text` as primary output: Use `output_path` reference for large transcripts

## Open Questions

Things that couldn't be fully resolved:

1. **Progress callback thread safety**
   - What we know: Orchestrator runs in thread pool, callback is sync
   - What's unclear: Best approach for updating DB from sync callback
   - Recommendation: Update job object in memory, write to DB at phase transitions only

2. **Retry scope**
   - What we know: Retry endpoint exists for partial failures
   - What's unclear: Should retry re-use cached transcript or re-transcribe?
   - Recommendation: Re-use transcript if available (store path), skip transcription step

3. **Segments array in response**
   - What we know: CONTEXT.md marks as Claude's discretion
   - What's unclear: Whether to include raw segment data or just formatted text
   - Recommendation: Start with just formatted text in `result_text`, add `segments` array later if needed

4. **Large transcript storage**
   - What we know: `result_text` stores full transcript in DB
   - What's unclear: Performance impact for very long transcripts
   - Recommendation: Keep current approach, monitor DB size, consider file reference if issues arise

## Sources

### Primary (HIGH confidence)
- [Pydantic Union Documentation](https://docs.pydantic.dev/latest/concepts/unions/) - Union type validation
- [FastAPI Status Codes](https://fastapi.tiangolo.com/reference/status/) - HTTP status codes including 207
- Existing codebase: cesar/api/models.py, server.py, worker.py, repository.py
- Existing codebase: cesar/orchestrator.py, diarization.py, config.py

### Secondary (MEDIUM confidence)
- [FastAPI Polling Strategy](https://openillumi.com/en/en-fastapi-long-task-progress-polling/) - Job status polling patterns
- [FastAPI Background Tasks](https://betterstack.com/community/guides/scaling-python/background-tasks-in-fastapi/) - Background processing
- [Building Resilient Task Queues](https://davidmuraya.com/blog/fastapi-arq-retries/) - Retry patterns

### Tertiary (LOW confidence)
- None - all findings verified against official docs or codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use, patterns verified in codebase
- Architecture: HIGH - Extending existing patterns, orchestrator integration straightforward
- Pitfalls: MEDIUM - Thread safety issues need implementation validation

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (30 days - stable technology stack, existing codebase patterns)
