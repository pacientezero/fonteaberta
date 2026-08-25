# Issue 09 - TSE presidential coverage full

Phase: 02-tse-v1
Status: open

## Goal

Expand the presidential TSE slice from the single featured sample to the full 2026 presidential candidate and asset coverage.

## Scope

- All presidential candidates in 2026.
- All declared assets for those candidates.
- Entity mapping for every imported candidate.
- Candidate index/discovery path in the public UI.
- Reproducible provenance for every imported row, evidence item, fact, and claim.

## Dependencies

- Issue 02.
- Issue 03.
- Existing sample bundle and summary paths.

## Acceptance criteria

- The database contains more than one 2026 presidential candidate.
- Every imported candidate has all declared assets imported and totaled.
- The public UI can discover and open multiple presidential candidates, not just the featured sample.
- The provenance chain remains traceable from source to claim for every imported candidate.

## Notes

- The official TSE dataset page for `Candidatos - 2026` exposes separate CSV resources for `Candidatos` and `Bens de candidatos`.
- The current repository only has a single-candidate fixture sample, so this issue is the formal backlog item for the missing coverage.
- The public search path now exposes a presidential candidate catalog route, but the imported database still contains only one candidate because the official ZIP resources are blocked from this environment with `403`.
