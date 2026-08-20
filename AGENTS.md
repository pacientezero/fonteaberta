# AGENTS.md

## Purpose

This repository is for the `fonteaberta` project: an open source platform for official public data with auditability, provenance, and reproducible calculations.

## Canonical references

Use these files as the source of truth before starting any implementation:

- `docs/referencias/README.md`
- `docs/referencias/BLUEPRINT_DADOS_PUBLICOS_OFICIAIS.md`
- `docs/referencias/AnaliseRAG.md`
- `issues/README.md`
- `issues/EPICS.md`
- `phases/README.md`
- `phases/00-bootstrap.md`
- `phases/01-data-governance.md`
- `phases/02-tse-v1.md`
- `phases/03-public-ui.md`
- `phases/04-documents-rag.md`
- `phases/05-expansion.md`
- `phases/06-hardening.md`

## Working rules

- Treat the blueprint document as the product contract.
- Treat the RAG analysis document as the technical priority and risk guide.
- Keep execution aligned with the phase order in `phases/`.
- Keep backlog items aligned with `issues/`.
- Do not start implementation from an untracked idea.
- Before any feature work, confirm the issue that defines the scope.

## Branch and issue policy

- Every new feature must have a dedicated issue.
- Every new feature must have a dedicated branch.
- Name the branch from the issue, for example `feature/03-tse-v1`.
- Do not implement a new feature directly on `main`.
- Do not mix multiple features in one branch unless the user explicitly asks for a combined change.
- Keep non-feature work small and traceable.

## Change discipline

- Make the smallest useful change for the current phase.
- Update the relevant issue file when scope or acceptance criteria change.
- Keep references, phase files, and issue files in sync.
- Prefer explicit dates, file paths, and evidence over vague summaries.

## Safety

- Do not use destructive git commands unless explicitly requested.
- Do not overwrite user changes outside the current scope.
- If a requested change conflicts with the phase plan or issue structure, call out the conflict before proceeding.
