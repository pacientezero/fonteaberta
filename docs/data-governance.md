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
- Directus collections exist for the managed canonical tables.
- Public and researcher read access is declared in the database-backed RBAC seed.

## Note

- `claims_evidence` is kept as the N:N join table for provenance and is intentionally not managed as a Directus collection because the Directus runtime ignores tables without a primary key.
