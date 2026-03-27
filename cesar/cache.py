"""
Content-addressable cache module for Cesar transcription tool.

Provides atomic, crash-safe caching of intermediate artifacts (starting with
YouTube downloads) using SHA-256 content addressing and XDG-compliant storage.

The cache enables resumable, idempotent transcription pipelines where
identical inputs skip reprocessing.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# === Helper Functions ===


def get_default_cache_dir() -> Path:
    """Get the default cache directory (XDG-compliant).

    Returns:
        Path: ~/.cache/cesar/
    """
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        base = Path(xdg_cache)
    else:
        base = Path.home() / ".cache"
    return base / "cesar"


def ensure_dir(path: Path) -> None:
    """Create directory and parents if needed.

    Args:
        path: Directory path to create
    """
    path.mkdir(parents=True, exist_ok=True)


# === Exception Classes ===


class CacheError(Exception):
    """Base exception for cache-specific errors.

    Attributes:
        http_status: Optional HTTP status code for API compatibility
    """

    def __init__(self, message: str, http_status: Optional[int] = None) -> None:
        """Initialize CacheError.

        Args:
            message: Error message
            http_status: Optional HTTP status code for API compatibility
        """
        super().__init__(message)
        self.http_status = http_status


# === Cache Entry Dataclass ===


@dataclass(frozen=True)
class CacheEntry:
    """Represents a single cached item.

    Attributes:
        key: The cache key (content hash or URL-based key)
        path: Path to the cached file on disk
        content_hash: SHA-256 hash of the cached content
        created_at: When the entry was created
        source_url: Original URL for YouTube downloads (if applicable)
        metadata: Additional metadata about the cached item
    """

    key: str
    path: Path
    content_hash: str
    created_at: datetime
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# === Content Addressable Cache ===


class ContentAddressableCache:
    """Content-addressable cache with atomic writes and XDG-compliant storage.

    Uses SHA-256 content hashing to address cached content, with URL-based
    lookup for YouTube downloads. Implements atomic write-to-temp-then-rename
    pattern to survive application crashes.

    Directory structure:
        cache_dir/
            objects/       # Content files, sharded by first 2 chars of hash
                ab/
                    abcdef...
            metadata/      # JSON files with CacheEntry info
                ab/
                    abcdef...json

    Example:
        >>> cache = ContentAddressableCache()
        >>> entry = cache.put('my-key', b'hello world')
        >>> retrieved = cache.get('my-key')
        >>> print(retrieved.path)  # Path to cached file
    """

    OBJECTS_DIR = "objects"
    METADATA_DIR = "metadata"

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """Initialize the content-addressable cache.

        Args:
            cache_dir: Custom cache directory path. If None, uses XDG default
                      (~/.cache/cesar/)
        """
        if cache_dir is None:
            self._cache_dir = get_default_cache_dir()
        else:
            self._cache_dir = cache_dir

        # Create cache directory structure
        self._objects_dir = self._cache_dir / self.OBJECTS_DIR
        self._metadata_dir = self._cache_dir / self.METADATA_DIR

        ensure_dir(self._objects_dir)
        ensure_dir(self._metadata_dir)

    def get_cache_dir(self) -> Path:
        """Return the cache directory path.

        Returns:
            Path to the cache directory
        """
        return self._cache_dir

    def _compute_hash(self, data: bytes) -> str:
        """Compute SHA-256 hash of data.

        Args:
            data: Bytes to hash

        Returns:
            Hex-encoded SHA-256 hash string
        """
        return hashlib.sha256(data).hexdigest()

    def _get_object_path(self, content_hash: str) -> Path:
        """Get the object path for a content hash.

        Uses first 2 characters as a subdirectory sharding mechanism
        to avoid too many files in one directory.

        Args:
            content_hash: SHA-256 hash string

        Returns:
            Path to the object file
        """
        shard = content_hash[:2]
        shard_dir = self._objects_dir / shard
        ensure_dir(shard_dir)
        return shard_dir / content_hash[2:]

    def _get_metadata_path(self, key: str) -> Path:
        """Get the metadata path for a cache key.

        Uses a hash of the key to create a safe shard directory,
        avoiding issues with special characters in keys.

        Args:
            key: Cache key

        Returns:
            Path to the metadata JSON file
        """
        # Use hash to create safe shard directory (avoids issues with / in keys)
        key_hash = self._compute_hash(key.encode())[:16]
        shard = key_hash[:2]
        shard_dir = self._metadata_dir / shard
        ensure_dir(shard_dir)
        return shard_dir / f"{key_hash}.json"

    def _write_metadata(self, entry: CacheEntry) -> None:
        """Write metadata JSON file for a cache entry.

        Args:
            entry: CacheEntry to persist
        """
        metadata_path = self._get_metadata_path(entry.key)
        metadata_data = {
            "key": entry.key,
            "path": str(entry.path),
            "content_hash": entry.content_hash,
            "created_at": entry.created_at.isoformat(),
            "source_url": entry.source_url,
            "metadata": entry.metadata,
        }
        # Write atomically
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=metadata_path.parent, prefix=".metadata_", suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(metadata_data, f)
            os.replace(tmp_path, metadata_path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _read_metadata(self, key: str) -> Optional[CacheEntry]:
        """Read metadata JSON file for a cache key.

        Args:
            key: Cache key

        Returns:
            CacheEntry if metadata exists, None otherwise
        """
        metadata_path = self._get_metadata_path(key)
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r") as f:
                data = json.load(f)

            return CacheEntry(
                key=data["key"],
                path=Path(data["path"]),
                content_hash=data["content_hash"],
                created_at=datetime.fromisoformat(data["created_at"]),
                source_url=data.get("source_url"),
                metadata=data.get("metadata", {}),
            )
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Failed to read metadata for key {key}: {e}")
            return None

    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        return self._get_metadata_path(key).exists()

    def get(self, key: str) -> Optional[CacheEntry]:
        """Retrieve a cache entry by key.

        Args:
            key: Cache key

        Returns:
            CacheEntry if found, None otherwise
        """
        return self._read_metadata(key)

    def put(
        self,
        key: str,
        data: bytes,
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CacheEntry:
        """Store data in the cache with the given key.

        Uses atomic write: writes to a temp file in the same directory,
        then renames to the final path. This ensures no partial files
        exist even if the process crashes.

        Args:
            key: Cache key (e.g., content hash or URL-based key)
            data: Bytes content to cache
            source_url: Original URL for YouTube downloads
            metadata: Additional metadata to store

        Returns:
            CacheEntry with the stored content info

        Raises:
            CacheError: If write fails (e.g., disk full)
        """
        content_hash = self._compute_hash(data)
        object_path = self._get_object_path(content_hash)

        # Atomic write: temp file in same directory, then rename
        tmp_fd = None
        tmp_path = None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=object_path.parent, prefix=".object_", suffix=".tmp"
            )
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            tmp_fd = None  # fd is now closed

            # Atomic rename (on POSIX this is atomic within same filesystem)
            os.replace(tmp_path, object_path)
            tmp_path = None  # Successfully renamed

        except OSError as e:
            # Clean up temp file on failure
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise CacheError(f"Failed to write to cache: {e}")

        # Create and persist entry metadata
        entry = CacheEntry(
            key=key,
            path=object_path,
            content_hash=content_hash,
            created_at=datetime.now(),
            source_url=source_url,
            metadata=metadata or {},
        )

        try:
            self._write_metadata(entry)
        except Exception as e:
            # Clean up object file if metadata write fails
            try:
                os.unlink(object_path)
            except OSError:
                pass
            raise CacheError(f"Failed to write metadata: {e}")

        return entry

    def delete(self, key: str) -> bool:
        """Remove an entry from the cache.

        Args:
            key: Cache key to remove

        Returns:
            True if entry existed and was removed, False if not found
        """
        entry = self._read_metadata(key)
        if entry is None:
            return False

        # Remove object file
        try:
            if entry.path.exists():
                os.unlink(entry.path)
        except OSError as e:
            logger.warning(f"Failed to delete object file {entry.path}: {e}")

        # Remove metadata file
        metadata_path = self._get_metadata_path(key)
        try:
            if metadata_path.exists():
                os.unlink(metadata_path)
        except OSError as e:
            logger.warning(f"Failed to delete metadata {metadata_path}: {e}")

        return True

    def clear(self) -> int:
        """Remove all entries from the cache.

        Returns:
            Number of entries removed
        """
        count = 0
        for metadata_file in self._metadata_dir.rglob("*.json"):
            try:
                # Read key from metadata file
                with open(metadata_file, "r") as f:
                    data = json.load(f)
                key = data.get("key")
                if key and self.delete(key):
                    count += 1
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        return count

    def list_entries(self) -> List[CacheEntry]:
        """List all cache entries.

        Returns:
            List of all CacheEntry objects in the cache
        """
        entries = []
        for metadata_file in self._metadata_dir.rglob("*.json"):
            try:
                with open(metadata_file, "r") as f:
                    data = json.load(f)

                entry = CacheEntry(
                    key=data["key"],
                    path=Path(data["path"]),
                    content_hash=data["content_hash"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    source_url=data.get("source_url"),
                    metadata=data.get("metadata", {}),
                )
                entries.append(entry)
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        return entries

    def get_size(self) -> int:
        """Get total cache size in bytes.

        Returns:
            Total size of all cached objects in bytes
        """
        total = 0
        for obj_file in self._objects_dir.rglob("*"):
            if obj_file.is_file():
                try:
                    total += obj_file.stat().st_size
                except OSError:
                    pass
        return total

    # === YouTube-Specific Methods ===

    @staticmethod
    def get_youtube_key(url: str) -> str:
        """Generate a normalized cache key from a YouTube URL.

        Normalizes the URL by:
        - Stripping whitespace
        - Lowercasing
        - Removing www prefix
        - Converting youtu.be URLs to watch format
        - Converting shorts URLs to watch format
        - Extracting only the video ID (v parameter)

        Args:
            url: YouTube URL string

        Returns:
            Normalized key string (video ID only) suitable for cache lookup
        """
        url = url.strip().lower()

        # Remove www prefix
        url = url.replace("://www.", "://")

        # Convert youtu.be/ID format to youtube.com/watch?v=ID
        match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
        if match:
            video_id = match.group(1)
            url = f"https://youtube.com/watch?v={video_id}"

        # Convert /shorts/ID format to /watch?v=ID
        match = re.search(r"/shorts/([a-zA-Z0-9_-]{11})", url)
        if match:
            video_id = match.group(1)
            url = f"https://youtube.com/watch?v={video_id}"

        # Parse and extract just the v parameter (ignore all others)
        if "?" in url:
            base, query = url.split("?", 1)
            video_id = None
            for param in query.split("&"):
                if param.startswith("v="):
                    video_id = param[2:]
                    break
                elif "=" in param:
                    k, v = param.split("=", 1)
                    if k == "v":
                        video_id = v
                        break
            if video_id:
                return f"https://youtube.com/watch?v={video_id}"

        return url

    def get_by_url(self, url: str) -> Optional[CacheEntry]:
        """Look up a cached YouTube download by URL.

        Args:
            url: YouTube URL

        Returns:
            CacheEntry if found, None otherwise
        """
        key = self.get_youtube_key(url)
        return self.get(key)

    def put_youtube_download(
        self,
        url: str,
        data: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CacheEntry:
        """Store a YouTube audio download.

        Uses URL-based key for lookup, but stores content with
        hash-based addressing.

        Args:
            url: YouTube URL
            data: Downloaded audio bytes
            metadata: Additional metadata (file_size, format, etc.)

        Returns:
            CacheEntry for the stored download
        """
        key = self.get_youtube_key(url)

        # Merge metadata
        merged_metadata = metadata.copy() if metadata else {}
        merged_metadata["url"] = url
        merged_metadata["cached_at"] = datetime.now().isoformat()

        return self.put(key, data, source_url=url, metadata=merged_metadata)
