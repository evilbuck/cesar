"""
Cesar: Offline audio transcription CLI using faster-whisper
"""
try:
    from importlib.metadata import version
    __version__ = version("cesar")
except Exception:
    __version__ = "0.0.0"  # Development fallback
