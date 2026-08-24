# Data Governance

This project treats provenance as a first-class contract.

## Canonical chain

- `sources`
- `datasets`
- `ingestion_runs`
- `raw_records`
- `evidence`
- `facts`
- `claims`
- `claims_evidence`

## Directus organization

The admin sidebar is grouped as:

- `catalogo`: `sources`, `datasets`
- `ingestao`: `ingestion_runs`
- `proveniencia`: `raw_records`, `evidence`, `facts`, `claims`
- `tse`: `people`, `entity_aliases`, `elections`, `parties`, `candidates`, `candidate_assets`
- `documentos_rag`: `documents`, `document_versions`, `document_chunks`
- `economia`: `economic_series`, `economic_observations`

`claims_evidence` stays a technical join table and is intentionally not managed as a Directus collection because the Directus runtime ignores tables without a primary key.

## What the first governance milestone covers

- Source registry and dataset registry
- Traceable dataset-to-source relationship
- Ingestion run bookkeeping
- Raw payload preservation
- Evidence and claims chain
- Read-only Directus access for the public provenance tables
- A smoke test that proves source -> dataset -> raw record -> evidence -> fact -> claim traceability

## Local commands

```bash
make migrate-governance
make check-governance
```

## Definition of done

- Every record can be traced from source to claim.
- The provenance path is testable with an automated smoke test.
- Directus collections and sidebar metadata exist for the managed canonical and document tables.
- Public and researcher read access is declared in the database-backed RBAC seed.
