# Requirements: Cesar v2.4 Idempotent Processing

**Defined:** 2026-02-02
**Core Value:** Transcribe audio to text anywhere, offline, with a single command or API call — no cloud services, no API keys, no ongoing costs.

## v2.4 Requirements

Requirements for idempotent processing milestone. Each maps to roadmap phases.

### Cache Foundation

- [ ] **CACHE-01**: Cache uses XDG-compliant directory (~/.cache/cesar/)
- [ ] **CACHE-02**: Cache writes are atomic (write-to-temp-then-rename pattern)
- [ ] **CACHE-03**: CLI accepts --no-cache flag to force reprocessing
- [ ] **CACHE-04**: API accepts no_cache parameter to force reprocessing

### Download Caching

- [ ] **DLOAD-01**: YouTube audio downloads are cached by URL
- [ ] **DLOAD-02**: Cached downloads skip re-download on subsequent requests
- [ ] **DLOAD-03**: Cache key includes time-step function for URL freshness (15-minute windows)
- [ ] **DLOAD-04**: Time-step interval is configurable via config.toml

### Disk Management

- [ ] **DISK-01**: Cache has configurable size limit (default 10GB)
- [ ] **DISK-02**: LRU eviction removes oldest entries when limit exceeded
- [ ] **DISK-03**: Cache size limit is configurable via config.toml

## Future Requirements

Deferred to later milestones. Tracked but not in current roadmap.

### Intermediate Artifact Caching

- **ARTIFACT-01**: Transcription output is cached by content hash
- **ARTIFACT-02**: Diarization segments are cached by content hash + options
- **ARTIFACT-03**: Resume from failure point (retry from last successful stage)

### Cache Visibility

- **VIS-01**: CLI --cache-info flag shows cache status/stats
- **VIS-02**: Verbose mode logs cache hits/misses
- **VIS-03**: API health endpoint includes cache statistics

### Cache Management

- **MGMT-01**: cesar cache clean command for manual cleanup
- **MGMT-02**: cesar cache list command to inspect entries

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Transcription caching | Complexity, defer to future milestone |
| Diarization caching | Complexity, defer to future milestone |
| Resume from failure | Requires artifact caching, defer |
| --cache-info flag | Polish feature, defer to future milestone |
| cesar cache commands | Management CLI, defer to future milestone |
| Distributed cache | Single-machine focus, no Redis/multi-instance |
| HTTP conditional requests | Advanced freshness, time-step sufficient for MVP |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CACHE-01 | Phase 17 | Pending |
| CACHE-02 | Phase 17 | Pending |
| CACHE-03 | Phase 18 | Pending |
| CACHE-04 | Phase 18 | Pending |
| DLOAD-01 | Phase 18 | Pending |
| DLOAD-02 | Phase 18 | Pending |
| DLOAD-03 | Phase 18 | Pending |
| DLOAD-04 | Phase 18 | Pending |
| DISK-01 | Phase 19 | Pending |
| DISK-02 | Phase 19 | Pending |
| DISK-03 | Phase 19 | Pending |

**Coverage:**
- v2.4 requirements: 11 total
- Mapped to phases: 11/11 (100%)
- Unmapped: 0

---
*Requirements defined: 2026-02-02*
*Last updated: 2026-02-02 after roadmap creation*
