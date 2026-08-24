# Issue 02 - Data governance and provenance

Phase: 01-data-governance

## Goal

Create the canonical data model for sources, datasets, ingestions, raw records, facts, evidence, and claims.

## Scope

- Migrations.
- Directus collections.
- RBAC.
- Provenance chain.

## Dependencies

- Issue 01.

## Acceptance criteria

- A record can be traced from source to claim.
- The dataset definition of done is testable.

## Notes

- This issue should not start before the bootstrap layer is stable.
- The Directus sidebar is organized by domain as `catalogo`, `ingestao`, `proveniencia`, `eleitoral`, `documentos`, `economia`, and `legislativo`, with icons and colors kept in the database-backed smoke test.
