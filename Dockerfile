FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cesar/ ./cesar/
COPY README.md ./

# Install the package
RUN pip install -e .

# Create directories for data
RUN mkdir -p /app/data /app/.cache

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV CESAR_HOST=0.0.0.0
ENV CESAR_PORT=8000
ENV WEB_DIR=/app/cesar/web
ENV HOME=/app

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "-m", "uvicorn", "cesar.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
