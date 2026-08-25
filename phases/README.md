# Phases

This repo is organized to avoid scope creep.

## Current phase order

| Phase | Goal | Depends on | Status |
| --- | --- | --- | --- |
| 00 | Bootstrap the repo and local stack skeleton | None | Completed |
| 01 | Build data governance and provenance model | 00 | Completed |
| 02 | Deliver the TSE 2026 vertical | 01 | Completed |
| 03 | Ship the public V1 UI | 01, 02 | Completed |
| 04 | Add documents and RAG | 00, 01 | Completed |
| 05 | Expand to legislature and transparency data | 01, 03, 04 | Completed |
| 06 | Hardening, tests, observability, and release readiness | All prior phases | Completed |

## Rule

Do not jump to a later phase before the earlier phase has a clear exit criterion and a testable output.
