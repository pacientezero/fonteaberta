# Issue 06 - Expansion sources

Phase: 05-expansion
Status: completed

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
- Directus now groups the economic collections under `economia` with stable icons, colors, and sort order defined by the phase migration.
- Directus now reserves `transparencia` and `tesouro` as top-level folders for the Portal da Transparência and SICONFI slices, keeping both separate from `economia`.
- Directus now reserves `comprasgov` as a top-level folder for the Compras.gov supplier slice, keeping it separate from `transparencia`, sitting after `tesouro` in the sidebar order, and leaving room for future procurement collections.
- Third expansion slice completed: Câmara current deputies snapshot with `mandates`, provenance, facts, and claims against the official `/deputados` and `/deputados/{id}` endpoints.
- Fourth expansion slice completed: Senado current roster snapshot using the official `GET /dadosabertos/senador/lista/atual?v=4` list endpoint, with snapshot-dated provenance and no dependency on the per-senator detail endpoint.
- Fifth expansion slice completed: Portal da Transparência despesas bulk slice with `government_expenses`, deterministic fixture, idempotent ingest, and summary/detail query behavior.
- Sixth expansion slice completed: Tesouro SICONFI RREO São Paulo 2024 P6 Anexo 01 with `rreo_rows`, deterministic fixture, idempotent ingest, and summary/detail query behavior.
- Public frontend now exposes `/dados` as a live coverage dashboard for V1, documents, BCB, IBGE, Câmara, Senado, Transparência, Tesouro, and Compras.gov, plus `/metodologia` for the operational contract.
- Public frontend now exposes `/fontes` with the featured TSE slice plus the live registry of the other public coverage cards, so the source page no longer reads as TSE-only.
