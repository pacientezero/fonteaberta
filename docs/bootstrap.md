# Phase 00 Bootstrap

This document explains the local stack skeleton that now exists in the repo.

## What ships in this phase

- PostgreSQL with `pgvector`
- Directus
- Redis
- n8n
- Kestra
- Ollama
- FastAPI AI service skeleton
- SvelteKit web skeleton

## How to start

```bash
make up
```

or:

```bash
docker compose up --build
```

## Local URLs

- Web: `http://localhost:4173`
- API: `http://localhost:8000`
- Directus: `http://localhost:8055`
- n8n: `http://localhost:5678`
- Kestra: `http://localhost:8080`
- Ollama: `http://localhost:11434`

## Bootstrap contract

- The stack is intentionally minimal.
- The data governance phase comes next.
- Business data ingestion is not part of this phase.
- The stack should start without manual edits after copying `.env.example` to `.env`, if you choose to use local overrides.
