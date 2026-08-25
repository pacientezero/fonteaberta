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

| Group | Icon | Color | Collections |
| --- | --- | --- | --- |
| `catalogo` | `database` | `#475569` | `sources`, `datasets` |
| `ingestao` | `tray-arrow-down` | `#d97706` | `ingestion_runs` |
| `proveniencia` | `shield-check` | `#059669` | `raw_records`, `evidence`, `facts`, `claims` |
| `eleicoes` | `ballot` | `#2563eb` | `people`, `entity_aliases`, `elections`, `parties`, `candidates`, `candidate_assets` |
| `documentos` | `book-open-page-variant` | `#0ea5e9` | `documents`, `document_versions`, `document_chunks` |
| `economia` | `chart-box-outline` | `#0891b2` | `economic_series`, `economic_observations` |
| `legislativo` | `gavel` | `#7c3aed` | `mandates` |
| `transparencia` | `file-eye` | `#0f766e` | `government_expenses` |
| `tesouro` | `bank` | `#1e3a8a` | `rreo_rows` |
| `comprasgov` | `cart-outline` | `#ca8a04` | `comprasgov_supplier_records` |

`claims_evidence` stays a technical join table and is intentionally not managed as a Directus collection because it only exists to link claims and evidence in the provenance chain.

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
- Directus collections and sidebar metadata exist for the phase 01 governance tables, with the sidebar palette pinned in the smoke test and later domain folders introduced by their own expansion migrations.
- Public and researcher read access is declared in the database-backed RBAC seed.
