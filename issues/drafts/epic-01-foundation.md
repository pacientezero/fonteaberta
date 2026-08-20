# EPIC 01 - Bootstrap da plataforma

## Objetivo

Subir o ambiente base do projeto para que o resto do trabalho seja incremental e verificavel.

## Escopo

- Criar o monorepo.
- Criar `docker-compose` com os servicos base.
- Subir PostgreSQL com `pgvector`.
- Subir Directus como camada de API e administracao.
- Subir Redis, n8n, Kestra e Ollama.
- Criar a app SvelteKit inicial.
- Criar o esqueleto da API de IA.

## Fora de escopo

- Ingestao de dados reais.
- RAG de documentos.
- Frontend de dominio completo.
- Qualquer expansao para Kafka, Elasticsearch/OpenSearch, Kubernetes ou banco de grafos.

## Dependencias

- Nenhuma.

## Criterios de aceite

- `docker compose up` inicia a stack sem ajuste manual.
- Cada servico tem healthcheck basico.
- O projeto documenta variaveis de ambiente e porta de cada servico.
- O repositorio mostra onde ficam as proximas etapas.

## Checklist

- [ ] Estrutura inicial do monorepo
- [ ] Compose base
- [ ] PostgreSQL + pgvector
- [ ] Directus
- [ ] Redis
- [ ] n8n
- [ ] Kestra
- [ ] Ollama
- [ ] SvelteKit
- [ ] API de IA
- [ ] README de bootstrap
