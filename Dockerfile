# syntax=docker/dockerfile:1

# Kamal 2 optimized Dockerfile for Cesar Transcription Service

# Build arguments for metadata
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_DATE=unknown

# Base image
FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# Production stage
FROM base AS production

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cesar/ ./cesar/
COPY README.md DEPLOY.md ./

# Install the package
RUN pip install -e .

# Pre-download Whisper models (base and tiny for faster startup)
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu')" && \
    python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu')"

# Create directories for data
RUN mkdir -p /app/data /app/.cache

# Set build metadata
ARG GIT_COMMIT
ARG GIT_BRANCH
ARG BUILD_DATE
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}
ENV BUILD_DATE=${BUILD_DATE}

# Environment for runtime
ENV CESAR_HOST=0.0.0.0
ENV CESAR_PORT=8000
ENV CESAR_DB_PATH=/app/data/jobs.db
ENV WEB_DIR=/app/cesar/web

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "-m", "uvicorn", "cesar.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
