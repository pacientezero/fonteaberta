# Backlog em Epicos

Fonte de referencia:

- `docs/referencias/BLUEPRINT_DADOS_PUBLICOS_OFICIAIS.md`
- `docs/referencias/AnaliseRAG.md`

## Regras de corte para V1

- Escopo V1: eleicao presidencial 2026.
- A pergunta inicial do produto e: `Quanto o candidato X declarou em patrimonio?`
- Toda resposta precisa mostrar fonte, dataset, data de coleta e mecanismo de calculo.
- Nao entrar em Kafka, Elasticsearch/OpenSearch, Kubernetes ou banco de grafos nesta fase.

## Ordem recomendada

1. Bootstrap da plataforma
2. Modelo de dados e governanca de evidencias
3. Connector TSE e importacao 2026
4. Frontend publico V1
5. Engine de documentos e RAG
6. Expansao legislativa e transparencia
7. Hardening, testes e observabilidade

## Phases

Each epic maps to a file under `phases/`.
Use the phase files as the execution plan and this file as the backlog index.

## Epicos

### EPIC 01 - Bootstrap da plataforma

- Objetivo: subir o monorepo e o stack minimo executavel.
- Inclui: Docker Compose, PostgreSQL, pgvector, Directus, Redis, n8n, Kestra, Ollama, SvelteKit e API de IA.
- Depende de: nada.
- Sai pronto quando: `docker compose up` sobe tudo, healthchecks passam e o ambiente fica documentado.

### EPIC 02 - Modelo de dados e governanca

- Objetivo: criar a camada canonica de fontes, datasets, ingestoes, raw records, pessoas, aliases, facts, evidence e claims.
- Inclui: migrations, collections do Directus, RBAC e rastreabilidade.
- Depende de: EPIC 01.
- Sai pronto quando: um dado pode ser rastreado de source -> dataset -> raw record -> evidence -> fact/claim.

### EPIC 03 - Connector TSE e V1 2026

- Objetivo: importar candidatos 2026 e bens 2026 com idempotencia e proveniencia.
- Inclui: connector core, connector TSE, entity mapping e testes.
- Depende de: EPIC 02.
- Sai pronto quando: a pergunta sobre patrimonio do candidato responde com fonte oficial e calculo reproduzivel.

### EPIC 04 - Frontend publico V1

- Objetivo: entregar home, busca, pagina de candidato, patrimonio e fontes.
- Inclui: provenance UI, rotas publicas e navegacao de evidencias.
- Depende de: EPIC 02 e EPIC 03.
- Sai pronto quando: o usuario consegue ver resposta, fonte, dataset, registros usados e origem oficial.

### EPIC 05 - Engine de documentos e RAG

- Objetivo: suportar propostas de governo e consulta com citacoes.
- Inclui: documents, document_versions, document_chunks, embeddings, vector search e AI service.
- Depende de: EPIC 01 e EPIC 02.
- Sai pronto quando: propostas oficiais podem ser indexadas e citadas sem extrapolacao.

### EPIC 06 - Expansao legislativa e transparencia

- Objetivo: adicionar Camara, Senado, Portal da Transparencia, Compras.gov, IBGE, BCB e Tesouro.
- Inclui: historico parlamentar, proposicoes, votacoes, despesas, contratos e series macro.
- Depende de: EPIC 02 e, idealmente, EPIC 04/05 como base de UI e evidencia.
- Sai pronto quando: o produto consegue responder perguntas do escopo estendido com a mesma cadeia de provenance.

### EPIC 07 - Hardening, testes e observabilidade

- Objetivo: fechar qualidade, confiabilidade e preparo para release.
- Inclui: testes anti-alucinacao, data quality, observabilidade, correcoes, versionamento, seguranca, privacidade, cache, busca, i18n, acessibilidade e README publico.
- Depende de: os epicos anteriores terem um caminho funcional.
- Sai pronto quando: a resposta factual passa no DoD e a operacao fica auditavel.
