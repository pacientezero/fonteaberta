# Issue 06 - Expansion sources

Phase: 05-expansion

## Goal

Add the next official sources after the V1 core is stable.

## Scope

- Camara.
- Senate.
- Transparency portal.
- Compras.gov.
- IBGE.
- BCB.
- Tesouro.

## Dependencies

- Issue 02.
- Issue 04.
- Issue 05.

## Acceptance criteria

- The same provenance chain works on the expanded sources.

## Notes

- Do not start this before the V1 core is stable and visible.
- First expansion slice completed: BCB Selic time series with deterministic fixture, idempotent ingest, and no-evidence query behavior.
- Second expansion slice completed: IBGE IPCA monthly variation with deterministic fixture, idempotent ingest, and no-evidence query behavior.
- Directus now groups the economic collections under `economia` with stable icons, colors, and sort order covered by the governance smoke test.
- Third expansion slice completed: Câmara current deputies snapshot with `mandates`, provenance, facts, and claims against the official `/deputados` and `/deputados/{id}` endpoints.
