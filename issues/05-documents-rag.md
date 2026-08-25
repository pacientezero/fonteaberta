# Issue 05 - Documents and RAG

Phase: 04-documents-rag
Status: completed

## Goal

Support official documents, extraction, chunking, embeddings, retrieval, and citations.

## Scope

- Documents.
- Document versions.
- Chunks.
- Embeddings.
- Vector search.
- AI service.

## Dependencies

- Issue 01.
- Issue 02.

## Acceptance criteria

- Official documents can be retrieved and cited without unsupported claims.

## Notes

- Keep this separate from the TSE vertical so the V1 path stays controlled.
- Validated with deterministic fixture-driven ingest, citation retrieval, and unsupported-query abstention.
