# Features Research: Async Transcription API

**Domain:** Job-based async transcription HTTP API
**Researched:** 2026-01-23
**Confidence:** HIGH (multiple authoritative sources, consistent patterns)

## Executive Summary

Async job-based APIs for transcription follow well-established patterns across industry leaders (AssemblyAI, Deepgram, Azure Speech). The core pattern is simple: submit job, get ID, poll or receive webhook, fetch results. For an internal service, many features that public APIs require (auth, rate limiting, billing) can be omitted, but the job lifecycle and response patterns should follow conventions.

---

## Table Stakes

Must-have features for any async job API. Missing these means the API feels broken or unusable.

| Feature | Why Expected | Complexity | Implementation Notes |
|---------|--------------|------------|---------------------|
| **POST /transcribe** | Submit transcription job | Low | Accept audio_url or file upload |
| **GET /jobs/{id}** | Poll job status | Low | Return current status + result when done |
| **Job ID in submit response** | Client needs ID to poll | Low | Return UUID immediately with 202 Accepted |
| **Status field in response** | Know if job is pending/done/failed | Low | Enum: queued, processing, completed, error |
| **Error details on failure** | Debug why job failed | Low | Include `error` field with message |
| **Timestamps** | Track job progress | Low | `created_at`, `completed_at` |
| **Result in status response** | Don't require separate fetch | Low | Include `text` when status=completed |

### Job Submission Requirements

**Two input methods are standard:**

1. **URL reference** (simpler): `{ "audio_url": "https://..." }`
   - Client hosts file, provides URL
   - Server fetches asynchronously
   - Used by: AssemblyAI, Deepgram

2. **File upload** (more complete): `multipart/form-data`
   - Client uploads directly
   - Server stores temporarily
   - More convenient for internal service

**Recommendation for internal service:** Support BOTH. URL reference is simpler for integrations; file upload is more convenient for direct use. File upload can accept the file and immediately return 202.

### Response Schema (Table Stakes)

```json
{
  "id": "uuid",
  "status": "queued | processing | completed | error",
  "created_at": "2026-01-23T10:00:00Z",
  "completed_at": "2026-01-23T10:01:30Z",
  "text": "transcribed text here...",
  "error": "optional error message"
}
```

---

## API Patterns

Common patterns from AssemblyAI, Deepgram, and async API best practices.

### HTTP Status Code Conventions

| Scenario | Status Code | Body |
|----------|-------------|------|
| Job submitted successfully | 202 Accepted | `{ "id": "...", "status": "queued" }` |
| Job status polled, still processing | 200 OK | `{ "status": "processing" }` |
| Job status polled, completed | 200 OK | `{ "status": "completed", "text": "..." }` |
| Job not found | 404 Not Found | `{ "error": "Job not found" }` |
| Invalid request (bad file, etc) | 400 Bad Request | `{ "error": "..." }` |
| Server error | 500 Internal Server Error | `{ "error": "Internal error" }` |

**Key insight:** Failed transcriptions (bad audio, processing error) return 200 with `status: "error"` in body, NOT a 4xx/5xx. The HTTP status codes are for request handling, not job outcomes.

### Location Header Pattern

Per [Azure Async Request-Reply Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply):

```http
POST /transcribe
Content-Type: multipart/form-data

HTTP/1.1 202 Accepted
Location: /jobs/abc-123
Retry-After: 5

{"id": "abc-123", "status": "queued"}
```

**Recommendation:** Include `Location` header pointing to status endpoint. Include `Retry-After` header with suggested poll interval.

### Endpoint Structure

Standard REST patterns from [REST API Design for Long-Running Tasks](https://restfulapi.net/rest-api-design-for-long-running-tasks/):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/transcribe` | POST | Submit new job |
| `/jobs/{id}` | GET | Get job status/result |
| `/jobs/{id}` | DELETE | Cancel or delete job |
| `/jobs` | GET | List jobs (optional) |

**Note:** Some APIs use `/transcripts` (AssemblyAI) or `/listen` (Deepgram). For internal service, `/transcribe` + `/jobs` is clearer.

---

## Job Lifecycle

### State Machine

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌───────┴───┐
│  queued  │───▶│processing│───▶│ completed │    │   error   │
└──────────┘    └──────────┘    └───────────┘    └───────────┘
     │                │                                ▲
     │                │                                │
     └────────────────┴────────────────────────────────┘
           (failure at any point)
```

### State Definitions

| State | Meaning | Transitions To |
|-------|---------|----------------|
| `queued` | Job accepted, waiting for worker | `processing`, `error` |
| `processing` | Worker actively transcribing | `completed`, `error` |
| `completed` | Transcription finished successfully | (terminal) |
| `error` | Job failed | (terminal) |

**AssemblyAI uses exactly these four states.** This is the industry standard.

### Error Handling

From [AssemblyAI docs](https://www.assemblyai.com/docs/api-reference/overview):

- Errors during job processing result in `status: "error"` with 200 OK response
- Error details in `error` field: `"Audio file could not be processed"`
- Common errors: unsupported format, corrupted file, empty audio, timeout

**Recommendation:** Preserve the same error categories:
- `invalid_audio`: File format not supported or corrupted
- `processing_failed`: Transcription engine error
- `timeout`: Job took too long
- `internal_error`: Unexpected server error

### Cancellation

From [REST API Design patterns](https://restfulapi.net/rest-api-design-for-long-running-tasks/):

- `DELETE /jobs/{id}` cancels a queued/processing job
- Returns 200 OK if cancelled, 404 if not found
- Idempotent: multiple deletes have same effect
- For internal service, cancellation prevents wasted compute

---

## Webhook Conventions

Optional for internal service, but useful pattern to understand.

### Deepgram Callback Pattern

From [Deepgram Callback docs](https://developers.deepgram.com/docs/callback):

**Request:** Include `callback` parameter in submit request
```
POST /transcribe?callback=https://myserver.com/hook
```

**Callback payload:** POST to callback URL when done
```json
{
  "job_id": "abc-123",
  "status": "completed",
  "text": "..."
}
```

### AssemblyAI Webhook Pattern

From [AssemblyAI Webhooks](https://www.assemblyai.com/docs/deployment/webhooks):

**Request body includes webhook_url:**
```json
{
  "audio_url": "https://...",
  "webhook_url": "https://myserver.com/hook"
}
```

**Callback payload:** Minimal by default
```json
{
  "transcript_id": "abc-123",
  "status": "completed"
}
```

Client then fetches full result via `GET /jobs/{id}`.

### Best Practices (from Webhook guides)

| Practice | Recommendation |
|----------|----------------|
| Authentication | Include custom header (`X-Webhook-Secret`) |
| Retry logic | Retry up to 10 times with exponential backoff |
| Timeout | Expect 200 response within 10 seconds |
| Idempotency | Client should handle duplicate deliveries |
| Payload size | Keep small; client fetches full result separately |

### Recommendation for Internal Service

**Start without webhooks.** Polling is simpler and sufficient for most internal use cases. Add webhooks later if:
- Jobs take very long (>5 minutes)
- Clients can't efficiently poll
- Event-driven architecture is needed

---

## Differentiators

Nice-to-have features that improve developer experience but aren't required.

| Feature | Value Proposition | Complexity | Priority |
|---------|-------------------|------------|----------|
| **Model selection** | Let caller choose tiny/base/large | Low | High |
| **Progress percentage** | Show 0-100% during processing | Medium | Medium |
| **Word-level timestamps** | Return `words: [{word, start, end}]` | Low (faster-whisper provides) | Medium |
| **Speaker diarization** | Identify different speakers | High | Low (v3+) |
| **Language detection** | Auto-detect language | Low (faster-whisper provides) | Medium |
| **Confidence scores** | Return confidence per segment | Low | Low |
| **Multiple output formats** | Return SRT, VTT, JSON | Medium | Medium |
| **Job listing** | `GET /jobs` with pagination | Medium | Low |
| **Job metadata** | Store caller-provided metadata | Low | Medium |

### Recommended for v2.0

1. **Model selection** - Already supported in CLI, expose in API
2. **Language detection** - Free from faster-whisper
3. **Word timestamps** - Free from faster-whisper, useful for downstream
4. **Job metadata** - Pass-through field for caller context

### Defer to Later

- Speaker diarization (complex, separate library)
- Output format conversion (can be client-side)
- Job listing (YAGNI for internal service)

---

## Request/Response Schemas

### Submit Job Request

**Option A: URL reference**
```http
POST /transcribe
Content-Type: application/json

{
  "audio_url": "https://example.com/audio.mp3",
  "model": "base",
  "language": "en",
  "metadata": {"caller_id": "service-a"}
}
```

**Option B: File upload**
```http
POST /transcribe
Content-Type: multipart/form-data

file: (binary audio data)
model: base
language: en
metadata: {"caller_id": "service-a"}
```

### Submit Job Response

```http
HTTP/1.1 202 Accepted
Location: /jobs/abc-123
Retry-After: 5
Content-Type: application/json

{
  "id": "abc-123",
  "status": "queued",
  "created_at": "2026-01-23T10:00:00Z"
}
```

### Get Job Response (Processing)

```http
GET /jobs/abc-123

HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": "abc-123",
  "status": "processing",
  "created_at": "2026-01-23T10:00:00Z",
  "progress": 45
}
```

### Get Job Response (Completed)

```http
GET /jobs/abc-123

HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": "abc-123",
  "status": "completed",
  "created_at": "2026-01-23T10:00:00Z",
  "completed_at": "2026-01-23T10:01:30Z",
  "duration_seconds": 90,
  "text": "Hello, this is the transcribed text...",
  "language": "en",
  "language_confidence": 0.98,
  "words": [
    {"word": "Hello", "start": 0.0, "end": 0.5, "confidence": 0.99},
    {"word": "this", "start": 0.6, "end": 0.8, "confidence": 0.97}
  ],
  "metadata": {"caller_id": "service-a"}
}
```

### Get Job Response (Error)

```http
GET /jobs/abc-123

HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": "abc-123",
  "status": "error",
  "created_at": "2026-01-23T10:00:00Z",
  "completed_at": "2026-01-23T10:00:05Z",
  "error": "Audio file format not supported",
  "error_code": "invalid_audio"
}
```

---

## OpenAPI Documentation Standards

### Required Documentation Elements

From [OpenAPI Specification v3.1](https://spec.openapis.org/oas/v3.1.0.html):

| Element | Purpose |
|---------|---------|
| Operation summaries | One-line description of each endpoint |
| Request body schemas | JSON Schema for all request formats |
| Response schemas | JSON Schema for all response types |
| Status codes | Document all possible response codes |
| Examples | Include realistic example payloads |
| Error responses | Document error format consistently |

### FastAPI Auto-Generation

FastAPI generates OpenAPI docs automatically from Pydantic models. Define:

```python
class JobSubmitRequest(BaseModel):
    audio_url: Optional[HttpUrl] = None
    model: Literal["tiny", "base", "small", "medium", "large"] = "base"
    language: Optional[str] = None
    metadata: Optional[dict] = None

class JobResponse(BaseModel):
    id: str
    status: Literal["queued", "processing", "completed", "error"]
    created_at: datetime
    completed_at: Optional[datetime] = None
    text: Optional[str] = None
    error: Optional[str] = None
```

Swagger UI available at `/docs`, ReDoc at `/redoc`.

---

## Anti-Features

Features to deliberately NOT build for an internal service.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **API key authentication** | Internal service, adds complexity | Trust network boundary (or add later) |
| **Rate limiting** | Internal service, self-manage load | Monitor, add if needed |
| **Usage billing/metering** | Not a public API | Log for observability only |
| **Multiple API versions** | Internal service, can coordinate deploys | Single version, deprecate carefully |
| **Signed webhooks** | Overkill for internal | Simple shared secret if needed |
| **Complex retry queues** | Over-engineering | Simple in-memory or Redis queue |
| **Real-time streaming** | Different architecture | Batch API only for v2.0 |
| **User management** | Not needed internally | No user accounts |
| **File storage/CDN** | Clients manage their files | Accept URL or upload, don't persist |
| **Complex job scheduling** | Priority queues, delayed jobs | FIFO is sufficient |

### Explicitly Out of Scope for v2.0

1. **Real-time/streaming transcription** - Requires WebSocket, different architecture
2. **Speaker diarization** - Complex feature, defer to v3+
3. **Translation** - Out of scope for transcription service
4. **Audio preprocessing** - Noise reduction, normalization (client responsibility)
5. **Long-term job history** - Jobs can be ephemeral, client stores results

---

## Sources

### Primary Sources (HIGH confidence)
- [AssemblyAI API Reference](https://www.assemblyai.com/docs/api-reference/overview)
- [AssemblyAI Webhooks](https://www.assemblyai.com/docs/deployment/webhooks)
- [Deepgram Callback Documentation](https://developers.deepgram.com/docs/callback)
- [Azure Async Request-Reply Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply)
- [OpenAPI Specification v3.1](https://spec.openapis.org/oas/v3.1.0.html)

### REST API Patterns (MEDIUM confidence)
- [REST API Design for Long-Running Tasks](https://restfulapi.net/rest-api-design-for-long-running-tasks/)
- [REST API Cookbook: Asynchronous API](https://octo-woapi.github.io/cookbook/asynchronous-api.html)
- [AWS Architecture Blog: Managing Async Workflows](https://aws.amazon.com/blogs/architecture/managing-asynchronous-workflows-with-a-rest-api/)

### Webhook Best Practices (MEDIUM confidence)
- [Webhook Best Practices Guide](https://inventivehq.com/blog/webhook-best-practices-guide)
- [Stripe Webhooks Documentation](https://docs.stripe.com/webhooks)

### FastAPI Background Tasks (MEDIUM confidence)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [FastAPI Background Processing Guide](https://blog.greeden.me/en/2025/12/02/practical-background-processing-with-fastapi-a-job-queue-design-guide-with-backgroundtasks-and-celery/)

---

## Implications for Roadmap

### Phase Structure Recommendation

**Phase 1: Core API (Table Stakes)**
- POST /transcribe (file upload)
- GET /jobs/{id}
- Job states: queued, processing, completed, error
- In-memory job queue (start simple)

**Phase 2: Enhanced Features**
- URL reference input
- Model selection
- Word timestamps
- Language detection
- Job deletion/cancellation

**Phase 3: Production Hardening**
- Redis-backed queue (persistence)
- Webhook callbacks (if needed)
- OpenAPI documentation polish

### Key Decision Points

1. **Queue backend**: Start with in-memory (FastAPI BackgroundTasks), graduate to Redis/ARQ if persistence needed
2. **File handling**: Accept upload, store temporarily, delete after processing
3. **Job retention**: Keep jobs in memory for 1 hour, then purge (no long-term storage)
4. **Webhook**: Defer unless specific use case emerges
