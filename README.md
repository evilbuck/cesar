# Cesar - Offline Audio Transcriber

A command-line tool for transcribing audio files to text using OpenAI's Whisper technology via the faster-whisper library. Designed for completely offline operation after initial setup.

## Features

- **Offline Operation**: Works without internet connection after initial model download
- **High Performance**: 4x faster than standard Whisper using faster-whisper
- **Parallel Processing**: Automatic chunking and parallel transcription for long files (>30 minutes)
- **GPU Acceleration**: Automatic Metal Performance Shaders (MPS) on macOS Sequoia+
- **Memory Efficient**: Handles large audio files using streaming segments
- **Multiple Formats**: Supports mp3, wav, m4a, ogg, flac, aac, wma
- **Two Interfaces**: CLI for direct use, HTTP API for integration
- **Async Job Queue**: Persistent job queue with crash recovery for API server
- **Simple Interface**: Single command execution with clear progress feedback
- **Configurable Threading**: Auto-detect CPU cores or manual thread specification

## Installation

1. **Install system dependencies:**
   ```bash
   # macOS (using Homebrew)
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   ```

2. **Install cesar:**
   ```bash
   # From git repository
   pipx install git+https://github.com/yourusername/cesar.git

   # Or from local clone
   git clone https://github.com/yourusername/cesar.git
   cd cesar
   pipx install .
   ```

3. **Verify installation:**
   ```bash
   cesar --version
   cesar --help
   ```

## Usage

### Basic Usage
```bash
cesar transcribe input.mp3 -o output.txt
```

### With Custom Model Size
```bash
cesar transcribe input.wav -o transcript.txt --model small
```

### Available Options

Run `cesar transcribe --help` to see all options:

- `INPUT_FILE`: Path to the audio file to transcribe (required)
- `-o, --output`: Path for the output text file (required)
- `--model`: Whisper model size - tiny, base, small, medium, large (default: base)
- `--device`: Force specific device - auto, cpu, cuda, mps (default: auto)
- `--compute-type`: Force compute type - auto, float32, float16, int8 (default: auto)
- `-v, --verbose`: Show detailed system information
- `-q, --quiet`: Suppress progress display

## Model Sizes

| Model  | Size  | Speed | Accuracy |
|--------|-------|-------|----------|
| tiny   | 39MB  | Fastest | Lowest |  
| base   | 74MB  | Fast    | Good   |
| small  | 244MB | Medium  | Better |
| medium | 769MB | Slow    | High   |
| large  | 1550MB| Slowest | Highest|

## Examples

```bash
# Basic transcription
cesar transcribe meeting.mp3 -o meeting_transcript.txt

# High accuracy transcription
cesar transcribe interview.wav -o interview.txt --model large

# Quick transcription
cesar transcribe note.m4a -o note.txt --model tiny

# Verbose output with system info
cesar transcribe podcast.mp3 -o podcast.txt --verbose

# Quiet mode (minimal output)
cesar transcribe recording.wav -o recording.txt --quiet
```

## HTTP API Server

Cesar v2.0+ includes an HTTP API server for programmatic access and integration with other services.

### Starting the Server

```bash
cesar serve
```

By default, the server listens on `http://127.0.0.1:5000`.

### Server Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port, -p` | 5000 | Port to bind to |
| `--host, -h` | 127.0.0.1 | Host to bind to (use 0.0.0.0 for external access) |
| `--reload` | off | Enable auto-reload for development |
| `--workers` | 1 | Number of uvicorn workers |

Example with custom options:
```bash
cesar serve --port 8080 --host 0.0.0.0 --workers 4
```

### API Documentation

Interactive API documentation is available at `/docs` when the server is running:
- Swagger UI: `http://localhost:5000/docs`

## API Endpoints

### Health Check

```bash
GET /health
```

Returns server health status and worker state.

```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "healthy",
  "worker": "running"
}
```

### Submit Transcription (File Upload)

```bash
POST /transcribe
```

Upload an audio file for transcription. Returns immediately with a job ID.

```bash
curl -X POST http://localhost:5000/transcribe \
  -F "file=@recording.mp3" \
  -F "model=base"
```

Response (HTTP 202 Accepted):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "audio_path": "/tmp/cesar/550e8400.mp3",
  "model_size": "base",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": null,
  "completed_at": null,
  "result_text": null,
  "detected_language": null,
  "error_message": null
}
```

### Submit Transcription (URL)

```bash
POST /transcribe/url
```

Download audio from a URL and transcribe it.

```bash
curl -X POST http://localhost:5000/transcribe/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/audio.mp3", "model": "base"}'
```

### Get Job Status

```bash
GET /jobs/{job_id}
```

Retrieve the status and results of a specific job.

```bash
curl http://localhost:5000/jobs/550e8400-e29b-41d4-a716-446655440000
```

Response (completed job):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "audio_path": "/tmp/cesar/550e8400.mp3",
  "model_size": "base",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:01Z",
  "completed_at": "2024-01-15T10:31:45Z",
  "result_text": "This is the transcribed text...",
  "detected_language": "en",
  "error_message": null
}
```

### List Jobs

```bash
GET /jobs
GET /jobs?status=queued
```

List all jobs, optionally filtered by status.

```bash
# List all jobs
curl http://localhost:5000/jobs

# List only completed jobs
curl "http://localhost:5000/jobs?status=completed"
```

Valid status values: `queued`, `processing`, `completed`, `error`

## Job Queue

Transcription jobs are processed asynchronously through a persistent job queue.

### Job Lifecycle

1. **queued**: Job submitted, waiting for worker
2. **processing**: Worker is actively transcribing
3. **completed**: Transcription finished, results available
4. **error**: Transcription failed, error message available

### Persistence and Recovery

- Jobs are stored in SQLite at `~/.local/share/cesar/jobs.db`
- Jobs persist across server restarts
- Jobs left in `processing` state after a crash are automatically re-queued on startup
- Completed job results remain available until manually cleared

## Output

The tool provides progress feedback during transcription:

```
✓ Input file validated: /path/to/audio.mp3
✓ Output path validated: /path/to/output.txt
Loading Whisper model 'base'...
✓ Model loaded in 2.3s
Transcribing audio: audio.mp3
Detected language: en (probability: 0.99)
Processed 10 segments (15.2s elapsed)
✓ Transcription completed!
  Audio duration: 180.5s
  Processing time: 45.2s
  Speed ratio: 4.0x faster than real-time
  Output saved to: /path/to/output.txt
```

## System Requirements

- **Platform**: macOS or Linux (Metal GPU acceleration on macOS, CUDA on Linux)
- **Python**: 3.10 or higher
- **Memory**: Varies by model size and audio file length
- **Storage**: Model cache requires 39MB - 1.5GB depending on model

## Error Handling

The tool provides clear error messages for common issues:

- File not found or unreadable
- Unsupported audio formats
- Output directory permissions
- Missing dependencies
- Model loading failures

## Technical Details

- Uses faster-whisper's streaming segments for memory efficiency
- Automatic device selection (Metal on macOS, CUDA on supported systems, CPU fallback)
- Voice Activity Detection (VAD) to skip silence
- **Parallel Processing**: Automatic chunking for files over 30 minutes
  - Uses ffmpeg for reliable audio splitting
  - Thread pool for concurrent chunk processing
  - Chronological transcript reassembly
  - Auto-detects optimal thread count (75% of CPU cores, max 8)
- Models cached in `~/.cache/huggingface/hub/`

## Troubleshooting

**Model fails to load:**
- Ensure you have internet connection for initial model download
- Check available disk space for model cache

**Audio file not recognized:**
- Verify the file format is supported
- Check file permissions and path

**Slow performance:**
- Try a smaller model size (tiny, base, small)
- Ensure Metal GPU acceleration is available on macOS

## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

### Installing for Development

```bash
git clone https://github.com/yourusername/cesar.git
cd cesar
pip install -e .
```
