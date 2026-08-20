# Referencias do Projeto

Estes dois arquivos sao a base de referencia do projeto:

- `BLUEPRINT_DADOS_PUBLICOS_OFICIAIS.md`: contrato principal de produto, arquitetura, V1 e ordem de implementacao.
- `AnaliseRAG.md`: analise complementar de arquitetura, prioridades e riscos para memoria, roteamento, RAG, avaliacao e handoff.

## Distincao importante

### O que veio como instrucao dos documentos

- Toda afirmacao factual deve apontar para fonte oficial.
- Separar `official_fact`, `computed_fact` e `ai_inference`.
- V1 e estritamente o caminho presidencial 2026.
- O caminho inicial deve ser vertical: TSE -> raw_records -> normalize -> people/elections/parties/candidates/candidate_assets.
- A ordem de implementacao prioriza fundacao, dados, connector TSE, frontend, documentos/RAG e depois expansoes.
- O sistema precisa mostrar evidencia e provenance, nao apenas respostas.
- O blueprint proibe, para esta fase, atalhos como Kafka, Elasticsearch/OpenSearch, Kubernetes e banco de grafos.

### O que veio como pedido do usuario

- Salvar os arquivos como referencia do projeto.
- Comecar a producao.
- Fatiar o trabalho em epicos/issues.
- Avancar passo a passo, com perguntas objetivas para destravar a proxima decisao.

## Leitura operacional

Use o blueprint como fonte de verdade de escopo.
Use o arquivo de analise como fonte de verdade de prioridades tecnicas.
Quando houver conflito, a regra do produto vem primeiro e a tecnica entra apenas como meio de implementacao.
