# Issue 09 - TSE presidential coverage full

Phase: 02-tse-v1
Status: completed

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

- The official TSE dataset page for `Candidatos - 2026` exposes separate CSV resources for `Candidatos`, `Candidatos complementar`, and `Bens de candidatos`.
- The repository now imports the full 2026 candidate catalog, the complementary dataset, and all declared assets into the local database.
- The public search path now exposes the full candidate catalog and can search by name or `SQ_CANDIDATO`.
- Current runtime evidence shows `20.732` imported candidates and traceable complementary and asset provenance for the featured sample.
