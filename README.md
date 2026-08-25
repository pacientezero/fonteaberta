# FonteAberta

Plataforma open source de dados publicos oficiais.

## O projeto

O objetivo e entregar uma plataforma auditavel para dados publicos oficiais, com provenance, rastreio de origem e calculos reproduziveis.

## O que e

Uma plataforma open source para consultar, cruzar e auditar dados publicos oficiais brasileiros com fonte, dataset, evidencia e calculo reproduzivel.

## O que nao e

- Nao e agregador de noticias.
- Nao e painel de opinioes ou resumos sem fonte.
- Nao e um chatbot generico sem provenance.
- Nao e substituto dos portais oficiais.

## Arquitetura

- `apps/web`: interface publica.
- `apps/api`: servico factual e de recuperacao.
- `infra/postgres`: schema, seeds e migrations.
- `Directus`: organizacao editorial e leitura operacional dos dados.
- `n8n` e `Kestra`: orquestracao e automacao.
- `docs/referencias`: contrato de produto e analise tecnica.

## Fontes

O projeto prioriza fontes primarias e oficiais. A ordem de implementacao, os dominios e os slices de dados estao documentados em:

- `docs/referencias/BLUEPRINT_DADOS_PUBLICOS_OFICIAIS.md`
- `docs/referencias/AnaliseRAG.md`
- `planning/ROADMAP.md`
- `issues/EPICS.md`

## Como criar connector

1. Abrir uma issue dedicada para a nova fonte ou slice.
2. Criar uma branch dedicada para essa issue.
3. Registrar source, dataset, fixture e migration.
4. Criar o script de validacao idempotente.
5. Atualizar os checks e a documentacao da fase.
6. Validar com `make check-*` antes de pedir merge.

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

## Metodologia

- Progresso por fatias verticais.
- Fonte oficial antes de inferencia.
- Provenance antes de resposta.
- Evidencia antes de claim.
- Nada entra em `main` sem branch e issue.

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

## Licenca

O projeto e distribuido sob `AGPL-3.0`. Derivados expostos como servico tambem precisam publicar modificacoes.
