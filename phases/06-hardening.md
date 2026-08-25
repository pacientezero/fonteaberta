# Phase 06 - Hardening

Status: completed

## Goal

Lock down correctness, observability, and release readiness.

## In scope

- Data quality.
- Anti-hallucination tests.
- Observability.
- Security.
- Privacy.
- Cache.
- Search.
- Accessibility.
- README public.

## Exit criteria

- The system is auditable and the factual response path is testable end to end.

## Status notes

- Web and API now emit baseline security headers, cache policy, request IDs, and server timing.
- The release gate checks the factual path and the new hardening headers against the local stack.
