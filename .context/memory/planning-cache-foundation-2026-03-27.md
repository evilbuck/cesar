---
date: 2026-03-27
domains: [planning, architecture]
topics: [v2.4, cache-foundation, phase-17, content-addressable-storage]
related: [research-2026-03-27.md]
priority: high
status: active
---

# Session: Phase 17 Cache Foundation Planning

## Context
- Previous work: Research completed for v2.4 Cache Foundation
- Goal: Create detailed implementation plan for Phase 17

## Decisions Made
- Created comprehensive plan following existing project patterns
- Plan includes 3 tasks: cache module, config updates, and unit tests
- Used SHA-256 for content addressing with 2-char directory sharding
- Atomic writes via temp-file-then-rename pattern
- XDG-compliant default cache location (~/.cache/cesar/)

## Implementation Plan Summary

### Task 1: Create cesar/cache.py
- ContentAddressableCache class with SHA-256 content addressing
- CacheEntry dataclass for metadata
- Atomic write operations (write-to-temp-then-rename)
- Directory sharding: objects/ab/cd/ef... to avoid too many files in one directory
- YouTube-specific methods for URL-based lookup

### Task 2: Update cesar/config.py
- Add cache_dir field to CesarConfig model
- Add get_cache_dir() helper function
- Update DEFAULT_CONFIG_TEMPLATE with cache documentation

### Task 3: Create tests/test_cache.py
- Comprehensive unit tests (minimum 200 lines)
- Test atomic writes, hash computation, metadata
- Test YouTube URL normalization
- Edge case tests (empty data, large files, unicode)

## Key Files Referenced
- `.planning/REQUIREMENTS.md` - CACHE-01, CACHE-02 requirements
- `.planning/phases/09-configuration-system/09-01-PLAN.md` - Planning template
- `cesar/config.py` - Existing config patterns
- `.context/RESEARCH.md` - Previous research findings

## Saved Plan Location
`.context/plans/17-cache-foundation-PLAN.md`

## Next Steps
- [ ] Execute plan with `/b-build` or `/b-build-hard`
- [ ] Review implementation with `/b-review`
- [ ] Update backlog when Phase 17 complete
- [ ] Begin Phase 18 planning (Download Caching & Controls)
