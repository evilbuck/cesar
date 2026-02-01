"""
SQLite database schema and initialization for transcription jobs.

Provides the database schema and initialization functions for the
async job repository.
"""
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


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
    error_message TEXT,
    download_progress INTEGER CHECK(download_progress >= 0 AND download_progress <= 100)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
"""


async def initialize_schema(connection: "aiosqlite.Connection") -> None:
    """Create tables if they don't exist.

    Args:
        connection: Active aiosqlite connection

    Idempotent - safe to call multiple times.
    """
    await connection.executescript(SCHEMA)
    await connection.commit()


def get_default_db_path() -> Path:
    """Get the default database file path.

    Returns:
        Path to ~/.local/share/cesar/jobs.db

    Creates parent directory if it doesn't exist.
    """
    db_dir = Path.home() / ".local" / "share" / "cesar"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "jobs.db"
