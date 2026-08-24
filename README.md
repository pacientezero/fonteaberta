# FonteAberta

Plataforma open source de dados publicos oficiais.

## O projeto

O objetivo e entregar uma plataforma auditavel para dados publicos oficiais, com provenance, rastreio de origem e calculos reproduziveis.

## Referencias canonicas

- `docs/referencias/BLUEPRINT_DADOS_PUBLICOS_OFICIAIS.md`
- `docs/referencias/AnaliseRAG.md`
- `docs/bootstrap.md`
- `issues/README.md`
- `issues/EPICS.md`
- `planning/ROADMAP.md`
- `phases/README.md`

## Estrutura de trabalho

- `issues/EPICS.md` define o backlog em epicos.
- `planning/ROADMAP.md` define o roteiro executivo.
- `phases/` define a ordem de execucao por fase.
- `docs/referencias/` guarda os documentos base copiados para o repo.

## Setup local

### Pre-requisitos

- Git
- Docker Desktop ou Docker Engine com Docker Compose v2
- `make`

### 1. Clonar o repo

```bash
git clone https://github.com/pacientezero/fonteaberta.git
cd fonteaberta
git checkout main
```

### 2. Criar o arquivo local de ambiente

```bash
cp .env.example .env
```

O arquivo `.env` fica fora do Git. Ajuste somente o que precisar para sua maquina local.
Se voce tiver uma licenca do Directus, coloque-a em `DIRECTUS_LICENSE` no `.env`.

### 3. Validar o compose

```bash
make check
```

### 4. Subir a stack

```bash
make up
```

Ou, se preferir, rode direto:

```bash
docker compose up --build
```

### 5. Abrir os servicos

- Web: `http://localhost:4173`
- API: `http://localhost:8000`
- Directus: `http://localhost:8055`
- n8n: `http://localhost:5678`
- Kestra: `http://localhost:8080`
- Ollama: `http://localhost:11434`

### 6. Operacao diaria

```bash
make ps
make logs
make down
```

## Como contribuir

Este repo e open source, mas segue um fluxo estrito para manter rastreio:

- Leia `AGENTS.md` antes de começar.
- Toda feature nova precisa de uma issue dedicada.
- Toda feature nova precisa de uma branch dedicada.
- Nao escreva direto em `main`.
- Toda mudanca entra em `main` por merge de branch.
- Preserve as branches depois do merge; nao delete sem pedido explicito.

## Bootstrap

Se quiser detalhes do que existe nesta fase inicial, leia `docs/bootstrap.md`.

## Escopo V1

- Eleicao presidencial 2026.
- Caminho vertical inicial: TSE -> raw_records -> normalize -> people/elections/parties/candidates/candidate_assets.
- Resposta factual sempre com fonte, dataset, data de coleta e evidencia.

## Ordem atual

1. Phase 00 - Bootstrap
2. Phase 01 - Data governance
3. Phase 02 - TSE V1
4. Phase 03 - Public UI
5. Phase 04 - Documents and RAG
6. Phase 05 - Expansion
7. Phase 06 - Hardening
