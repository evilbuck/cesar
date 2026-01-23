# Phase 2: Foundation - Research

**Researched:** 2026-01-23
**Domain:** Job models and SQLite repository for async job queue
**Confidence:** HIGH

## Summary

Phase 2 establishes the data layer for the async transcription API. This includes:
1. **Job model** with Pydantic for validation and serialization
2. **SQLite schema** for persistent job storage
3. **Repository pattern** with aiosqlite for async database operations
4. **State management** via enum-based job status

The standard approach uses Pydantic v2 models for the Job entity, a simple repository class wrapping aiosqlite for CRUD operations, and SQLite with WAL mode for concurrent access. This phase is purely data layer - no API endpoints or background workers yet.

**Primary recommendation:** Use Pydantic models for in-memory Job representation, aiosqlite with WAL mode for persistence, and a clean repository pattern with explicit transaction control.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pydantic** | `>=2.0.0` | Job model validation | Industry standard for Python data validation. Implicit via FastAPI. Strong typing, serialization, validation in one package. |
| **aiosqlite** | `>=0.22.0` | Async SQLite access | Only maintained async wrapper for sqlite3. Single background thread model prevents blocking event loop. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **uuid** | stdlib | Job ID generation | Use UUIDv4 for globally unique job identifiers |
| **datetime** | stdlib | Timestamp handling | Use UTC for all timestamps (created_at, started_at, etc.) |
| **enum** | stdlib | Job status states | Type-safe state representation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| aiosqlite | SQLAlchemy async | SQLAlchemy adds complexity; raw SQL is sufficient for simple job CRUD |
| aiosqlite | pydantic_sqlite | Less mature, adds dependency for marginal benefit |
| aiosqlite | encode/databases | More abstraction than needed; aiosqlite is simpler for SQLite-only |
| raw SQL | aiosql | SQL-file approach adds complexity; inline SQL is fine for small schema |

**Installation:**
```bash
pip install "pydantic>=2.0.0" "aiosqlite>=0.22.0"
```

Note: pydantic is already implicit via FastAPI (`fastapi[standard]`), which is added in later phases.

## Architecture Patterns

### Recommended Project Structure
```
cesar/
  __init__.py
  cli.py                # Existing CLI
  transcriber.py        # Existing transcription logic
  api/
    __init__.py
    models.py           # Pydantic Job model and enums
    database.py         # SQLite schema and connection management
    repository.py       # JobRepository class with CRUD operations
```

### Pattern 1: Pydantic Job Model with Enum Status

**What:** Define Job as a Pydantic model with an Enum for status states
**When to use:** Always - this is the canonical approach for typed Python data models
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid

class JobStatus(str, Enum):
    """Job lifecycle states.

    Flow: queued -> processing -> completed | error
    """
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class Job(BaseModel):
    """Transcription job data model."""

    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM-style attribute access
        str_strip_whitespace=True,
        extra='forbid',  # Fail fast on unknown fields
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
```

### Pattern 2: Repository Pattern with aiosqlite

**What:** Encapsulate all database operations in a repository class
**When to use:** Always - separates data access from business logic
**Example:**
```python
# Source: https://aiosqlite.omnilib.dev/en/stable/api.html
import aiosqlite
from pathlib import Path
from typing import Optional, List
from datetime import datetime

class JobRepository:
    """Async repository for Job persistence in SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open database connection with optimal settings."""
        self._connection = await aiosqlite.connect(self.db_path)
        # Enable WAL mode for concurrent access
        await self._connection.execute("PRAGMA journal_mode=WAL;")
        # Increase busy timeout to 5 seconds
        await self._connection.execute("PRAGMA busy_timeout=5000;")
        # Enable foreign keys
        await self._connection.execute("PRAGMA foreign_keys=ON;")
        # Balance durability and performance
        await self._connection.execute("PRAGMA synchronous=NORMAL;")
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def create(self, job: Job) -> Job:
        """Insert new job into database."""
        await self._connection.execute(
            """
            INSERT INTO jobs (id, status, audio_path, model_size,
                              created_at, started_at, completed_at,
                              result_text, detected_language, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job.id, job.status.value, job.audio_path, job.model_size,
             job.created_at.isoformat(),
             job.started_at.isoformat() if job.started_at else None,
             job.completed_at.isoformat() if job.completed_at else None,
             job.result_text, job.detected_language, job.error_message)
        )
        await self._connection.commit()
        return job

    async def get(self, job_id: str) -> Optional[Job]:
        """Retrieve job by ID."""
        async with self._connection.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_job(row)
            return None

    async def update(self, job: Job) -> Job:
        """Update existing job."""
        await self._connection.execute(
            """
            UPDATE jobs SET
                status = ?, started_at = ?, completed_at = ?,
                result_text = ?, detected_language = ?, error_message = ?
            WHERE id = ?
            """,
            (job.status.value,
             job.started_at.isoformat() if job.started_at else None,
             job.completed_at.isoformat() if job.completed_at else None,
             job.result_text, job.detected_language, job.error_message,
             job.id)
        )
        await self._connection.commit()
        return job

    async def list_all(self) -> List[Job]:
        """List all jobs ordered by creation time."""
        async with self._connection.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    def _row_to_job(self, row: tuple) -> Job:
        """Convert database row to Job model."""
        return Job(
            id=row[0],
            status=JobStatus(row[1]),
            audio_path=row[2],
            model_size=row[3],
            created_at=datetime.fromisoformat(row[4]),
            started_at=datetime.fromisoformat(row[5]) if row[5] else None,
            completed_at=datetime.fromisoformat(row[6]) if row[6] else None,
            result_text=row[7],
            detected_language=row[8],
            error_message=row[9],
        )
```

### Pattern 3: Schema Initialization

**What:** Create tables on first use, idempotent via IF NOT EXISTS
**When to use:** On application startup / repository connect
**Example:**
```python
# Source: https://github.com/litements/litequeue (schema pattern)

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    audio_path TEXT NOT NULL,
    model_size TEXT NOT NULL DEFAULT 'base',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    result_text TEXT,
    detected_language TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
"""

async def initialize_schema(connection: aiosqlite.Connection) -> None:
    """Create tables if they don't exist."""
    await connection.executescript(SCHEMA)
    await connection.commit()
```

### Anti-Patterns to Avoid

- **Using sync sqlite3 in async context:** Blocks event loop. Always use aiosqlite.
- **Storing timestamps as Unix epoch:** Use ISO 8601 strings for readability and SQLite compatibility.
- **Using AUTO_INCREMENT integer IDs:** UUIDs are better for distributed systems and prevent enumeration attacks.
- **Raw status strings:** Use Enum to catch typos and enable IDE completion.
- **Connection per query:** Expensive. Use a single long-lived connection with proper lifecycle management.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Data validation | Manual if/else checks | Pydantic models | Handles type coercion, validation errors, serialization automatically |
| UUID generation | Random strings | `uuid.uuid4()` | Guaranteed unique, standard format |
| Async SQLite | Threading wrappers | aiosqlite | Mature, maintained, handles edge cases |
| ISO timestamps | Manual string formatting | `datetime.isoformat()` | Standard, handles timezone properly |
| State enum | String constants | `enum.Enum` | Type safety, IDE completion, prevents typos |

**Key insight:** The temptation is to write minimal raw SQL without abstractions. While raw SQL is fine, use Pydantic for the model layer - the validation and serialization pay off immediately in later phases when building the API.

## Common Pitfalls

### Pitfall 1: Database Locked Errors (SQLite Contention)

**What goes wrong:** Multiple async operations try to write simultaneously, causing `sqlite3.OperationalError: database is locked`
**Why it happens:** SQLite allows only one writer at a time. Default timeout is too short (5 seconds).
**How to avoid:**
  - Enable WAL mode: `PRAGMA journal_mode=WAL;`
  - Increase busy_timeout: `PRAGMA busy_timeout=5000;` (or higher)
  - Keep transactions short
  - Commit after each write operation
**Warning signs:** Intermittent "database is locked" errors under concurrent load

### Pitfall 2: Blocking Event Loop with Sync Code

**What goes wrong:** Using sync `sqlite3` module in async code blocks the entire event loop
**Why it happens:** sqlite3 operations are synchronous and hold the GIL
**How to avoid:**
  - Always use aiosqlite, never sqlite3 directly
  - Use `await` for all database operations
**Warning signs:** API becomes unresponsive during database operations

### Pitfall 3: Forgetting to Close Connections

**What goes wrong:** Connection objects are garbage collected without proper cleanup, causing ResourceWarning
**Why it happens:** aiosqlite v0.22.0+ no longer inherits from Thread; connections must be explicitly closed
**How to avoid:**
  - Use `async with` context manager
  - Or explicitly call `await connection.close()` in cleanup
  - Implement proper lifecycle in repository class
**Warning signs:** ResourceWarning in logs, connection exhaustion over time

### Pitfall 4: Timezone Confusion

**What goes wrong:** Timestamps saved in local time cause issues when server timezone differs from expected
**Why it happens:** `datetime.now()` uses local time; different machines may have different timezones
**How to avoid:**
  - Always use `datetime.utcnow()` for created_at, started_at, completed_at
  - Store as ISO 8601 strings (include 'Z' or offset if needed)
  - Document that all timestamps are UTC
**Warning signs:** Timestamps appear off by hours, inconsistent ordering

### Pitfall 5: Not Initializing Schema Before Use

**What goes wrong:** First database operation fails with "no such table: jobs"
**Why it happens:** Schema creation skipped or happens after first query attempt
**How to avoid:**
  - Call `initialize_schema()` in repository's `connect()` method
  - Use `IF NOT EXISTS` for idempotent schema creation
**Warning signs:** "no such table" errors on fresh database

## Code Examples

Verified patterns from official sources:

### Complete Job Model with Validation
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
import uuid

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class Job(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra='forbid',
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.QUEUED
    audio_path: str
    model_size: str = "base"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_text: Optional[str] = None
    detected_language: Optional[str] = None
    error_message: Optional[str] = None

    @field_validator('model_size')
    @classmethod
    def validate_model_size(cls, v: str) -> str:
        valid = {'tiny', 'base', 'small', 'medium', 'large'}
        if v not in valid:
            raise ValueError(f'model_size must be one of {valid}')
        return v
```

### aiosqlite Connection with Context Manager
```python
# Source: https://aiosqlite.omnilib.dev/en/stable/api.html
import aiosqlite

async def example_usage():
    async with aiosqlite.connect("jobs.db") as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout=5000;")

        # Insert
        await db.execute(
            "INSERT INTO jobs (id, status, audio_path) VALUES (?, ?, ?)",
            ("job-123", "queued", "/path/to/audio.mp3")
        )
        await db.commit()

        # Query
        async with db.execute("SELECT * FROM jobs WHERE id = ?", ("job-123",)) as cursor:
            row = await cursor.fetchone()
            print(row)
```

### State Transition Helper
```python
from datetime import datetime

async def transition_to_processing(repo: JobRepository, job_id: str) -> Job:
    """Mark job as processing with started_at timestamp."""
    job = await repo.get(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")
    if job.status != JobStatus.QUEUED:
        raise ValueError(f"Job {job_id} is not queued, cannot start processing")

    job.status = JobStatus.PROCESSING
    job.started_at = datetime.utcnow()
    return await repo.update(job)

async def transition_to_completed(
    repo: JobRepository,
    job_id: str,
    result_text: str,
    detected_language: str
) -> Job:
    """Mark job as completed with results."""
    job = await repo.get(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")
    if job.status != JobStatus.PROCESSING:
        raise ValueError(f"Job {job_id} is not processing, cannot complete")

    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.utcnow()
    job.result_text = result_text
    job.detected_language = detected_language
    return await repo.update(job)

async def transition_to_error(
    repo: JobRepository,
    job_id: str,
    error_message: str
) -> Job:
    """Mark job as failed with error message."""
    job = await repo.get(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    job.status = JobStatus.ERROR
    job.completed_at = datetime.utcnow()
    job.error_message = error_message
    return await repo.update(job)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 models | Pydantic v2 with ConfigDict | 2023 | v2 is 5-50x faster, uses ConfigDict instead of inner Config class |
| sqlite3 sync | aiosqlite async | 2019+ | Required for async FastAPI; non-blocking database access |
| String status constants | str Enum | Python 3.4+ | Type safety, IDE support, prevents typos |
| Auto-increment IDs | UUIDs | Modern practice | Better for distributed systems, no enumeration attacks |

**Deprecated/outdated:**
- **Pydantic v1 Config class**: Use `model_config = ConfigDict(...)` instead
- **aiosqlite Connection inheriting Thread**: As of v0.22.0, connections must be explicitly closed
- **`datetime.utcnow()` deprecation**: Python 3.12+ prefers `datetime.now(timezone.utc)` but utcnow still works

## Open Questions

Things that couldn't be fully resolved:

1. **Result text storage approach**
   - What we know: Small results fit in TEXT column; large transcripts may be 100KB+
   - What's unclear: Performance impact of large TEXT fields vs. file reference
   - Recommendation: Store result_text directly for simplicity; optimize later if needed

2. **Database file location**
   - What we know: Should be in user data directory, not source directory
   - What's unclear: Best cross-platform path (XDG on Linux, ~/Library on macOS)
   - Recommendation: Use `~/.local/share/cesar/jobs.db` initially; make configurable via env var

3. **Connection lifecycle for testing**
   - What we know: Production uses long-lived connection; tests need isolation
   - What's unclear: Best pattern for test database setup/teardown
   - Recommendation: Use in-memory database (`:memory:`) for tests; fixture creates fresh repo per test

## Sources

### Primary (HIGH confidence)
- [Pydantic v2 Models](https://docs.pydantic.dev/latest/concepts/models/) - Model definition, ConfigDict, validation
- [aiosqlite API Reference](https://aiosqlite.omnilib.dev/en/stable/api.html) - Connection management, cursor operations
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite) - v0.22.0 breaking changes, lifecycle

### Secondary (MEDIUM confidence)
- [SQLite WAL Mode](https://sqlite.org/wal.html) - Concurrent access patterns, checkpoint behavior
- [SQLite PRAGMA documentation](https://www.sqlite.org/pragma.html) - busy_timeout, journal_mode configuration
- [litequeue GitHub](https://github.com/litements/litequeue) - Schema design patterns for job queues
- [Simon Willison: Enabling WAL Mode](https://til.simonwillison.net/sqlite/enabling-wal-mode) - WAL best practices

### Tertiary (LOW confidence)
- [12 Pydantic v2 Model Patterns](https://medium.com/@ThinkingLoop/12-pydantic-v2-model-patterns-youll-reuse-forever-543426b3c003) - Community patterns (verify against official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - aiosqlite and Pydantic are well-documented, verified against official sources
- Architecture: HIGH - Repository pattern is standard; patterns verified against official docs
- Pitfalls: HIGH - SQLite concurrency issues well-documented; aiosqlite changelog confirms v0.22.0 changes

**Research date:** 2026-01-23
**Valid until:** 60 days (stable libraries, infrequent breaking changes)
