"""
Simplified FastAPI server for Vercel deployment.
Serves the web frontend only - no actual transcription.
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse

# Web frontend directory
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Cesar - Audio Transcription")


@app.get("/")
async def serve_frontend():
    """Serve the web frontend."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "message": "Cesar transcription service"}
