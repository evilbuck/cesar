"""
Async repository for Job persistence in SQLite.

Provides the JobRepository class for CRUD operations on transcription jobs.
"""
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

import aiosqlite

from cesar.api.database import initialize_schema
from cesar.api.models import Job, JobStatus


class JobRepository:
    """Async repository for Job persistence in SQLite.

    Encapsulates all database operations for the Job model.
    Uses aiosqlite for non-blocking async access.

    Example:
        repo = JobRepository(Path("jobs.db"))
        await repo.connect()
        job = Job(audio_path="/path/to/audio.mp3")
        await repo.create(job)
        await repo.close()
    """

    def __init__(self, db_path: Union[Path, str]):
        """Initialize repository with database path.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory DB
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open database connection with optimal settings.

        Sets PRAGMAs for WAL mode, busy timeout, foreign keys, and sync mode.
        Initializes schema if needed.
        """
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
        # Initialize schema
        await initialize_schema(self._connection)

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def create(self, job: Job) -> Job:
        """Insert new job into database.

        Args:
            job: Job model instance to persist

        Returns:
            The same job instance (now persisted)
        """
        await self._connection.execute(
            """
            INSERT INTO jobs (id, status, audio_path, model_size,
                              created_at, started_at, completed_at,
                              result_text, detected_language, error_message,
                              download_progress)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.status.value,
                job.audio_path,
                job.model_size,
                job.created_at.isoformat(),
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                job.result_text,
                job.detected_language,
                job.error_message,
                job.download_progress,
            ),
        )
        await self._connection.commit()
        return job

    async def get(self, job_id: str) -> Optional[Job]:
        """Retrieve job by ID.

        Args:
            job_id: UUID string of the job

        Returns:
            Job if found, None otherwise
        """
        async with self._connection.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_job(row)
            return None

    async def update(self, job: Job) -> Job:
        """Update existing job.

        Updates all mutable fields: status, timestamps, results, error, audio_path, download_progress.
        Note: audio_path is updated to support YouTube download flow (URL -> downloaded file path).

        Args:
            job: Job model instance with updated values

        Returns:
            The same job instance (now updated in DB)
        """
        await self._connection.execute(
            """
            UPDATE jobs SET
                status = ?, audio_path = ?, started_at = ?, completed_at = ?,
                result_text = ?, detected_language = ?, error_message = ?,
                download_progress = ?
            WHERE id = ?
            """,
            (
                job.status.value,
                job.audio_path,
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                job.result_text,
                job.detected_language,
                job.error_message,
                job.download_progress,
                job.id,
            ),
        )
        await self._connection.commit()
        return job

    async def list_all(self) -> List[Job]:
        """List all jobs ordered by creation time (newest first).

        Returns:
            List of all Job instances
        """
        async with self._connection.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_job(row) for row in rows]

    async def get_next_queued(self) -> Optional[Job]:
        """Get the next job that needs processing (QUEUED or DOWNLOADING status).

        Returns jobs in FIFO order by created_at timestamp.
        Used by the worker to pick up the next job to process.

        Returns:
            Oldest queued or downloading Job, or None if none available
        """
        async with self._connection.execute(
            "SELECT * FROM jobs WHERE status IN ('queued', 'downloading') ORDER BY created_at ASC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_job(row)
            return None

    def _row_to_job(self, row: tuple) -> Job:
        """Convert database row to Job model.

        Args:
            row: Tuple of column values from database

        Returns:
            Job model instance
        """
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
            download_progress=row[10],
        )
