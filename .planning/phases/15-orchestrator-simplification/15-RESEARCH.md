# Phase 15: Orchestrator Simplification - Research

**Researched:** 2026-02-01
**Domain:** Python architecture refactoring - pipeline replacement and error handling
**Confidence:** HIGH

## Summary

This phase involves replacing Cesar's existing multi-component transcription pipeline (AudioTranscriber + SpeakerDiarizer + timestamp_aligner) with the unified WhisperX pipeline implemented in Phase 14. This is primarily an architectural refactoring task focused on simplifying the orchestrator, not a library integration task.

The research covers three critical domains: (1) clean pipeline replacement patterns, (2) Python exception chaining for wrapping WhisperX errors in Cesar's domain exceptions, and (3) graceful degradation patterns for partial success scenarios where transcription succeeds but diarization fails.

The key insight is that WhisperX already handles the complex coordination between transcription, alignment, and diarization internally. The orchestrator's role simplifies from "coordinate three separate components" to "call WhisperX and handle errors gracefully."

**Primary recommendation:** Use constructor-based dependency injection to replace components cleanly, employ Python's `raise ... from e` pattern for exception wrapping, and implement explicit partial-success messaging before fallback to maintain user trust.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib exceptions | 3.12+ | Exception chaining with `__cause__` | PEP 3134 standard for wrapping third-party errors |
| dataclasses | 3.12+ | Data structure compatibility | Structural typing via duck typing |
| typing.Protocol | 3.12+ | Interface compatibility without inheritance | PEP 544 structural subtyping |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | stdlib | Structured error messages | Graceful degradation communication |
| pathlib.Path | stdlib | File path handling | Output file extension changes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Constructor injection | Factory pattern | Constructor injection sufficient for simple replacement |
| Duck typing | Explicit Protocol classes | Duck typing simpler when structure matches exactly |
| Manual exception mapping | Exception groups (PEP 654) | Exception groups overkill for linear pipeline |

**No additional installation required** - this phase uses Python stdlib features exclusively.

## Architecture Patterns

### Recommended Project Structure
```
cesar/
├── whisperx_wrapper.py      # EXISTS: WhisperX pipeline (Phase 14)
├── orchestrator.py           # MODIFIED: Simplified to use WhisperX
├── diarization.py            # MODIFIED: Keep exception classes only
├── timestamp_aligner.py      # DELETED: WhisperX handles alignment
├── transcript_formatter.py   # MINIMAL CHANGES: Accept WhisperXSegment
└── transcriber.py            # UNCHANGED: Keep for non-diarized transcription
```

### Pattern 1: Constructor Dependency Replacement
**What:** Replace multi-component dependencies with single unified pipeline
**When to use:** When migrating from multi-step to unified pipeline
**Example:**
```python
# OLD: Multi-component orchestrator (current)
class TranscriptionOrchestrator:
    def __init__(
        self,
        transcriber: AudioTranscriber,           # Separate transcription
        diarizer: Optional[SpeakerDiarizer],     # Separate diarization
        formatter: Optional[MarkdownTranscriptFormatter]
    ):
        self.transcriber = transcriber
        self.diarizer = diarizer
        self.formatter = formatter

# NEW: Unified pipeline orchestrator (Phase 15)
class TranscriptionOrchestrator:
    def __init__(
        self,
        pipeline: Optional[WhisperXPipeline] = None,  # Single unified pipeline
        formatter: Optional[MarkdownTranscriptFormatter] = None
    ):
        self.pipeline = pipeline
        self.formatter = formatter
```

**Why this works:**
- WhisperX handles transcription + alignment + diarization internally
- Orchestrator responsibility reduces to "call pipeline, format output, handle errors"
- Constructor change forces callers to update (fail-fast migration)

### Pattern 2: Python Exception Chaining for Third-Party Wrapping
**What:** Wrap WhisperX exceptions in Cesar's domain exceptions while preserving cause chain
**When to use:** Always when catching exceptions from third-party libraries
**Example:**
```python
# Source: PEP 3134 - Exception Chaining and Embedded Tracebacks
# https://peps.python.org/pep-3134/

# In WhisperXPipeline._load_diarize_model():
try:
    self._diarize_model = whisperx.DiarizationPipeline(
        use_auth_token=self.hf_token,
        device=self.device
    )
except Exception as e:
    error_str = str(e)
    # Detect authentication failures
    if "401" in error_str or "Unauthorized" in error_str or "access" in error_str.lower():
        raise AuthenticationError(
            "HuggingFace authentication failed.\n"
            "1. Get token at: https://hf.co/settings/tokens\n"
            "2. Accept conditions at: https://hf.co/pyannote/speaker-diarization-3.1\n"
            "3. Accept conditions at: https://hf.co/pyannote/segmentation-3.0\n"
            "4. Set hf_token in config or HF_TOKEN environment variable"
        ) from e  # ← Explicit chaining preserves original traceback
    # Generic diarization errors
    raise DiarizationError(f"Failed to load diarization model: {e}") from e
```

**Key details:**
- `raise ... from e` sets `__cause__` attribute to original exception
- Preserves full traceback chain for debugging
- User sees domain exception (DiarizationError), developers see root cause
- `__cause__` displayed in traceback as "The above exception was the direct cause..."

**Anti-pattern to avoid:**
```python
# WRONG: Loses original traceback
except Exception as e:
    raise DiarizationError(f"Failed: {e}")  # Missing "from e"

# WRONG: Exposes implementation details
except whisperx.DiarizationError as e:
    raise e  # Leaks WhisperX-specific exception
```

### Pattern 3: Graceful Degradation with Explicit Messaging
**What:** Communicate partial success before falling back to degraded functionality
**When to use:** When one step succeeds but dependent step fails
**Example:**
```python
# Source: Medium - Robust Error Handling in Python (2025)
# https://medium.com/@RampantLions/robust-error-handling-in-python-tracebacks-graceful-degradation-and-suppression-11f7a140720b

# In orchestrator.orchestrate():
try:
    # Step 1: Transcription (REQUIRED)
    segments, metadata = self.pipeline.transcribe_and_diarize(
        audio_path,
        min_speakers=min_speakers,
        max_speakers=max_speakers
    )
    transcription_succeeded = True
    diarization_succeeded = True

except DiarizationError as e:
    # Diarization failed, but transcription may have succeeded
    logger.warning(
        f"Transcription succeeded, but diarization failed: {e}\n"
        f"Falling back to plain transcript without speaker labels."
    )
    # Retry transcription-only
    segments = self.pipeline.transcribe_only(audio_path)
    transcription_succeeded = True
    diarization_succeeded = False

except Exception as e:
    # Complete failure - transcription is REQUIRED
    raise
```

**Why explicit messaging matters:**
- User knows what worked and what didn't (builds trust)
- "Falling back to X" communicates degraded but functional state
- Logs contain diagnostic information for debugging
- Distinguishes between partial and complete failure

**User-facing error message pattern:**
```
"Transcription succeeded, diarization failed: [specific reason]"
```

### Pattern 4: Structural Compatibility via Duck Typing
**What:** Ensure WhisperXSegment works with MarkdownTranscriptFormatter without changes
**When to use:** When two dataclasses have identical structure
**Example:**
```python
# Source: PEP 544 - Protocols: Structural subtyping
# https://peps.python.org/pep-0544/

# Current formatter expects AlignedSegment:
@dataclass
class AlignedSegment:
    start: float
    end: float
    speaker: str
    text: str

# WhisperXSegment has identical structure:
@dataclass
class WhisperXSegment:
    start: float
    end: float
    speaker: str
    text: str

# Formatter works with both via duck typing:
class MarkdownTranscriptFormatter:
    def format(self, segments: List[AlignedSegment]) -> str:
        # Also accepts List[WhisperXSegment] without changes
        for seg in segments:
            seg.start    # ✓ Duck typing: attribute exists
            seg.end      # ✓
            seg.speaker  # ✓
            seg.text     # ✓
```

**Why this works:**
- Python uses structural typing (duck typing) for runtime behavior
- Type checkers accept compatible dataclasses without explicit Protocol
- Formatter doesn't care about class name, only attribute structure
- Zero changes needed if structure matches

**When Protocol is needed:**
```python
# Optional: Make compatibility explicit for type checkers
from typing import Protocol

class SegmentLike(Protocol):
    start: float
    end: float
    speaker: str
    text: str

class MarkdownTranscriptFormatter:
    def format(self, segments: List[SegmentLike]) -> str:
        # Now explicitly accepts any SegmentLike
        ...
```

### Anti-Patterns to Avoid
- **Partial dependency injection:** Don't keep old components "just in case" - clean replacement is clearer
- **Silent fallback:** Don't hide failures from users - explicit messaging builds trust
- **Manual exception translation:** Don't create elaborate exception mapping - use `from e` chain
- **Preserving dead interfaces:** Don't keep timestamp_aligner.py "for reference" - git history preserves it

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exception translation layer | Custom exception mapper | `raise ... from e` | Python stdlib pattern, preserves traceback |
| Retry logic for diarization | Custom retry loops | Try-except with explicit fallback | Simpler, clearer intent |
| Type compatibility checking | isinstance() checks | Duck typing | Python idiom, simpler code |
| Partial success tracking | Boolean flags everywhere | Single try-except with clear logging | Easier to follow control flow |

**Key insight:** Python's stdlib exception chaining and duck typing are specifically designed for these scenarios. Custom abstractions add complexity without benefit.

## Common Pitfalls

### Pitfall 1: Exception Cause Chain Omission
**What goes wrong:** Using `raise NewError(...)` without `from e` loses original traceback
**Why it happens:** Developers forget `from e` or don't know about exception chaining
**How to avoid:**
- Always use `raise CustomException(...) from e` when wrapping
- Linters can catch this: `pylint --enable=raise-missing-from`
- Code review checklist: "All third-party exceptions wrapped with from?"
**Warning signs:** Users report errors but logs don't show root cause

### Pitfall 2: Exposing Implementation Details in Errors
**What goes wrong:** Error messages mention "WhisperX" or internal class names
**Why it happens:** Raising third-party exceptions directly or using their names in messages
**How to avoid:**
- Map all WhisperX errors to Cesar domain exceptions (DiarizationError, AuthenticationError)
- Error messages should use domain language ("diarization failed" not "WhisperX.DiarizationPipeline failed")
- Test error messages: would a user understand them without reading code?
**Warning signs:** Error messages contain library names or technical implementation details

### Pitfall 3: Silent Fallback Without User Communication
**What goes wrong:** Diarization fails silently, user gets plain transcript without knowing why
**Why it happens:** Catching exceptions but only logging (user never sees logs)
**How to avoid:**
- Log with WARNING level: visible in default log output
- Structure message: "[what succeeded], but [what failed]: [reason]. [what we're doing instead]."
- Example: "Transcription succeeded, but diarization failed: HuggingFace authentication required. Saving plain transcript."
**Warning signs:** Users confused why speaker labels are missing when diarization was enabled

### Pitfall 4: Incomplete Component Removal
**What goes wrong:** Deleting timestamp_aligner.py but leaving imports or references
**Why it happens:** Module used in multiple places, easy to miss references
**How to avoid:**
- `grep -r "timestamp_aligner" .` before committing
- `grep -r "align_timestamps" .` (function name)
- Python will raise ImportError if references remain (good!)
- Update all imports in same commit as deletion
**Warning signs:** Import errors after deletion, tests fail

### Pitfall 5: Formatter Assumes Specific Dataclass Type
**What goes wrong:** Formatter uses `isinstance(seg, AlignedSegment)` check
**Why it happens:** Over-defensive type checking
**How to avoid:**
- Rely on duck typing: access attributes directly
- If type check needed, check for attributes: `hasattr(seg, 'speaker')`
- Or use Protocol for explicit structural typing
**Warning signs:** TypeError when passing WhisperXSegment to formatter

### Pitfall 6: Preserving Old Pipeline "Just in Case"
**What goes wrong:** Orchestrator keeps both old and new pipelines, complexity grows
**Why it happens:** Fear of breaking existing functionality
**How to avoid:**
- CONTEXT.md confirms: "Clean replacement — delete old code entirely"
- Git history preserves old implementation if ever needed
- Single code path is easier to maintain and test
- Feature flags if gradual rollout needed (not mentioned in requirements)
**Warning signs:** Orchestrator has `use_legacy_pipeline` flag or dual code paths

## Code Examples

Verified patterns from official sources:

### Complete Orchestrator Simplification
```python
# Source: Combining Python stdlib patterns with Cesar architecture

class TranscriptionOrchestrator:
    """Orchestrate WhisperX pipeline with graceful fallback."""

    def __init__(
        self,
        pipeline: Optional[WhisperXPipeline] = None,
        formatter: Optional[MarkdownTranscriptFormatter] = None
    ):
        self.pipeline = pipeline
        self.formatter = formatter

    def orchestrate(
        self,
        audio_path: Path,
        output_path: Path,
        enable_diarization: bool = True,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> OrchestrationResult:
        """Run transcription with optional diarization.

        Gracefully falls back to plain transcript if diarization fails.
        """

        diarization_succeeded = False
        speakers_detected = 0

        # Attempt full pipeline with diarization
        if enable_diarization and self.pipeline is not None:
            try:
                segments, speakers_detected, audio_duration = self.pipeline.transcribe_and_diarize(
                    str(audio_path),
                    min_speakers=min_speakers,
                    max_speakers=max_speakers,
                    progress_callback=progress_callback
                )
                diarization_succeeded = True

            except AuthenticationError as e:
                # Authentication is user-fixable, don't hide it
                logger.error(f"HuggingFace authentication required: {e}")
                raise  # Re-raise for user to fix

            except DiarizationError as e:
                # Diarization failed, but transcription may have succeeded
                logger.warning(
                    f"Transcription succeeded, diarization failed: {e}\n"
                    f"Falling back to plain transcript without speaker labels."
                )
                # TODO: Implement transcription-only fallback
                segments = self._transcribe_only(audio_path, progress_callback)
                diarization_succeeded = False

        else:
            # Diarization disabled or no pipeline
            segments = self._transcribe_only(audio_path, progress_callback)

        # Format and save output
        if diarization_succeeded:
            final_output = self._save_with_speakers(segments, output_path, audio_duration)
        else:
            final_output = self._save_plain_transcript(segments, output_path)

        return OrchestrationResult(
            output_path=final_output,
            speakers_detected=speakers_detected,
            audio_duration=audio_duration,
            diarization_succeeded=diarization_succeeded,
            # ... other metrics
        )
```

### Exception Wrapping with Cause Chain
```python
# Source: Python Built-in Exceptions documentation
# https://docs.python.org/3/library/exceptions.html

# In WhisperXPipeline or orchestrator:
try:
    result = whisperx_operation()
except Exception as e:
    # Explicit chaining with diagnostic information
    raise DiarizationError(
        f"Speaker detection failed. Check audio quality and HuggingFace token."
    ) from e
    # __cause__ preserves original exception
    # __suppress_context__ hides implicit context
```

### Partial Success with Structured Logging
```python
# Source: AWS Well-Architected Framework - Graceful Degradation
# https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_graceful_degradation.html

# Structured log message for partial success:
logger.warning(
    "Partial pipeline success",
    extra={
        "transcription_status": "succeeded",
        "diarization_status": "failed",
        "diarization_error": str(e),
        "fallback_action": "plain_transcript",
        "audio_path": str(audio_path)
    }
)
```

### Duck Typing Compatibility Check
```python
# Source: PEP 544 - Protocols: Structural subtyping
# https://peps.python.org/pep-0544/

# Optional runtime check for debugging:
def _validate_segment_structure(segments: List) -> None:
    """Verify segments have required attributes for formatter."""
    if not segments:
        return

    required_attrs = ('start', 'end', 'speaker', 'text')
    sample = segments[0]

    for attr in required_attrs:
        if not hasattr(sample, attr):
            raise TypeError(
                f"Segment missing required attribute: {attr}\n"
                f"Got type: {type(sample).__name__}"
            )
```

## State of the Art

| Old Approach (Cesar v2.2) | Current Approach (Phase 15) | When Changed | Impact |
|---------------------------|----------------------------|--------------|--------|
| Multi-component orchestration | Unified WhisperX pipeline | Phase 15 | Simpler orchestrator logic |
| Custom timestamp alignment | WhisperX internal alignment | Phase 14 | Delete timestamp_aligner.py |
| Manual exception mapping | Python stdlib `from e` chaining | Phase 15 | Preserves full traceback |
| Implicit fallback | Explicit partial-success messaging | Phase 15 | Better user communication |
| Three constructor dependencies | One pipeline dependency | Phase 15 | Simpler initialization |

**Deprecated/outdated:**
- `timestamp_aligner.py`: Replaced by WhisperX wav2vec2 alignment
- `SpeakerDiarizer` constructor parameter: Replaced by WhisperXPipeline
- Separate transcription + diarization steps: Unified in WhisperX

**New patterns:**
- Exception chaining with `raise ... from e`: Python 3+ standard pattern
- Duck typing for dataclass compatibility: PEP 544 structural subtyping
- Explicit partial-success messaging: AWS Well-Architected graceful degradation

## Open Questions

Things that couldn't be fully resolved:

1. **Should transcriber.py be kept for non-diarized transcription?**
   - What we know: WhisperX can do transcription-only by skipping diarization steps
   - What's unclear: Whether to keep AudioTranscriber for backward compatibility or use WhisperX for all transcription
   - Recommendation: Evaluate in implementation - WhisperX for consistency, or keep AudioTranscriber if significantly faster for transcription-only use case

2. **Should diarizer.py be deleted or kept for exception definitions?**
   - What we know: CONTEXT.md says "Claude decides... diarizer.py if WhisperX replaces it"
   - What's unclear: Where should DiarizationError and AuthenticationError live?
   - Recommendation: Keep diarization.py with exception classes only (delete SpeakerDiarizer class) - maintains import compatibility

3. **Word-level vs segment-level timestamps in output?**
   - What we know: WhisperX provides word-level timestamps, formatter currently uses segment-level
   - What's unclear: Whether to expose word-level granularity in markdown output
   - Recommendation: CONTEXT.md marks as "Claude's Discretion" - start with segment-level (matches current output), consider word-level in future if users request

4. **Handling transcription-only fallback implementation?**
   - What we know: Need fallback when diarization fails
   - What's unclear: Does WhisperX support transcribe-without-diarize, or need separate AudioTranscriber call?
   - Recommendation: Check WhisperX API - if it supports partial pipeline, use that; otherwise keep AudioTranscriber for fallback

## Sources

### Primary (HIGH confidence)
- [PEP 3134 - Exception Chaining and Embedded Tracebacks](https://peps.python.org/pep-3134/) - Official specification for `raise ... from e`
- [Python Built-in Exceptions documentation](https://docs.python.org/3/library/exceptions.html) - `__cause__`, `__context__`, `__suppress_context__` attributes
- [PEP 544 - Protocols: Structural subtyping](https://peps.python.org/pep-0544/) - Duck typing and Protocol classes

### Secondary (MEDIUM confidence)
- [Python Exception Handling: Patterns and Best Practices](https://jerrynsh.com/python-exception-handling-patterns-and-best-practices/) - Wrapping third-party exceptions
- [Real Python: Duck Typing in Python](https://realpython.com/duck-typing-python/) - Structural compatibility patterns
- [Medium: Robust Error Handling in Python](https://medium.com/@RampantLions/robust-error-handling-in-python-tracebacks-graceful-degradation-and-suppression-11f7a140720b) - Graceful degradation patterns (2025)
- [AWS Well-Architected: Graceful Degradation](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_graceful_degradation.html) - Partial failure patterns
- [Python Dependency Injection Guide](https://betterstack.com/community/guides/scaling-python/python-dependency-injection/) - Constructor injection patterns

### Tertiary (LOW confidence)
- [Coding Data Pipeline Design Patterns in Python](https://amsayed.medium.com/coding-data-pipeline-design-patterns-in-python-44a705f0af9e) - Pipeline refactoring patterns
- [Start Data Engineering: Code Patterns](https://www.startdataengineering.com/post/code-patterns/) - Facade pattern for unified pipelines

### Internal (Cesar codebase - HIGH confidence)
- Phase 14 Research: WhisperX architecture and API
- Current orchestrator.py: Multi-component pattern to replace
- Current timestamp_aligner.py: Module to delete
- Current diarization.py: Exception classes to preserve

## Metadata

**Confidence breakdown:**
- Exception chaining patterns: HIGH - Official Python documentation (PEP 3134)
- Duck typing compatibility: HIGH - Official Python documentation (PEP 544)
- Graceful degradation: MEDIUM - Industry patterns from multiple sources
- Pipeline refactoring: MEDIUM - Cesar-specific application of general patterns

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (30 days - stdlib patterns are stable)

**Key constraints from CONTEXT.md:**
- Clean replacement, delete old code entirely
- Generic error messages, don't expose "WhisperX" in user-facing errors
- Explicit partial success messaging before fallback
- Formatter should adapt to WhisperXSegment directly
