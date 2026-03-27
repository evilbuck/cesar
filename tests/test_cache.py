"""
Unit tests for content-addressable cache module.

Tests the ContentAddressableCache class, CacheEntry dataclass, CacheError
exception, and all cache operations including YouTube URL handling.
"""

import hashlib
import os
import shutil
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path

from cesar.cache import (
    CacheEntry,
    CacheError,
    ContentAddressableCache,
    ensure_dir,
    get_default_cache_dir,
)


# === Test Fixtures ===


def get_sample_hash(data: bytes) -> str:
    """Compute SHA-256 hash of sample data."""
    return hashlib.sha256(data).hexdigest()


class TestCacheEntry(unittest.TestCase):
    """Tests for CacheEntry dataclass."""

    def test_creation_with_all_fields(self):
        """CacheEntry can be created with all fields."""
        now = datetime.now()
        path = Path("/tmp/test")

        entry = CacheEntry(
            key="test-key",
            path=path,
            content_hash="abc123",
            created_at=now,
            source_url="https://youtube.com/watch?v=test",
            metadata={"size": 100},
        )

        self.assertEqual(entry.key, "test-key")
        self.assertEqual(entry.path, path)
        self.assertEqual(entry.content_hash, "abc123")
        self.assertEqual(entry.created_at, now)
        self.assertEqual(entry.source_url, "https://youtube.com/watch?v=test")
        self.assertEqual(entry.metadata, {"size": 100})

    def test_creation_with_defaults(self):
        """CacheEntry can be created with default metadata."""
        path = Path("/tmp/test")

        entry = CacheEntry(
            key="test-key",
            path=path,
            content_hash="abc123",
            created_at=datetime.now(),
        )

        self.assertIsNone(entry.source_url)
        self.assertEqual(entry.metadata, {})

    def test_frozen_immutability(self):
        """CacheEntry is frozen (immutable)."""
        now = datetime.now()
        path = Path("/tmp/test")

        entry = CacheEntry(
            key="test-key",
            path=path,
            content_hash="abc123",
            created_at=now,
        )

        # Attempting to modify should raise FrozenInstanceError
        with self.assertRaises(Exception):  # dataclasses.FrozenInstanceError
            entry.key = "new-key"


class TestHelperFunctions(unittest.TestCase):
    """Tests for helper functions."""

    def test_get_default_cache_dir(self):
        """get_default_cache_dir returns XDG-compliant path."""
        cache_dir = get_default_cache_dir()

        self.assertTrue(cache_dir.is_absolute())
        self.assertEqual(cache_dir.name, "cesar")
        self.assertTrue(str(cache_dir).endswith(".cache/cesar"))

    def test_ensure_dir(self):
        """ensure_dir creates directory and parents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "nested" / "path" / "dir"

            ensure_dir(test_path)

            self.assertTrue(test_path.exists())
            self.assertTrue(test_path.is_dir())


class TestContentAddressableCacheInit(unittest.TestCase):
    """Tests for ContentAddressableCache initialization."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_cache_dir_creation(self):
        """ContentAddressableCache creates default cache directory."""
        temp_dir = tempfile.mkdtemp()
        try:
            cache = ContentAddressableCache(cache_dir=Path(temp_dir))
            self.assertTrue(cache.get_cache_dir().exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_custom_cache_directory(self):
        """ContentAddressableCache accepts custom directory."""
        self.assertEqual(self.cache.get_cache_dir(), Path(self.temp_dir))

    def test_directory_structure(self):
        """Cache creates objects/ and metadata/ subdirectories."""
        cache_dir = self.cache.get_cache_dir()

        self.assertTrue((cache_dir / "objects").exists())
        self.assertTrue((cache_dir / "metadata").exists())


class TestBasicOperations(unittest.TestCase):
    """Tests for basic cache put/get operations."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))
        self.sample_data = b"hello world"
        self.sample_hash = get_sample_hash(self.sample_data)

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_put_and_get(self):
        """put() stores data and get() retrieves it."""
        entry = self.cache.put("test-key", self.sample_data)

        self.assertEqual(entry.key, "test-key")
        self.assertEqual(entry.content_hash, self.sample_hash)
        self.assertTrue(entry.path.exists())

        retrieved = self.cache.get("test-key")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.key, "test-key")
        self.assertEqual(retrieved.content_hash, self.sample_hash)

        # Verify content matches
        with open(retrieved.path, "rb") as f:
            self.assertEqual(f.read(), self.sample_data)

    def test_exists_true(self):
        """exists() returns True for existing keys."""
        self.cache.put("test-key", self.sample_data)
        self.assertTrue(self.cache.exists("test-key"))

    def test_exists_false(self):
        """exists() returns False for missing keys."""
        self.assertFalse(self.cache.exists("nonexistent"))

    def test_get_nonexistent(self):
        """get() returns None for missing keys."""
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)

    def test_put_overwrite(self):
        """put() with same key updates content."""
        entry1 = self.cache.put("test-key", b"original")
        entry2 = self.cache.put("test-key", b"updated")

        self.assertEqual(entry1.content_hash, get_sample_hash(b"original"))
        self.assertEqual(entry2.content_hash, get_sample_hash(b"updated"))

        # Should retrieve updated content
        retrieved = self.cache.get("test-key")
        with open(retrieved.path, "rb") as f:
            self.assertEqual(f.read(), b"updated")


class TestAtomicWrite(unittest.TestCase):
    """Tests for atomic write operations."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_atomic_write_no_partial_files(self):
        """Verify no partial files remain after simulated crash."""
        # Write a large amount of data
        large_data = b"x" * 1024 * 1024  # 1MB

        entry = self.cache.put("large-key", large_data)

        # Check that the object file exists and is complete
        self.assertTrue(entry.path.exists())
        with open(entry.path, "rb") as f:
            self.assertEqual(f.read(), large_data)

        # Check no temp files remain
        for root, dirs, files in os.walk(self.temp_dir):
            for fname in files:
                self.assertFalse(fname.startswith(".object_"))
                self.assertFalse(fname.startswith(".metadata_"))

    def test_concurrent_writes(self):
        """Multiple threads writing same key should be safe."""
        key = "concurrent-key"
        results = []
        errors = []

        def write_data(data: bytes):
            try:
                entry = self.cache.put(key, data)
                results.append(entry)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=write_data, args=(f"data-{i}".encode(),))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All writes should succeed
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 5)


class TestHashBasedStorage(unittest.TestCase):
    """Tests for hash-based content addressing."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_content_hash_correct(self):
        """SHA-256 hash is computed correctly."""
        data = b"hello world"
        expected_hash = hashlib.sha256(data).hexdigest()

        entry = self.cache.put("key", data)
        self.assertEqual(entry.content_hash, expected_hash)

    def test_same_content_same_key(self):
        """Same data produces same content hash (deduplication)."""
        data = b"same content"

        entry1 = self.cache.put("key1", data)
        entry2 = self.cache.put("key2", data)

        self.assertEqual(entry1.content_hash, entry2.content_hash)

    def test_different_content_different_key(self):
        """Different data produces different content hashes."""
        entry1 = self.cache.put("key1", b"content A")
        entry2 = self.cache.put("key2", b"content B")

        self.assertNotEqual(entry1.content_hash, entry2.content_hash)

    def test_directory_sharding(self):
        """Content is stored with 2-char directory sharding."""
        data = b"test data for sharding"
        entry = self.cache.put("shard-key", data)

        # Object should be in objects/<first2chars>/<rest>
        first_two = entry.content_hash[:2]
        expected_path = (
            self.cache.get_cache_dir() / "objects" / first_two / entry.content_hash[2:]
        )

        self.assertEqual(entry.path, expected_path)


class TestDeletion(unittest.TestCase):
    """Tests for cache deletion operations."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_delete_existing(self):
        """delete() removes existing entry and returns True."""
        self.cache.put("test-key", b"data")
        self.assertTrue(self.cache.exists("test-key"))

        result = self.cache.delete("test-key")

        self.assertTrue(result)
        self.assertFalse(self.cache.exists("test-key"))

    def test_delete_nonexistent(self):
        """delete() returns False for missing key."""
        result = self.cache.delete("nonexistent")
        self.assertFalse(result)

    def test_clear_all(self):
        """clear() removes all entries."""
        self.cache.put("key1", b"data1")
        self.cache.put("key2", b"data2")
        self.cache.put("key3", b"data3")

        self.assertEqual(len(self.cache.list_entries()), 3)

        count = self.cache.clear()

        self.assertEqual(count, 3)
        self.assertEqual(len(self.cache.list_entries()), 0)


class TestMetadata(unittest.TestCase):
    """Tests for cache entry metadata."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_entry_metadata(self):
        """Entry contains correct metadata fields."""
        entry = self.cache.put(
            "test-key",
            b"data",
            source_url="https://example.com",
            metadata={"format": "m4a"},
        )

        self.assertIsNotNone(entry.created_at)
        self.assertEqual(entry.source_url, "https://example.com")
        self.assertEqual(entry.metadata, {"format": "m4a"})

    def test_custom_metadata(self):
        """Custom metadata is stored and retrieved correctly."""
        custom_metadata = {
            "size": 12345,
            "duration": 120.5,
            "format": "m4a",
            "nested": {"key": "value"},
        }

        entry = self.cache.put(
            "test-key",
            b"data",
            metadata=custom_metadata,
        )

        retrieved = self.cache.get("test-key")
        self.assertEqual(retrieved.metadata, custom_metadata)


class TestYouTubeSpecific(unittest.TestCase):
    """Tests for YouTube-specific cache methods."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_youtube_key_normalization(self):
        """get_youtube_key normalizes YouTube URLs consistently."""
        url1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        url2 = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        url3 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=ignored"

        key1 = ContentAddressableCache.get_youtube_key(url1)
        key2 = ContentAddressableCache.get_youtube_key(url2)
        key3 = ContentAddressableCache.get_youtube_key(url3)

        # Keys should be normalized (same base, sorted params)
        self.assertIn("dqw4w9wgxcq", key1)  # lowercase after normalization
        self.assertEqual(key1, key2)

    def test_get_youtube_key_removes_www(self):
        """get_youtube_key strips www prefix."""
        url_with_www = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        url_without_www = "https://youtube.com/watch?v=dQw4w9WgXcQ"

        key_with_www = ContentAddressableCache.get_youtube_key(url_with_www)
        key_without_www = ContentAddressableCache.get_youtube_key(url_without_www)

        self.assertEqual(key_with_www, key_without_www)

    def test_put_youtube_download(self):
        """put_youtube_download stores download with URL key."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        audio_data = b"fake audio data"

        entry = self.cache.put_youtube_download(url, audio_data)

        self.assertEqual(entry.source_url, url)
        self.assertIn("dqw4w9wgxcq", entry.key)  # lowercase after normalization
        self.assertTrue(entry.path.exists())

    def test_get_by_url(self):
        """get_by_url retrieves cached YouTube download."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        audio_data = b"fake audio data"

        # Store via put_youtube_download
        self.cache.put_youtube_download(url, audio_data)

        # Retrieve via get_by_url
        entry = self.cache.get_by_url(url)

        self.assertIsNotNone(entry)
        self.assertEqual(entry.source_url, url)
        self.assertTrue(entry.path.exists())

    def test_youtube_url_variants(self):
        """Different URL formats produce same cache key."""
        variants = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        ]

        keys = [ContentAddressableCache.get_youtube_key(v) for v in variants]

        # All keys should be the same after normalization
        self.assertEqual(len(set(keys)), 1)

    def test_youtube_key_strips_query_params(self):
        """YouTube key excludes non-video query parameters."""
        url_with_extra = "https://youtube.com/watch?v=dQw4w9WgXcQ&list=playlist&index=1"
        url_basic = "https://youtube.com/watch?v=dQw4w9WgXcQ"

        key_with_extra = ContentAddressableCache.get_youtube_key(url_with_extra)
        key_basic = ContentAddressableCache.get_youtube_key(url_basic)

        # Only v parameter should matter
        self.assertEqual(key_with_extra, key_basic)


class TestSizeCalculation(unittest.TestCase):
    """Tests for cache size calculation."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_size_empty(self):
        """get_size() returns 0 for empty cache."""
        self.assertEqual(self.cache.get_size(), 0)

    def test_get_size_with_entries(self):
        """get_size() returns correct total size."""
        self.cache.put("key1", b"x" * 100)
        self.cache.put("key2", b"y" * 200)

        size = self.cache.get_size()

        self.assertEqual(size, 300)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error conditions."""

    def setUp(self):
        """Set up temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = ContentAddressableCache(cache_dir=Path(self.temp_dir))

    def tearDown(self):
        """Clean up temporary cache."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_data(self):
        """Cache can store empty byte string."""
        entry = self.cache.put("empty", b"")

        self.assertTrue(entry.path.exists())
        self.assertEqual(entry.path.stat().st_size, 0)

        retrieved = self.cache.get("empty")
        with open(retrieved.path, "rb") as f:
            self.assertEqual(f.read(), b"")

    def test_large_data(self):
        """Cache can store large files (10MB+)."""
        large_data = b"x" * (10 * 1024 * 1024)  # 10MB

        entry = self.cache.put("large", large_data)

        self.assertEqual(entry.path.stat().st_size, 10 * 1024 * 1024)

        retrieved = self.cache.get("large")
        with open(retrieved.path, "rb") as f:
            self.assertEqual(f.read(), large_data)

    def test_special_characters_in_key(self):
        """Keys with special characters are handled correctly."""
        special_keys = [
            "key/with/slashes",
            "key.with.dots",
            "key-with-dashes",
            "key_with_underscores",
            "key with spaces",
        ]

        for key in special_keys:
            entry = self.cache.put(key, f"data for {key}".encode())
            self.assertTrue(entry.path.exists())

            retrieved = self.cache.get(key)
            self.assertIsNotNone(retrieved)

    def test_unicode_content(self):
        """Unicode data in metadata is handled correctly."""
        unicode_metadata = {
            "title": "Test Video - 日本語",
            "description": "A test with émojis 🎉 and unicode: 你好",
        }

        entry = self.cache.put(
            "unicode-key",
            b"data",
            metadata=unicode_metadata,
        )

        retrieved = self.cache.get("unicode-key")
        self.assertEqual(retrieved.metadata, unicode_metadata)


class TestCacheError(unittest.TestCase):
    """Tests for CacheError exception."""

    def test_cache_error_creation(self):
        """CacheError can be created with message."""
        error = CacheError("Test error message")
        self.assertEqual(str(error), "Test error message")
        self.assertIsNone(error.http_status)

    def test_cache_error_with_status(self):
        """CacheError can include HTTP status code."""
        error = CacheError("Not found", http_status=404)
        self.assertEqual(str(error), "Not found")
        self.assertEqual(error.http_status, 404)

    def test_cache_error_inheritance(self):
        """CacheError inherits from Exception."""
        error = CacheError("test")
        self.assertIsInstance(error, Exception)


if __name__ == "__main__":
    unittest.main()
