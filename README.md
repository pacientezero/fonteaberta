# FonteAberta

Plataforma open source de dados publicos oficiais.

## Referencias canonicas

- `docs/referencias/BLUEPRINT_DADOS_PUBLICOS_OFICIAIS.md`
- `docs/referencias/AnaliseRAG.md`

## Estrutura de trabalho

- `issues/EPICS.md` define o backlog em epicos.
- `planning/ROADMAP.md` define o roteiro executivo.
- `phases/` define a ordem de execucao por fase.
- `docs/referencias/` guarda os documentos base copiados para o repo.

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
