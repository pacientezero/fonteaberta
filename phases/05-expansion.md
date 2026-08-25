# Phase 05 - Expansion

Status: completed

## Goal

Add the next official sources after the V1 core is stable.

## In scope

- Camara.
- Senate.
- Transparency portal.
- Compras.gov.
- IBGE.
- BCB.
- Tesouro.

## Exit criteria

- The same provenance chain works on the expanded sources.

## Status notes

- BCB Selic validated locally.
- IBGE IPCA validated locally.
- Câmara dos Deputados validated locally.
- Senado Federal validated locally.
- Portal da Transparência despesas validated locally.
- Tesouro SICONFI RREO validated locally.
- Compras.gov supplier snapshot taxonomy reserved locally under `comprasgov`.
- Public frontend now exposes `/dados` as the live coverage dashboard, `/metodologia` as the operational contract page, and `/fontes` as the full source registry instead of a TSE-only page.
