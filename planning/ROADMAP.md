# Roadmap Executivo

## Objetivo

Entregar a V1 da plataforma com base em dados publicos oficiais, provenance auditavel e calculos reproduziveis.

## Estado atual

- Repo Git criado e publicado em GitHub.
- Branch de trabalho atual: `feature/06-expansion`.
- Fases 00 a 05 concluidas e validadas localmente na branch de trabalho.
- Fase 05 concluida localmente com os slices do BCB Selic, IBGE IPCA, Câmara dos Deputados, Senado Federal, Portal da Transparência, Compras.gov e Tesouro validados localmente.
- `AGENTS.md` define o contrato operacional.
- `issues/` contem o backlog em 7 issues.
- `phases/` contem a ordem de execucao por fase.

## Regras de execucao

- Cada feature nova precisa de uma issue dedicada.
- Cada feature nova precisa de uma branch dedicada.
- `main` e protegida e nao recebe escrita direta.
- Toda mudanca entra em `main` por merge de branch.
- Branches sao preservadas apos merge e nao devem ser deletadas sem pedido explicito.
- Nao misturar multiplas features na mesma branch.

## Sequencia de entrega

### Fase 00 - Bootstrap

Base: [Issue 01](../issues/01-bootstrap.md)

Entregas:

- estrutura minima do monorepo
- stack local base
- docker compose
- docs de bootstrap

Criterio de aceite:

- ambiente sobe sem ajuste manual e a estrutura fica versionada

### Fase 01 - Data governance

Base: [Issue 02](../issues/02-data-governance.md)

Entregas:

- migrations
- collections Directus
- RBAC
- source registry
- datasets
- ingestion runs
- raw records
- facts
- evidence
- claims

Criterio de aceite:

- qualquer dado pode ser rastreado da source ao claim

### Fase 02 - TSE V1

Base: [Issue 03](../issues/03-tse-v1.md)

Entregas:

- connector core
- connector TSE
- candidatos 2026
- bens 2026
- entity mapping
- testes de importacao

Criterio de aceite:

- a pergunta sobre patrimonio do candidato responde com fonte oficial e calculo reproduzivel

### Fase 03 - Public UI

Base: [Issue 04](../issues/04-public-ui.md)

Entregas:

- home
- pesquisa
- pagina de candidato
- pagina de patrimonio
- pagina de fontes
- provenance UI

Criterio de aceite:

- o usuario enxerga resposta, fonte, dataset, registros e evidencia

### Fase 04 - Documents and RAG

Base: [Issue 05](../issues/05-documents-rag.md)

Entregas:

- documents
- document versions
- chunks
- embeddings
- vector search
- AI service
- citacoes

Criterio de aceite:

- propostas oficiais podem ser recuperadas e citadas sem extrapolacao

### Fase 05 - Expansion

Base: [Issue 06](../issues/06-expansion.md)

Entregas:

- Camara
- Senate
- Transparency portal
- Compras.gov
- IBGE
- BCB
- Tesouro

Criterio de aceite:

- a mesma cadeia de provenance funciona nas novas fontes

Status atual:

- BCB Selic validado localmente.
- IBGE IPCA validado localmente.
- Câmara dos Deputados validado localmente com a primeira fatia de deputados e mandates.
- Senado Federal validado localmente com snapshot datado da lista de senadores em exercício.
- Portal da Transparência validado localmente com o slice de despesas.
- Tesouro validado localmente com o slice de RREO São Paulo 2024 P6 Anexo 01.
- Compras.gov teve a taxonomia Directus organizada em `comprasgov` e a API pública exposta para o slice de fornecedores ativos.

### Fase 06 - Hardening

Base: [Issue 07](../issues/07-hardening.md)

Entregas:

- data quality
- anti-hallucination tests
- observability
- security
- privacy
- cache
- search
- accessibility
- public README

Criterio de aceite:

- o caminho factual fica auditavel e testavel end to end

Status atual:

- headers basicos de seguranca, politica de cache, request IDs e server timing estao ativos em web e API
- o gate de release verifica a trilha factual completa e o slice de hardening no stack local

## Estado geral

- Fases 00 a 06 concluidas e verificadas localmente.
- A licenca final do projeto e `AGPL-3.0`.

## Caminho critico

1. Data governance antes do connector.
2. Connector antes da UI publica.
3. UI publica antes da expansao.
4. Documents and RAG podem comecar cedo, mas nao podem travar a V1.
5. Hardening fica por ultimo, depois do fluxo funcional existir.

## Proxima acao recomendada

Abrir a branch da [Issue 07](../issues/07-hardening.md) assim que a Issue 06 estiver consolidada na branch principal.
