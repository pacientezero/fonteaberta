## Sumário executivo — 10 decisões de arquitetura

1. **Tire o estado conversacional do `static data` do n8n primeiro**: ele é experimental, indicado para dados pequenos e pode ser pouco confiável sob alta frequência; Postgres deve virar a fonte de verdade de sessão, eventos, handoff e mídia. ([GitHub][1])
2. **Separe sessão de canal e memória de longo prazo**: a janela de 24 h do WhatsApp é uma regra de envio, não o limite semântico de uma conversa; adote sessões por episódio, com TTL de inatividade inicialmente em 30–60 min e encerramento explícito por resolução/handoff/reset. ([Google Cloud Documentation][2])
3. **Não substitua o roteador determinístico por um LLM**: preserve IDs exatos, regras de negócio e regras de segurança como contratos; use modelo somente para texto livre, entidades, OOS, ambiguidade e classificação probabilística.
4. **Evolua o RAG antes de trocar de banco vetorial**: entity resolution → filtros de metadados → busca lexical+densa → RRF → reranker → evidência estruturada; códigos de erro e modelos não devem depender de similaridade semântica pura. ([Google Pesquisa][3])
5. **Transforme “confiança” em selective prediction**: `ANSWER / CLARIFY / HANDOFF`, calibrado em tráfego PT-BR rotulado; nunca trate a confiança autodeclarada pelo LLM como probabilidade de segurança. ([NeurIPS Proceedings][4])
6. **Handoff precisa ser uma transação real**: só diga “encaminhei” depois de ticket/queue ACK persistido; mantenha estados `PENDING → ACKNOWLEDGED → HUMAN_ACTIVE → RESOLVED/FAILED` e suprima o bot enquanto o humano assumiu.
7. **Pare de descartar mídia**: plaquetas e displays devem passar por quality gate → retificação/crop → OCR → extração tipada → validação de domínio → VLM como fallback → confirmação do usuário quando houver incerteza.
8. **Avalie a trajetória inteira, não só a resposta**: roteamento, slots, recuperação, citações, procedimento, escalada, número de turnos, estado final, custo e latência; instrumente com OpenTelemetry e mantenha LangSmith como backend substituível. ([Docs by LangChain][5])
9. **Temporal é P1/P2, não P0**: primeiro torne o estado durável no Postgres; adote execução durável quando RMA, timers, retries e espera por humano precisarem sobreviver por horas/dias a deploys e crashes.
10. **GraphRAG, MCP, multiagentes e fine-tuning generativo não são os próximos gargalos**: benchmark local primeiro; hoje os maiores ganhos prováveis estão em estado durável, recuperação estruturada, abstenção, OCR e avaliação.

A arquitetura analisada é exatamente a descrita no material: webhook multi-tenant, roteador determinístico em n8n, backend FastAPI/Postgres/pgvector com RAG híbrido e camada de envio WhatsApp.  Os seis problemas A–F também são fortemente acoplados: resolver memória sem resolver durabilidade, por exemplo, só muda o lugar onde o estado pode ser perdido.

**Legenda de maturidade usada abaixo:** **[ESTABELECIDO]** = boa sustentação em literatura/prática madura; **[PROMISSOR]** = evidência interessante, mas ainda dependente de contexto; **[HYPE/SEM EVIDÊNCIA SUFICIENTE]** = não há justificativa para fazê-lo no seu caso sem experimento local.

---

# Arquitetura-alvo

Eu convergiria para isto:

```text
WhatsApp Webhook
      |
      v
[verify signature + dedupe wamid]
      |
      v
[tenant dispatch: phone_number_id]
      |
      v
[load + serialize conversation state in Postgres]
      |
      v
+--------------------------------------------------+
| Deterministic contract layer                     |
| exact interactive IDs / safety / business rules  |
+--------------------------------------------------+
      |
      v
[intent/OOS + entity/slot extraction]
      |
      +---- ambiguous/incomplete ----> clarification
      |
      v
[entity-scoped hybrid retrieval]
BM25/lexical + dense -> RRF -> reranker
      |
      v
[typed diagnostic procedure / grounded generation]
      |
      v
[claim verification + calibrated selective gate]
      |
   +--+--------------------+
   |                       |
 ANSWER                  HANDOFF
   |                       |
   v                       v
[outbox]               [durable ticket/queue]
   |                       |
WhatsApp             ACK -> HUMAN_ACTIVE
   |
[status webhook]
      |
      v
[state transition + OTel trace + eval signals]
```

O n8n continua valioso como **integration/orchestration glue**. O problema é fazê-lo também de **conversation state store**. A própria documentação do n8n marca `getWorkflowStaticData` como experimental, para dados pequenos, e alerta sobre comportamento pouco confiável em execuções de alta frequência. Queue mode melhora escalabilidade usando Redis, workers e banco, mas não fornece por si só a semântica de uma máquina de estados conversacional durável. ([GitHub][1])

---

# 1. Gestão de sessão e memória em agentes conversacionais

## Terminologia canônica

Os termos que vale usar são **conversation session**, **dialogue state**, **Dialogue State Tracking (DST)**, **working memory / short-term memory**, **episodic memory**, **semantic memory**, **user/profile memory**, **memory consolidation**, **memory retrieval**, **progressive/rolling summarization**, **retention policy**, **idle session timeout / TTL** e **cross-session memory**.

Para o seu sistema, há uma separação especialmente importante:

| Camada                              | Conteúdo                                                                             | Vida útil                           |
| ----------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------- |
| **Working memory / dialogue state** | intenção ativa, marca/modelo corrente, pergunta pendente, slot faltante, passo atual | sessão                              |
| **Raw conversation history**        | mensagens reais, IDs, mídia, timestamps                                              | retenção auditável definida         |
| **Rolling summary**                 | resumo factual da sessão para controle de contexto                                   | sessão + handoff                    |
| **Episodic memory**                 | “cliente teve incidente X e fez Y”                                                   | entre sessões, se houver finalidade |
| **Profile/semantic memory**         | equipamento habitual, modelo, serial confirmado                                      | entre sessões, versionado           |
| **Procedural memory**               | manual, garantia, procedimento técnico                                               | **KB/RAG**, não memória do usuário  |

**[ESTABELECIDO]** A literatura recente de memória deixa claro que “jogar o histórico inteiro no contexto” não resolve o problema. Wu et al., *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory* (ICLR 2025), medem extração, raciocínio entre sessões, raciocínio temporal, atualização de fatos e abstenção; encontram forte degradação em interações longas e ganhos com **session decomposition**, **fact-augmented keys** e **time-aware query expansion**. ([ML Anthology][6]) Maharana et al., *Evaluating Very Long-Term Conversational Memory of LLM Agents* (ACL 2024), com o benchmark **LoCoMo**, chegam à mesma direção: long context e RAG ajudam, mas continuam substancialmente abaixo de humanos em relações temporais e causais entre sessões. ([ACL Anthology][7])

Isso também explica por que a estratégia atual — reescrever a nova consulta acrescentando a pergunta anterior — não é memória conversacional. Ela é melhor descrita como **query rewriting / contextual query reformulation**. É útil para recuperação:

> “E esse erro no modelo 8 kW?”
> → “erro E031 no inversor Marca X modelo Y 8 kW”

Mas não preserva adequadamente estado como “já pedi o serial”, “o cliente confirmou que o LED está vermelho”, “tentativa anterior falhou” ou “o procedimento está no passo 4”.

### Onde cada abordagem ganha

**Query rewriting** ganha em consultas independentes ou quase independentes e ajuda o retriever a receber uma consulta auto-contida. **Full/real history + DST** ganha quando os turnos executam uma tarefa, acumulam slots, negam fatos anteriores, alternam passos ou têm consequências. Para vocês, use os dois: histórico/estado é a verdade conversacional; query rewriting é uma transformação derivada para retrieval.

### Como produtos maduros definem sessão

Não há um número “cientificamente correto”. Há uma política de produto baseada em **inatividade + eventos explícitos**. Dialogflow CX mantém uma sessão por 30 min por padrão e permite TTL de até 24 h; Amazon Lex V2 usa 5 min por padrão, configurável até 24 h; o Rasa usa 60 min como configuração padrão atual e permite decidir se slots atravessam a fronteira da sessão. ([Google Cloud Documentation][2])

Isso sustenta uma política mais defensável que a de “WhatsApp = 24 horas”.

### Política que eu testaria

| Evento                                                  | Ação                                                         |
| ------------------------------------------------------- | ------------------------------------------------------------ |
| primeira mensagem sem sessão ativa                      | cria sessão                                                  |
| mensagem dentro de ~45 min de inatividade               | continua sessão                                              |
| >45 min sem atividade                                   | novo episódio por padrão                                     |
| “quero falar de outra coisa” / intenção não relacionada | fecha episódio anterior                                      |
| resolução confirmada                                    | `close_reason=resolved`                                      |
| handoff humano                                          | `close_reason=human_handoff` ou sessão em estado especial    |
| reset solicitado                                        | fecha + não carrega working state                            |
| nova sessão                                             | recupera apenas fatos cross-session explicitamente elegíveis |

Eu começaria com **45 minutos** e trataria isso como parâmetro a otimizar — não como verdade universal.

### Memória de longo prazo

Aqui há um risco comum: “agente com memória” vira “grave tudo para sempre”. Em suporte, prefira **memory write policy** explícita. Um fato só vai para memória cross-session quando:

1. tem utilidade futura previsível;
2. tem confiança suficiente;
3. sua proveniência é conhecida;
4. não é simplesmente estado temporário;
5. tem política de expiração/correção.

Um `serial_number` confirmado por foto pode persistir; “cliente acha que o inversor é 10 kW” deveria ficar com confiança/proveniência e ser substituível.

### O que os exemplos `memory_agents` realmente mostram

Os exemplos Agno/Memori/Strands confirmam a viabilidade de armazenamento persistente em SQL, separando memória de histórico/sessão, mas **não encontrei neles uma política de TTL, retenção ou fim de sessão que eu consideraria pronta para produção**. O exemplo Agno separa storage de sessões e user memories; os exemplos Memori usam banco SQL e busca de memória.   O exemplo Strands+Memori também vende “continuidade entre sessões”, mas a semântica de retenção continua sendo essencialmente a do demo.

**Antipadrão atual:** estado `pending`/marca/pergunta anterior no `static data` do workflow, sem TTL e sem durabilidade.

**Aplicado ao nosso caso:** coloque `conversation_session`, `message_event`, `state_transition` e `asset_profile` em Postgres. O backend recebe `session_id` real em todas as chamadas. Mantenha os últimos turnos verbatim + DST estruturado + rolling summary; use query rewriting só para retrieval. Um Redis pode ser cache/lock, nunca a única fonte de verdade.

---

# 2. Roteamento e classificação de intenção

## O que a literatura pré-LLM ainda acerta

Sistemas de **task-oriented dialogue (TOD)** tradicionalmente separavam:

1. NLU / intent classification;
2. entity/slot extraction;
3. Dialogue State Tracking;
4. dialogue policy;
5. NLG.

A chegada dos LLMs não tornou essa decomposição errada. Ela tornou opcional implementar cada etapa como um modelo separado.

Rastogi et al., *Towards Scalable Multi-Domain Conversational Agents: The Schema-Guided Dialogue Dataset* (AAAI 2020), formalizam intents, slots e DST em um esquema extensível. ([AAAI Publicações][8]) Larson et al., *An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction* (EMNLP-IJCNLP 2019), mostram o ponto que continua extremamente relevante: classificadores podem acertar intenções suportadas e ainda ser ruins em reconhecer **out-of-scope (OOS)**. O dataset ficou conhecido como **CLINC150**. ([ACL Anthology][9])

## A fronteira defensável: regra × modelo

Não é “rules versus AI”. São diferentes tipos de decisão:

| Decisão                                              | Mecanismo recomendado |
| ---------------------------------------------------- | --------------------- |
| `phone_number_id → tenant`                           | determinístico        |
| botão/lista `id="open_rma"`                          | determinístico        |
| bloqueio de procedimento perigoso                    | determinístico/policy |
| direitos/restrições comerciais                       | determinístico/policy |
| palavra coloquial “wifi não pega” → monitoring_setup | probabilístico        |
| “Growatt 5kw” → marca/modelo/potência                | extractor + gazetteer |
| frase fora do domínio                                | OOS detector          |
| duas intents igualmente plausíveis                   | clarification         |
| escolher modelo barato/forte                         | model router          |

Por isso, o problema do roteador atual não é ele ser determinístico. O problema é que um **gazetteer first-match** está sendo usado também onde a semântica é probabilística.

### Cascata que eu usaria

```text
1 exact interactive ID
2 hard business/safety rule
3 explicit entity pattern / exact code
4 intent + OOS classifier
5 ambiguity threshold
6 clarification if needed
7 downstream RAG/action route
```

Meça pelo menos **macro-F1**, per-intent recall, OOS AUROC/AUPRC, false in-scope rate, confusion matrix e **expected cost of misrouting**. Um falso “RMA” e um falso “FAQ” podem ter custos diferentes.

### DSPy

Khattab et al., *DSPy: Compiling Declarative Language Model Calls into State-of-the-Art Pipelines* (ICLR 2024), propõem módulos LM parametrizados e otimização contra uma métrica, substituindo tuning artesanal de prompts por **programmatic optimization**. ([ICLR Proceedings][10])

Isto **não** implica substituir código de negócio por um modelo.

O exemplo do `awesome-ai-apps` é ainda mais fraco como evidência para essa troca: o starter usa um pequeno programa DSPy/ReAct; não demonstra um compilador pegando 230 linhas de requisitos e aprendendo uma política equivalente.

**Veredito DSPy:** **ADAPTAR** para query rewrite, classificação fuzzy, geração do verifier, talvez escolha de demonstrações. **DESCARTAR** a ideia de compilar automaticamente IDs de botões, precedência contratual ou regras de segurança.

### RouteLLM

Ong et al., *RouteLLM: Learning to Route LLMs with Preference Data* (ICLR 2025), tratam de **model routing**: escolher entre um LLM forte e um fraco conforme a consulta e o trade-off qualidade/custo. Não é intent routing. Os experimentos reportam reduções de custo superiores a 2× em alguns regimes mantendo qualidade do benchmark. ([ML Anthology][11])

O exemplo do repositório segue exatamente essa ideia: controlador com strong/weak model e threshold.

**Aplicado ao nosso caso:** mantenha uns 20–30% do roteador atual como “contract layer” determinística. Tire o texto livre da cadeia de `if/else` e coloque-o num classificador/OOS benchmarkado. Só depois acrescente RouteLLM, e apenas para decidir qual modelo gera/verifica a resposta.

---

# 3. RAG para suporte técnico e diagnóstico

Para manuais fotovoltaicos, a pergunta correta não é apenas “qual embedding?”. O problema é **structured technical retrieval**.

## Recuperação por tipo de evidência

Um código `E031`, `ARC-FAULT`, `SUN2000-5KTL-L1` ou `MOD 600W` tem alta densidade lexical. Embeddings frequentemente suavizam justamente as diferenças que importam.

O pipeline robusto é:

```text
query
 -> entity resolution
 -> scope restriction
 -> lexical retrieval
 -> dense retrieval
 -> fusion
 -> reranking
 -> evidence assembly
 -> procedural reasoning
```

### Entity resolution antes do retriever

Primeiro normalize:

```text
manufacturer
product_family
model
power_rating
firmware/version
fault_code
country/market
document_type
document_revision
```

Depois aplique **metadata filtering / faceted retrieval**. Se o usuário informou “Fronius Primo 5.0-1”, não faz sentido deixar o dense retriever disputar resultados de toda a base.

### Busca híbrida

**[ESTABELECIDO]** BEIR, de Thakur et al. (NeurIPS Datasets & Benchmarks 2021), consolidou a necessidade de avaliar retrievers em domínios heterogêneos; o benchmark mantém BM25 como baseline forte e evidencia que a melhor estratégia varia por domínio. ([GitHub][12])

Para fundir ranking lexical+denso, **Reciprocal Rank Fusion (RRF)**, de Cormack, Clarke & Büttcher, *Reciprocal Rank Fusion outperforms Condorcet and Individual Rank Learning Methods* (SIGIR 2009), continua sendo uma baseline excelente por não exigir scores calibrados entre retrievers. ([Google Pesquisa][3])

Depois, use um **cross-encoder reranker** ou late interaction. Khattab & Zaharia, *ColBERT* (SIGIR 2020), é a referência canônica para **late interaction**. ([arXiv][13])

## Chunking

O antipadrão clássico aqui é:

```text
PDF -> texto -> chunks de 500 caracteres -> embeddings
```

Para o seu corpus, os chunk types deveriam ser ao menos:

* `fault_code_entry`;
* `procedure`;
* `procedure_step`;
* `warning/caution`;
* `specification_table`;
* `warranty_clause`;
* `model_compatibility`;
* `paragraph`;
* `figure_caption`.

Cada pedaço deveria carregar `page`, `section`, `table_id`, `model_scope`, `doc_revision` e, idealmente, bbox/proveniência.

Uma tabela de falhas deveria virar algo semelhante a:

```text
FaultCode {
  code,
  product_scope,
  meaning,
  probable_causes[],
  approved_actions[],
  stop_conditions[],
  hazard_class,
  source_page,
  document_revision
}
```

O LLM fica muito menos livre para inventar uma sequência.

## Procedimento técnico não é texto comum

Para diagnóstico, eu separaria **retrieval** de **procedure execution**. Um procedimento que diz:

1. verificar LED;
2. medir tensão;
3. se X, desligar;
4. caso contrário, executar Y;

deveria ser representado como **typed decision procedure / decision tree**, não apenas como parágrafo no contexto.

Para ações potencialmente perigosas, o modelo deve selecionar entre passos aprovados, e não redigir uma intervenção inédita.

## Embeddings a benchmarkar em português

Não declare vencedor por leaderboard geral. Monte qrels PT-BR locais. Os candidatos tecnicamente razoáveis hoje incluem:

* **BGE-M3** — dense, sparse e multi-vector, >100 línguas, até 8k tokens; boa escolha para experimento de híbrido. ([BGE Model][14])
* **Qwen3-Embedding / Qwen3-Reranker** — família 2025, multilíngue, tamanhos diferentes para embedding/rerank. A alegação de SOTA vem do fornecedor/autores e precisa ser verificada no corpus local. ([Qwen][15])
* **multilingual-e5** — Wang et al., *Multilingual E5 Text Embeddings: A Technical Report* (Microsoft Research, 2024), treinado sobre 1 bilhão de pares multilíngues. ([arXiv][16])
* **jina-embeddings-v3** — Sturua et al. (preprint 2024), 570M, Task LoRA e contexto longo; novamente, benchmark local. ([arXiv][17])

### pgvector versus Qdrant

O exemplo **Advanced/Production PDF RAG with Reranking** é um dos mais úteis do repositório: parsing de páginas/tabelas/imagens, metadata enrichment, híbrido dense+sparse, RRF, reranking, citações e visualização da página.

Mas isso é evidência para a **arquitetura do pipeline**, não para Qdrant como requisito. Postgres+pgvector pode continuar perfeitamente defensável se:

* Recall@k/nDCG estão bons;
* filtro por metadata não é gargalo;
* volume/latência cabem;
* operacionalmente Postgres é mais simples.

Migrar porque o exemplo usa Qdrant seria **cargo cult architecture**.

## GraphRAG

Edge et al., *From Local to Global: A Graph RAG Approach to Query-Focused Summarization* (Microsoft Research preprint, 2024), atacam especialmente **global sensemaking questions** sobre corpora grandes, construindo grafo de entidades + summaries de comunidades. ([arXiv][18])

Seu caminho crítico é predominantemente:

> modelo exato → código exato → procedimento exato.

Isso favorece índice lexical/estruturado, não GraphRAG.

O demo Neo4j do catálogo extrai entidades/relações genericamente e permite NL→Cypher. É interessante, mas não produz uma ontologia fotovoltaica confiável só porque existe um grafo.

Graph pode fazer sentido posteriormente para relações como:

```text
MODEL --USES_FIRMWARE--> VERSION
MODEL --REPLACED_BY--> MODEL
FAULT_CODE --APPLIES_TO--> FIRMWARE_RANGE
PRODUCT --HAS_WARRANTY--> POLICY
MODULE --COMPATIBLE_WITH--> INVERTER
```

**Aplicado ao nosso caso:** permaneça em pgvector por enquanto. Implemente metadata/entity scoping + BM25/textual exact-match + dense + RRF + reranker + chunks tipados. Faça GraphRAG só se um conjunto de perguntas relacionais reais mostrar ganho que a estrutura relacional normal do Postgres não resolve.

---

# 4. Fidelidade, abstenção e calibração

Essa é a área em que eu seria mais conservador porque uma resposta incorreta pode recomendar intervenção elétrica inadequada.

## Termos corretos

**Groundedness**, **faithfulness**, **citation correctness**, **hallucination detection**, **uncertainty estimation**, **calibration**, **selective prediction**, **selective classification**, **reject option**, **risk–coverage trade-off**, **conformal prediction / conformal risk control** e **abstention**.

### Não existe uma única “confidence”

Eu separaria sinais:

```text
retrieval_support
entity_completeness
retrieval_margin
out_of_scope_score
claim_verifier_result
citation_coverage
cross-source_contradiction
procedure_match
safety_class
dialogue_loop_count
```

A decisão final é uma policy:

```text
ANSWER
CLARIFY
HANDOFF
```

Não:

```text
llm_confidence > 0.72
```

### Evidência

Geifman & El-Yaniv, *Selective Classification for Deep Neural Networks* (NeurIPS 2017), formalizam o **reject option** e o trade-off entre risco e cobertura. ([NeurIPS Proceedings][4]) Isso é muito mais próximo do problema de suporte técnico que “pedir ao modelo uma porcentagem de confiança”.

Angelopoulos et al., *Conformal Risk Control* (ICLR 2024), generalizam conformal prediction para controle de perdas monotônicas. É **[PROMISSOR]** para obter limites auditáveis em subsistemas bem definidos, mas não autoriza afirmar “95% de segurança” sobre uma resposta RAG aberta sem definir score, loss, calibration set e suposições de distribuição. ([ICLR Proceedings][19])

Farquhar et al., *Detecting Hallucinations in Large Language Models Using Semantic Entropy* (Nature 2024), mostram **semantic entropy** como sinal útil para certas confabulações. É mais um feature potencial, não um safety oracle. ([Nature][20])

Para RAG, Es et al., *RAGAs* (EACL 2024) separam relevância do contexto, uso fiel do contexto e qualidade da geração. ([ACL Anthology][21]) Saad-Falcon et al., *ARES* (NAACL 2024), usam judges leves + dados sintéticos + um pequeno conjunto humano para context relevance, answer faithfulness e answer relevance. ([ACL Anthology][22])

## “Trustworthy RAG” do catálogo

O código é útil porque decompõe resposta em claims, verifica evidência/citação e classifica algo como `SUPPORTED`, `PARTIAL`, `UNSUPPORTED` ou `CONTRADICTED`. Porém, o *trust score* é uma combinação heurística, incluindo confiança gerada pelo próprio modelo.

**Adotar:** claim decomposition, source attribution, contradiction flag.

**Não adotar como safety mechanism:** considerar o número retornado um probability estimate calibrado.

## Um gate auditável

Exemplo de policy inicial:

| Condição                                               | Decisão         |
| ------------------------------------------------------ | --------------- |
| safety class alto + evidência incompleta               | HANDOFF         |
| brand/model não confirmado e resposta depende deles    | CLARIFY         |
| código exato não existe em documentos permitidos       | HANDOFF/UNKNOWN |
| evidência contraditória entre versões de manual        | HANDOFF         |
| retrieval bom, todas as claims suportadas, risco baixo | ANSWER          |
| 2 clarificações sem progresso                          | HANDOFF         |

Depois escolha os thresholds no conjunto de validação para uma meta como:

> “Entre as respostas automáticas de alta criticidade que realmente emitimos, erro técnico grave < X%, aceitando reduzir cobertura.”

A métrica é **risk–coverage curve**, não simplesmente accuracy.

---

## WFGY 16-Problem Map

O exemplo solicitado expõe os 16 rótulos seguintes. Importante: **isso é uma taxonomia comunitária/open-source de diagnóstico, não uma taxonomia acadêmica validada nem um benchmark de segurança**. Use-a como checklist de engenharia, não como evidência científica.

| #  | WFGY mode                     |        Exposição de vocês | Leitura prática                                      |
| -- | ----------------------------- | ------------------------: | ---------------------------------------------------- |
| 1  | Hallucination and chunk drift |                  **Alta** | recupera manual vizinho/modelo errado                |
| 2  | Interpretation collapse       |                  **Alta** | manual certo, interpretação/procedimento errado      |
| 3  | Long reasoning chains         |                     Média | diagnóstico longo pode degradar                      |
| 4  | Bluffing and overconfidence   |                  **Alta** | procedimento inventado com linguagem segura          |
| 5  | Semantic ≠ embedding          |                  **Alta** | códigos/modelos exatos são caso clássico             |
| 6  | Logic collapse and recovery   |                     Média | fluxo cai em estado sem recuperação                  |
| 7  | Memory breaks across sessions |             **Já ocorre** | continuidade atual é simulada                        |
| 8  | Debugging as a black box      |                  **Alta** | sem trace de trajetória, difícil localizar regressão |
| 9  | Entropy collapse              |               Baixa–média | menos central em chats curtos                        |
| 10 | Creative freeze               |                     Baixa | criatividade não é objetivo                          |
| 11 | Symbolic collapse             |               Baixa–média | relevante a regras de garantia/compliance            |
| 12 | Philosophical recursion       |               Irrelevante | não é caso de uso                                    |
| 13 | Multi-agent chaos             |                Baixa hoje | sobe se adotarem multiagentes                        |
| 14 | Bootstrap ordering            |                     Média | ordem de inicialização/configuração                  |
| 15 | Deployment deadlock           |                     Média | filas, espera humana, side effects                   |
| 16 | Pre-deploy collapse           | **Alta operacionalmente** | mudanças de prompt/model/schema não testadas         |

**Aplicado ao nosso caso:** implemente uma matriz de decisão de abstenção offline e versionada. Toda mudança de threshold deve produzir curva risk–coverage e confusion matrix `ANSWER/CLARIFY/HANDOFF` num conjunto congelado de produção. Em alta tensão/risco pessoal, use hard policy + procedimento aprovado; não deixe um verifier LLM “liberar” conteúdo novo.

---

# 5. Humano no loop e transferência

Há duas coisas diferentes chamadas **human-in-the-loop**:

1. **human approval** de uma ação;
2. **ownership transfer / escalation** da conversa.

O segundo é o que suporte precisa.

## O que um handoff verdadeiro contém

O padrão é parecido com uma **Saga** ou workflow durável:

```text
BOT_ACTIVE
   |
request_handoff
   v
HANDOFF_PENDING
   |
external system ACK + ticket_id
   v
HANDOFF_ACKNOWLEDGED
   |
agent assigned
   v
HUMAN_ACTIVE
   |
resolve
   v
RESOLVED
```

Se criação/ACK falhar:

```text
HANDOFF_FAILED
```

e o usuário recebe uma mensagem verdadeira sobre isso.

### O antipadrão concreto encontrado no repositório

No **Customer Support Resolution Agent**, a ferramenta de ticket do demo grava um JSON local e retorna linguagem equivalente a uma promessa de acompanhamento humano. Isso é uma demonstração útil de interface, mas **não é uma transferência operacional de atendimento**.

Esse padrão é perigoso em produção:

> “Encaminhei seu caso para nossa equipe.”

quando nenhuma equipe foi notificada.

Chame isso de **false handoff / phantom escalation**.

## Pacote de contexto para o humano

Não entregue só o transcript completo. Entregue:

```text
reason_for_escalation
safety_flags
active_intent
confirmed manufacturer/model/serial/firmware
fault_code
user_goal
steps_already_attempted
observations
retrieved_evidence + page citations
media references
bot's unresolved question
conversation summary
full transcript link
```

O resumo deve ser derivado do transcript, mas campos críticos como serial/código precisam vir de dados estruturados e manter provenance.

## Critérios de escalada

Além de baixa confiança:

* risco elétrico/segurança;
* pedido fora do procedimento publicado;
* garantia/RMA que cria compromisso comercial;
* conflito entre manuais;
* usuário relata dano físico/fumaça/aquecimento;
* OOS persistente;
* loop improdutivo;
* duas ou três tentativas sem avanço;
* frustração explícita;
* pedido explícito de humano;
* falha operacional do bot;
* necessidade de mídia que o pipeline não consegue interpretar.

### “Detecção de frustração”

Use com moderação. Um sentiment classifier não deveria ser o único gatilho. Regras operacionais simples são frequentemente melhores:

```text
same issue repeated >= 2
clarification count >= 2
negative feedback
explicit "atendente", "humano", "ninguém resolve"
session duration / turn count
```

## Frameworks com HITL realmente útil

No estado atual de 2026:

* **LangGraph**: checkpointer + `interrupt()` grava estado e pode aguardar indefinidamente; a documentação recomenda persistent checkpointer, inclusive Postgres, em produção. ([Docs by LangChain][23])
* **OpenAI Agents SDK**: `RunState` serializável é uma fronteira durável de pause/resume; há approvals e persistência de run state. ([OpenAI][24])
* **AWS Strands**: `HumanInTheLoop` + session manager para stateless deployments. ([Strands Agents SDK][25])
* **Microsoft Agent Framework**: estado de sessão, workflows e Durable Extension para checkpoint/recovery distribuído e HITL. ([Microsoft Learn][26])

Esses mecanismos ainda precisam ser integrados ao sistema real de tickets. Um `interrupt()` não notifica um atendente sozinho.

**Aplicado ao nosso caso:** faça o handoff primeiro como workflow explícito em Postgres/outbox + sistema real de atendimento. Depois decida se LangGraph/Temporal/Microsoft Durable gerenciam a espera. Nunca deixe o LLM emitir a frase de sucesso antes de `external_ticket_id` estar persistido.

---

# 6. Multimodal aplicado a campo

Há dois problemas diferentes:

1. **scene text**: foto de plaqueta/display em ambiente real;
2. **document AI**: PDF escaneado de fabricante.

Eles não deveriam usar necessariamente o mesmo pipeline.

## Foto de plaqueta/display

TextOCR, Singh et al. (CVPR 2021), foi criado justamente porque OCR em texto arbitrário no mundo real é difícil; possui cerca de 900 mil palavras anotadas em imagens reais. ([OpenAccess CVF][27])

O pipeline de produção deveria começar antes do OCR:

```text
media ingestion
 -> blur/noise/glare check
 -> orientation
 -> perspective rectification
 -> region detection/crop
 -> contrast/denoise if useful
 -> OCR with bbox + confidence
 -> typed extraction
 -> domain validation
 -> VLM arbitration/fallback
 -> user confirmation
```

### OCR clássico versus VLM

**OCR clássico/especializado ainda vence quando:**

* região de texto já foi localizada;
* fonte/display é previsível;
* alto contraste;
* você precisa de bbox/confiança caractere a caractere;
* volume é alto;
* latência/custo precisam ser pequenos;
* serial exige reproducibilidade.

**VLM/document VLM ganha quando:**

* layout é irregular;
* a foto tem múltiplos campos e você quer interpretação;
* precisa entender “qual texto corresponde ao campo MODEL?”;
* o documento possui tabela/gráfico;
* OCR clássico produziu resultado ambíguo.

Por isso eu faria **cascade**, não VLM-only.

### Validação de domínio é indispensável

Se o OCR lê:

```text
SN: A8O5O13
```

você pode ter confusão `O/0`, `I/1`, `S/5`.

Valide com:

* regex de fabricante;
* prefixos conhecidos;
* catálogo de modelos;
* tamanho esperado;
* checksums quando existirem;
* consistência entre modelo e potência;
* segunda leitura/crop;
* confirmação humana.

Para `serial_number`, **exact field accuracy** é mais importante que BLEU ou “parece correto”.

## PDF escaneado

Mathew et al., *DocVQA* (WACV 2021), mostram que questões dependentes da estrutura documental são significativamente mais difíceis que texto linear. ([OpenAccess CVF][28]) LayoutLMv3, Huang et al. (ACM Multimedia 2022), é um trabalho canônico de multimodal Document AI combinando texto e imagem/layout. ([DOI][29])

Entre ferramentas atuais:

* **Docling** — Auer et al., *Docling Technical Report* (2024): layout analysis + TableFormer, open source, execução local; é technical report, não estudo independente. ([arXiv][30])
* **PaddleOCR-VL-0.9B** — documentação/projeto reporta 109 línguas, incluindo português, e parsing de texto/tabela/fórmula/gráfico. É **[PROMISSOR]**, especialmente pelo tamanho, mas as alegações de SOTA são dos autores/fornecedor e precisam ser verificadas no seu PDF. ([GitHub][31])
* **ColPali**, Faysse et al. (ICLR 2025), introduz recuperação diretamente de imagens de páginas e o benchmark **ViDoRe**, evitando depender integralmente de OCR/text extraction para visual document retrieval. É especialmente interessante para manuais visuais. ([ICLR Proceedings][32])

## Exemplos do repositório

O **Gemma OCR** transforma páginas em imagens e usa VLM para obter texto/tabelas; bom protótipo, mas não oferece por si só bbox/confiança auditável.

O **NVIDIA Nemotron-Nano OCR** do catálogo converte PDF em páginas e as envia como imagem para `nvidia/Nemotron-Nano-V2-12b` via Nebius, retornando conteúdo estruturado. Isso demonstra pipeline e integração; não demonstra precisão de serial, português de campo ou segurança em produção.

## Benchmark específico que eu faria

100–300 amostras reais, separadas:

| Dataset local              | Métrica primária             |
| -------------------------- | ---------------------------- |
| plaqueta boa               | exact field accuracy         |
| plaqueta ruim/glare        | exact field accuracy         |
| display sete segmentos/LCD | exact code accuracy          |
| serial                     | full-string exact match      |
| manual scan                | CER/WER + structure accuracy |
| tabela                     | cell/row structure accuracy  |
| páginas RAG                | downstream Recall@k          |

Compare pelo menos classical OCR/PaddleOCR + PaddleOCR-VL + um VLM geral/Nemotron/Gemma, registrando **latência e custo por página/foto**.

**Aplicado ao nosso caso:** a mudança imediata é não perder o media event. Persista `media_id`, hash, tipo e object URI; execute um pipeline de OCR/visão e associe a extração ao mesmo `message_event`. Serial/modelo com baixa confiança deve ser mostrado ao usuário para confirmação antes de influenciar diagnóstico.

---

# 7. Avaliação

Seu agente é metade máquina de estados e metade RAG. Portanto uma métrica única de “answer quality” é conceitualmente errada.

## Pirâmide de avaliação

### 1. Contract/routing tests

Para cada botão/lista:

```text
interactive_id -> expected deterministic route
```

Deveria ser teste unitário 100% determinístico.

Para texto livre:

* intent macro-F1;
* per-class recall;
* OOS false acceptance;
* entity exact match/F1;
* slot completeness;
* clarification accuracy.

### 2. Retrieval

Monte **qrels** para perguntas reais.

Métricas canônicas:

* Recall@k;
* Precision@k;
* MRR;
* nDCG@k;
* exact document/page recall;
* fault-code retrieval accuracy.

Faça **component ablations**:

```text
lexical only
dense only
lexical+dense
+ metadata filters
+ query rewrite
+ reranker
```

Isso responde se Qdrant, outro embedding ou reranker realmente agregam.

### 3. Generation/fidelity

* claim supportedness;
* citation precision;
* citation recall/coverage;
* answer relevance;
* procedure-step correctness;
* forbidden-step rate;
* contradiction rate;
* abstention correctness.

RAGAs e ARES são bons frameworks conceituais para decomposição, mas não substituem ground truth humano técnico. ([ACL Anthology][21])

### 4. Dialogue trajectory

Termos: **trajectory evaluation**, **task success**, **dialogue state accuracy**, **joint goal accuracy**, **turn-level evaluation**.

AgentBench, Liu et al. (ICLR 2024), é uma referência geral para avaliar agentes em ambientes interativos. ([ICLR Proceedings][33]) Mais próximo do seu problema, **τ²-Bench** modela ambientes de suporte em que tanto agente quanto usuário alteram o estado — “dual-control”; telecom troubleshooting é uma analogia muito melhor a diagnóstico fotovoltaico que QA estático. ([Hugging Face][34]) A revisão **τ²-Bench-Verified** de 2026 também é instrutiva porque expõe o quanto erros no próprio benchmark podem distorcer conclusões. ([GitHub][35])

Métricas locais:

```text
resolved_without_human
correct_handoff
turns_to_resolution
clarification_turns
unproductive_loop_rate
wrong_route_rate
recontact_within_N_days
unsafe_recommendation_rate
```

### 5. Operacional

```text
p50/p95/p99 end-to-end latency
retrieval latency
model TTFT
cost per turn
cost per resolved conversation
tokens per resolved conversation
duplicate webhook rate
outbound failure rate
handoff acknowledgement latency
```

## LLM-as-a-judge

Liu et al., *G-Eval* (EMNLP 2023), mostra correlação útil com julgamento humano, mas os próprios autores apontam viés em favor de texto gerado por LLM. ([ACL Anthology][36]) O trabalho *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* também documenta position/verbosity/self-enhancement biases.

Conclusão: **[ESTABELECIDO]** judges ajudam a escalar; **não** devem ser o único oracle.

Use:

* judge blinded;
* ordem randomizada em pairwise;
* rubric extremamente específica;
* amostra humana periódica;
* especialistas humanos no subset safety-critical;
* métricas determinísticas sempre que possível.

## Português brasileiro

Não traduza um benchmark inglês e declare validade.

Construa um **golden set PT-BR originário do tráfego brasileiro**, incluindo:

* abreviações;
* erros ortográficos;
* “kw”, “kva”, “5k”;
* marca escrita foneticamente;
* foto ruim;
* pergunta incompleta;
* alternância PT/termo inglês do manual;
* códigos de erro;
* instalador versus consumidor leigo.

Você pode usar datasets ingleses para metodologia, não para estimar a qualidade operacional em português.

## OpenTelemetry versus LangSmith

Minha recomendação é **OpenTelemetry como telemetry contract**, com LangSmith como consumer/backend.

O próprio LangSmith hoje aceita traces OpenTelemetry de aplicações não-LangChain e consegue executar avaliação sobre esses traces. Também suporta fan-out para outros destinos. ([Docs by LangChain][37])

Então instrumente spans como:

```text
conversation
 route
 intent_classify
 entity_extract
 retrieval
 rerank
 generate
 verify_claims
 selective_gate
 handoff
 whatsapp_send
```

No mínimo grave `trace_id`, `session_id`, versões de prompt/model/embedding/index e IDs de evidência. Evite mandar telefone, serial e imagens sem política explícita de redaction/retention.

### Exemplo Okahu/Monocle do catálogo

O demo Temporal Transaction Agent instrumenta com Monocle→OpenTelemetry, mantém asserts determinísticos e avaliações LLM sobre traces, e consegue provocar uma regressão de prompt para verificar se os testes ficam vermelhos. Isso é um padrão de alto valor para vocês.

A parte “coding agent corrige sozinho até ficar verde” é demo interessante, mas eu **não** usaria auto-fix sem revisão para lógica de suporte elétrico.

**Aplicado ao nosso caso:** antes de qualquer migração de arquitetura, monte aproximadamente 200–500 casos PT-BR com strata de risco. Um release só passa se não regredir contratos determinísticos, retrieval, safety/abstention e trajectory. LangSmith pode continuar; desacople a instrumentação dele via OTel.

---

# 8. Engenharia de custo e latência

## Pense por conversa resolvida

A métrica correta não é apenas `$ / 1M tokens`.

Use:

```text
cost_per_resolved_conversation
tokens_per_resolved_conversation
LLM_calls_per_resolution
strong_model_calls_per_resolution
p95_time_to_resolution
```

Um modelo barato que exige três clarificações pode ser mais caro que um modelo forte em um turno.

## Cascata recomendada

```text
0. deterministic rule             ~no LLM cost
1. small classifier/extractor     low cost
2. retrieval/rerank
3. cheap generator                low-risk grounded cases
4. strong model                   complex synthesis
5. human                          unsafe/unsupported
```

### FrugalGPT e RouteLLM

Chen, Zaharia & Zou, *FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance* (TMLR 2024), estudam seleção/cascata entre serviços e reportam reduções muito grandes em alguns datasets — até 98% em condições experimentais específicas. Isso não é um número a transferir para produção, mas sustenta o princípio de **LLM cascades**. ([ML Anthology][38])

RouteLLM adiciona um learned router strong/weak. ([ML Anthology][11])

## Prompt/prefix caching

Gim et al., *Prompt Cache: Modular Attention Reuse for Low-Latency Inference* (MLSys 2024), formalizam reutilização de attention states para prefixos recorrentes e mostram reduções grandes de TTFT em seu protótipo. ([Proceedings ML Sys][39])

Seu caso tem excelentes candidatos a prefix caching:

* instrução base;
* estilo WhatsApp;
* policy de segurança;
* schema de output;
* descrições de ferramentas.

## Semantic cache

**[PROMISSOR, MAS PERIGOSO AQUI]**.

“erro 31 no inversor A” e “erro 31 no inversor B” podem ter embeddings próximos e procedimentos diferentes.

Se usar semantic cache:

```text
tenant
manufacturer
model family
firmware scope
intent
normalized query
knowledge-base version
prompt version
model version
```

devem entrar no escopo/chave. Eu começaria por **exact cache** de conteúdos imutáveis e só depois testaria cache semântico.

## SLO de produto

Não há SLO acadêmico universal para WhatsApp. Como alvo de engenharia eu usaria inicialmente:

| Métrica             |      Alvo inicial |
| ------------------- | ----------------: |
| p50 resposta normal |             2–4 s |
| p95                 |           <8–10 s |
| p99                 |             <15 s |
| roteamento/entity   | <300 ms desejável |
| retrieval+rerank    |    <1 s desejável |

Esses números são **objetivos de produto propostos**, não resultados da literatura.

Para uma resposta de 30 segundos, mesmo que “correta”, a UX conversacional já se deteriora fortemente. Evite pipelines sequenciais com três ou quatro LLMs grandes quando verificações independentes puderem rodar em paralelo ou ser executadas seletivamente.

**Aplicado ao nosso caso:** não introduza RouteLLM antes de medir `strong_model_call_rate`. Primeiro elimine chamadas LLM desnecessárias via contratos determinísticos, classificador pequeno e entity resolution. Depois roteie somente a geração/verificação entre modelos.

---

# 9. Restrições do canal WhatsApp

## A janela de 24 h não é a sessão do agente

A documentação Meta reproduzida em sua coleção oficial Postman distingue a janela de conversação/pricing da **rolling customer support window**: a última é atualizada pela mensagem do usuário; fora dela uma mensagem business-initiated precisa usar template. ([Postman][40])

Isso responde diretamente à questão A:

```text
dialogue session != WhatsApp service window
```

Um incidente pode terminar em 20 min enquanto a janela WhatsApp continua aberta. E um caso de RMA pode continuar por dias, atravessando várias janelas de canal.

## Idempotência

O endpoint de mensagens é por `Phone-Number-ID`; uma resposta bem-sucedida retorna um ID `wamid`, usado para acompanhar status. Respostas contextuais usam `context.message_id`. ([Postman][41])

Faça:

```text
UNIQUE(phone_number_id, inbound_wamid)
```

antes de executar qualquer side effect.

Para outbound, use **transactional outbox**:

```text
DB transaction:
  state transition
  create outbound_message/outbox record
COMMIT

worker:
  send WhatsApp
  persist outbound wamid
  consume status webhook
```

Assim retry não duplica logicamente a transição.

## Botões versus listas

O valor arquitetural do menu não é “mais bonito”; é reduzir **semantic entropy** no roteamento.

* poucas alternativas estáveis → reply buttons;
* conjunto maior estruturado → list;
* problemas não previstos → sempre mantenha free-text escape hatch.

Mais importante: use **interactive IDs como contratos**, não o texto visível do botão.

O limite de tamanho que vocês já respeitam — 1024 no corpo interativo e 4096 no texto — faz parte do desenho fornecido.

## “Menu aumenta resolução?”

Não encontrei evidência séria que justifique um número universal de ganho em FCR para o seu domínio. Essa é uma pergunta de experimento local.

A/B:

```text
A: free text first
B: structured first menu
```

e medir:

```text
correct_route_rate
resolution_rate
time_to_resolution
turn_count
menu_abandonment
free_text_fallback_rate
recontact_rate
```

O menu provavelmente ajuda em intenções claramente enumeráveis; pode piorar experiência em diagnóstico complexo.

## Mídia no webhook

Uma mensagem pedindo foto e depois descartando a foto é um **broken conversational affordance**: o bot dá ao usuário uma ação cuja semântica o backend não implementa. Isso deve ser tratado como erro funcional, não backlog multimodal opcional.

**Aplicado ao nosso caso:** mantenha a janela de 24 h num campo `service_window_expires_at` do canal, separado de `conversation_session.expires_at`. Deduplicate por `wamid`, use outbox para envio/status e mantenha IDs estruturados do WhatsApp no contrato determinístico.

---

# 10. Tecnologias, modelos e conceitos emergentes que realmente mudam decisões

## MCP

A especificação MCP de 28 de julho de 2026 tornou o core do protocolo explicitamente **stateless** e adicionou extensões, Multi Round-Trip Requests, melhorias de routing/auth etc. ([Model Context Protocol Blog][42])

Isso reforça a resposta:

> Expor seu RAG como MCP melhora interoperabilidade; **não cria memória, fidelidade ou durabilidade**.

É útil se amanhã o mesmo serviço de conhecimento precisar ser consumido por:

```text
WhatsApp agent
internal support copilot
IDE assistant
field technician mobile app
third-party agent runtime
```

Aí MCP pode substituir APIs/tools proprietários por uma interface comum.

Se só o FastAPI atual consome o RAG, é principalmente reembalagem.

**Veredito:** **ADAPT quando houver dois ou mais clientes heterogêneos; não fazer como projeto de qualidade de RAG.**

## Small specialized models

Para 31 intents + OOS + entidades, eu testaria **antes de LoRA generativo**:

* encoder multilíngue + classification head;
* SetFit/few-shot sentence-transformer;
* lightweight cross-encoder;
* distillation de um LLM forte para labels;
* regras/gazetteer como features ou overrides.

Por quê? O output é pequeno, fechado e facilmente avaliado. Um LLM generativo fine-tuned é mais caro operacionalmente e aumenta superfície de comportamento.

Os exemplos de fine-tuning/LoRA do catálogo demonstram que o pipeline existe, mas não constituem evidência de que LoRA seja melhor que classificação discriminativa para 31 labels. O benchmark local deve decidir.

## Visual retrieval sem OCR

**ColPali/ViDoRe** é uma das mudanças mais interessantes desde os pipelines “OCR tudo primeiro”: recuperar a página diretamente por representação visual pode ser útil em manual com diagrama, tabela e layout. ([ICLR Proceedings][32])

Eu testaria como **segunda retrieval lane**, não substituição imediata da representação textual. Texto continua melhor para códigos exatos e citações.

## Durable agent runtimes

Essa área mudou materialmente.

**LangGraph** tem persistence/checkpoints/HITL/fault recovery de primeira classe. ([Docs by LangChain][23])

**Microsoft Agent Framework**, atualmente o sucessor direto de AutoGen + Semantic Kernel segundo a própria Microsoft, acrescenta workflows e estado robusto para cenários long-running/HITL; a Durable Extension roda sobre Durable Task para recuperação entre workers distribuídos. ([Microsoft Learn][26])

**OpenAI Agents SDK** agora possui sessions, HITL e `RunState` serializável. ([OpenAI][43])

**AWS Strands** possui HITL interrupt/resume e pode combinar isso com session manager para deploy stateless. ([Strands Agents SDK][25])

Para um greenfield Microsoft stack em 2026, eu avaliaria **Agent Framework**, não iniciaria um projeto novo em Semantic Kernel Agents simplesmente por familiaridade: a própria documentação o chama de sucessor direto de Semantic Kernel e AutoGen. ([Microsoft Learn][26])

### Ranking para o seu requisito de estado + interrupção humana

| Framework/runtime                    | Estado                                  | HITL                      | Durabilidade longa      | Fit                      |
| ------------------------------------ | --------------------------------------- | ------------------------- | ----------------------- | ------------------------ |
| LangGraph + Postgres                 | forte                                   | forte                     | boa                     | **alto**                 |
| Temporal + código próprio/PydanticAI | excelente                               | explícito                 | **excelente**           | **alto se long-running** |
| Microsoft Agent Framework Durable    | forte                                   | forte                     | **excelente**           | alto                     |
| AWS Strands + durable session store  | forte                                   | forte                     | boa                     | alto                     |
| OpenAI Agents SDK + DB               | forte                                   | forte                     | boa                     | alto                     |
| Google ADK                           | Session/State/Memory explícitos         | disponível no ecossistema | depende backend         | bom                      |
| Agno + DB                            | sessões/memória                         | pause/resume              | boa                     | bom                      |
| Mastra                               | snapshots/suspend-resume                | bom                       | boa                     | bom para TS              |
| CrewAI/smolagents                    | não é onde eu apostaria nesse requisito | variável                  | não diferencial central | baixo                    |

Não escolham framework por número de features. Escolham depois de um teste:

> “interrompa uma conversa, mate todos os processos, faça deploy de nova réplica e retome exatamente do estado anterior sem repetir side effects.”

## Temporal

Temporal não é “mais um agent framework”; é **durable execution**.

Use quando precisar:

* aguardar horas/dias;
* retry de APIs externas;
* timers/SLA;
* signals de humano;
* compensações;
* retomar após crash;
* evitar reconstruir manualmente workflow state.

Não é necessário para cada pergunta simples de WhatsApp.

**Aplicado ao nosso caso:** P0 = Postgres para estado. P1 = LangGraph/own state machine para conversas se isso reduzir código. P2 = Temporal ou Microsoft Durable quando handoff/RMA/timers/retries de longa duração mostrarem necessidade real. MCP e GraphRAG ficam atrás disso.

---

# Onde o n8n termina

O limite que eu desenharia é simples.

**n8n continua adequado para:**

```text
webhook ingress
tenant adapter
third-party API calls
notifications
low-risk integrations
backoffice automation
simple event-driven workflows
```

**n8n deixa de ser o lugar ideal para ser a única fonte de verdade de:**

```text
conversation state
durable agent checkpoint
long-running human wait
exactly-once-ish side-effect coordination
session lifecycle
concurrent message serialization
cross-session memory
safety-critical transition policy
```

O **FlowSentinel** do catálogo é interessante para audit trail ao redor de n8n; ele não demonstra que o `static data` do n8n deva virar state store de agente.

---

# Modelo de dados recomendado

Eu começaria por algo deste gênero:

```text
conversation_session
--------------------
session_id UUID PK
tenant_id
phone_number_id
wa_id
status
active_intent
slots JSONB
working_summary
safety_class
version
started_at
last_user_at
last_bot_at
expires_at
closed_at
close_reason

message_event
-------------
event_id UUID PK
tenant_id
phone_number_id
wa_id
wamid
direction
message_type
text
payload_hash
media_asset_id
occurred_at
processing_status

UNIQUE(phone_number_id, wamid)

asset_profile
-------------
asset_id
tenant_id
wa_id
manufacturer
model
serial
power_rating
firmware
confidence
provenance_event_id
valid_from
valid_to

state_transition
----------------
id
session_id
from_state
to_state
trigger
trace_id
occurred_at

handoff_request
---------------
id
session_id
status
reason
severity
external_ticket_id
created_at
ack_at
assigned_at
resolved_at
failure_reason

media_asset
-----------
id
message_event_id
provider_media_id
mime_type
object_uri
sha256
ocr_result JSONB
extracted_fields JSONB
processing_status

outbox
------
id
aggregate_type
aggregate_id
event_type
payload
status
retry_count
next_retry_at
created_at
```

Use **optimistic locking** (`version`) ou lock/advisory lock para serializar mensagens concorrentes da mesma sessão. O `message_event` é append-only. Side effects externos saem por **transactional outbox**.

---

# Leitura do `awesome-ai-apps`

Código de exemplo aqui deve ser tratado como **demonstração**, não como evidência de produção — exatamente como você pediu. Vários demos não definem TTL, concorrência, failure recovery ou retenção; isso é uma informação arquitetural importante, não um detalhe a preencher por suposição.

| Exemplo                            | Resolve                    | Padrão observado                             | Veredito                                                |
| ---------------------------------- | -------------------------- | -------------------------------------------- | ------------------------------------------------------- |
| Letta / Stateful Memory            | memória de longo prazo     | hierarquia de memória no estilo MemGPT       | **ADAPTAR** o conceito, não o runtime necessariamente   |
| Agno Memory Agent                  | sessão + memória           | session storage separado de user memory      | **ADAPTAR**; falta policy de TTL no demo                |
| Memori agents                      | memória SQL                | SQL-backed ingestion/search                  | **ADOTAR/ADAPTAR** ao Postgres existente                |
| AWS Strands + Memori               | continuidade multi-session | persistent memory + memory search            | **ADAPTAR**; lifecycle frouxo                           |
| Engineering Content Agent / Engram | memory retrieval           | records + novelty/use of prior memory        | **IDEIA ÚTIL**, não policy de sessão                    |
| RouteLLM demo                      | custo                      | strong/weak model routing                    | **ADAPTAR depois do business router**                   |
| DSPy starter                       | módulos LM                 | programmatic LM pipeline                     | **ADAPTAR módulos fuzzy; não business rules**           |
| Trustworthy RAG                    | fidelidade                 | claims + citation verifier + heuristic score | **ADOTAR verifier; DESCARTAR score como probabilidade** |
| Agentic Typed RAG                  | output estruturado         | typed answer/provenance                      | **ADAPTAR fortemente**                                  |
| Customer Support Resolution        | escalation                 | local “ticket” demo                          | **DESCARTAR handoff falso; manter trigger**             |
| WFGY debugger                      | debugging taxonomy         | 16 failure labels                            | **USAR COMO CHECKLIST**, não ciência validada           |
| Gemma Document OCR                 | OCR VLM                    | PDF page → image → VLM                       | **BENCHMARKAR**                                         |
| NVIDIA Nemotron OCR                | OCR VLM                    | PDF/image → Nemotron-Nano                    | **BENCHMARKAR**                                         |
| Advanced PDF RAG + Reranking       | RAG produção               | layout + hybrid + RRF + rerank + citation    | **CLONAR PRIMEIRO**                                     |
| GraphRAG Neo4j                     | graph retrieval            | LLM entity graph + Cypher                    | **DESCARTAR no core; PoC para relações**                |
| FlowSentinel                       | audit trail                | n8n + external logging                       | **ADAPTAR audit trail**                                 |
| Temporal + Okahu/Monocle           | trajectory eval            | OTel traces + pytest + LLM graders           | **CLONAR/ADAPTAR**                                      |
| MCP RAG examples                   | interoperabilidade         | RAG exposto como tool/server                 | **SÓ SE houver vários consumidores**                    |
| Fine-tuning support/claims         | especialização             | LoRA/generative fine-tune                    | **BENCHMARKAR contra encoder pequeno primeiro**         |

### Um ponto em que o repositório não sustentou o pedido

Na árvore atual que consegui pesquisar, não apareceu uma implementação inequivocamente separada sob o nome exato **“Prompt Format Benchmark (XML versus JSON versus Markdown)”**. Há referências/context-engineering e arena-style comparisons, mas seria incorreto atribuir um benchmark específico a um arquivo que não pude identificar.

A metodologia de **controlled comparison** continua sendo correta: mesmo input/dataset/model/temperature, variar só o formato e comparar task success, tokens, latency e violations. Mas eu não apresentaria uma conclusão “XML vence JSON” como resultado do catálogo sem a implementação/dados correspondentes.

---

# Protótipos descartáveis — valor de informação por hora

|  Ordem | Protótipo                                           | Pergunta que responde                                       | Valor/hora                   |
| -----: | --------------------------------------------------- | ----------------------------------------------------------- | ---------------------------- |
|  **1** | Advanced PDF RAG + reranking versus pipeline atual  | chunk/layout/hybrid/rerank melhoram retrieval real?         | **Muito alto**               |
|  **2** | OCR bake-off: classical/PaddleOCR-VL/Gemma/Nemotron | qual lê plaqueta, display e PDF PT-BR com menor erro/custo? | **Muito alto**               |
|  **3** | Postgres session + Memori/Agno-style memory         | restart/deploy preserva contexto corretamente?              | **Muito alto**               |
|  **4** | Temporal + Monocle/OTel eval demo                   | trajectory tests e durable pause valem a complexidade?      | Alto                         |
|  **5** | Trustworthy RAG verifier                            | claim verification reduz unsupported answers?               | Alto                         |
|  **6** | small intent/OOS model versus gazetteer             | quanto das 230 linhas pode sair sem regressão?              | Alto                         |
|  **7** | RouteLLM replay                                     | dá economia real no mix de perguntas?                       | Médio                        |
|  **8** | DSPy optimization                                   | otimiza submódulos depois que dataset existe?               | Médio                        |
|  **9** | Neo4j GraphRAG                                      | relações cross-document justificam graph layer?             | Baixo hoje                   |
| **10** | MCP wrapper                                         | há ganho operacional de interop?                            | Baixo sem segundo consumidor |

O ponto mais importante é a ordem: **DSPy, RouteLLM e GraphRAG têm pouco valor informacional enquanto vocês ainda não possuem um conjunto de avaliação local capaz de dizer se houve regressão**.

---

# Antipadrões encontrados no desenho atual

| Antipadrão                                        |     Está presente? | Correção                   |
| ------------------------------------------------- | -----------------: | -------------------------- |
| **Volatile conversation state**                   |            **Sim** | Postgres                   |
| **Channel window = dialogue session**             | risco de acontecer | separar relógios           |
| **Query rewriting as memory**                     |            **Sim** | history + DST + summary    |
| **First-match keyword routing for all NLU**       |       parcialmente | hybrid cascade             |
| **LLM self-confidence as probability**            |  risco no verifier | calibration/selective gate |
| **Embedding-only lookup for identifiers**         |          potencial | lexical + metadata         |
| **Structure-agnostic chunking**                   |           provável | layout/typed ingestion     |
| **Silent media discard**                          |            **Sim** | media pipeline             |
| **Phantom human escalation**                      |     precisa evitar | external ACK               |
| **Answer-only evaluation**                        |    **Sim/parcial** | trajectory evaluation      |
| **English benchmark = PT-BR validity**            |     precisa evitar | local gold set             |
| **Framework/vector DB migration before eval**     |     precisa evitar | ablation first             |
| **Agentic workflow where ordinary code suffices** |     precisa evitar | deterministic functions    |

A própria Microsoft agora formula uma regra surpreendentemente boa em sua documentação do Agent Framework: se você consegue escrever uma função para resolver aquela etapa, use a função em vez de um agente. ([Microsoft Learn][26]) É particularmente apropriado para suporte técnico safety-sensitive.

---

# Consenso, promissor e hype

**[ESTABELECIDO]** para este caso: DST e slots explícitos; estado persistente externo; sessões por lifecycle/inactivity; busca híbrida; filtros de metadata; lexical para códigos; reranking; proveniência; reject option; transactional handoff; idempotência de webhook; trajectory testing.

**[PROMISSOR]**: memory consolidation automática; Conformal Risk Control adaptado a gates de RAG; ColPali/visual retrieval; VLM OCR end-to-end; learned strong/weak model routing; LLM judges; pequenos modelos especializados derivados de LLMs.

**[HYPE/SEM EVIDÊNCIA SUFICIENTE PARA VOCÊS AGORA]**: multiagente genérico; GraphRAG para lookup de código de falha; MCP como melhoria de qualidade; generative LoRA substituindo IDs/regras de negócio; trocar pgvector por Qdrant porque um demo usa Qdrant; “trust score 0.91” produzido por LLM como safety probability.

---

# Sequência de implantação que minimiza risco

Eu faria a evolução em seis incrementos:

1. **Durable state foundation:** Postgres session/event/outbox/media/handoff, dedupe `wamid`, sem mudar o RAG.
2. **Eval harness:** golden set PT-BR + route contracts + retrieval qrels + safety/abstention + OTel.
3. **Hybrid router:** exact rules + intent/OOS/entities + clarification; shadow mode primeiro.
4. **RAG v2:** structured ingestion, entity filter, lexical+dense, RRF, reranker, typed procedures.
5. **Selective answer/handoff:** calibrar `ANSWER/CLARIFY/HANDOFF`, ticket ACK real.
6. **Multimodal + durable long-running:** OCR/VLM; Temporal/Microsoft Durable somente onde RMA/humano/timers justificarem.

Essa ordem é importante: ela cria o sistema de medição **antes** de substituir componentes.

---

# Vocabulário técnico em inglês para pesquisa futura

### Eixo 1 — sessão e memória

`conversation session lifecycle`, `idle session timeout`, `dialogue state tracking`, `working memory`, `episodic memory`, `semantic memory`, `profile memory`, `cross-session memory`, `memory consolidation`, `memory retrieval`, `progressive summarization`, `rolling summary`, `long-term conversational memory`, `memory write policy`, `memory retention policy`, `temporal memory retrieval`, `session decomposition`.

### Eixo 2 — roteamento

`task-oriented dialogue`, `intent classification`, `out-of-scope detection`, `open-set intent classification`, `semantic routing`, `cascaded routing`, `hybrid router`, `slot filling`, `entity extraction`, `dialogue policy`, `ambiguity detection`, `clarification question`, `model routing`, `cost-aware routing`, `selective classification`.

### Eixo 3 — RAG

`hybrid retrieval`, `lexical retrieval`, `BM25`, `dense retrieval`, `metadata filtering`, `faceted retrieval`, `entity-aware retrieval`, `Reciprocal Rank Fusion`, `cross-encoder reranking`, `late interaction retrieval`, `ColBERT`, `layout-aware chunking`, `table retrieval`, `structured retrieval`, `document provenance`, `procedural RAG`, `decision-tree execution`, `visual document retrieval`, `GraphRAG`.

### Eixo 4 — fidelidade/abstenção

`groundedness`, `faithfulness`, `citation correctness`, `claim verification`, `hallucination detection`, `uncertainty estimation`, `confidence calibration`, `selective prediction`, `reject option`, `risk-coverage curve`, `conformal prediction`, `conformal risk control`, `abstention`, `semantic entropy`.

### Eixo 5 — humano

`human-in-the-loop`, `human handoff`, `ownership transfer`, `escalation policy`, `durable human approval`, `conversation handover`, `handoff context packet`, `transactional outbox`, `saga pattern`, `dead-letter queue`, `loop detection`, `agent takeover`.

### Eixo 6 — multimodal

`scene text recognition`, `document AI`, `visual document understanding`, `OCR confidence`, `text detection bounding boxes`, `perspective rectification`, `glare detection`, `document layout analysis`, `table structure recognition`, `multimodal document parsing`, `vision-language OCR`, `visual retrieval`, `ColPali`, `ViDoRe`.

### Eixo 7 — avaliação

`offline evaluation`, `online evaluation`, `trajectory evaluation`, `task success`, `joint goal accuracy`, `retrieval qrels`, `Recall@k`, `MRR`, `nDCG`, `citation precision`, `citation recall`, `LLM-as-a-judge bias`, `pairwise evaluation`, `adversarial evaluation`, `red teaming`, `agent benchmark`, `dual-control benchmark`, `OpenTelemetry GenAI tracing`.

### Eixo 8 — custo/latência

`LLM cascade`, `model routing`, `difficulty routing`, `prompt caching`, `prefix caching`, `semantic cache`, `knowledge cache invalidation`, `speculative decoding`, `distillation`, `token budget`, `time to first token`, `cost per resolved conversation`, `latency budget`.

### Eixo 9 — WhatsApp

`customer service window`, `message idempotency`, `webhook deduplication`, `transactional outbox`, `delivery status webhook`, `interactive message ID`, `reply button`, `list message`, `conversation session`, `message correlation ID`, `inbound media processing`.

### Eixo 10 — emergentes

`durable execution`, `durable agent workflow`, `checkpointing`, `pause and resume`, `workflow replay`, `human signal`, `Model Context Protocol`, `Agent-to-Agent protocol`, `small language model`, `task-specific encoder`, `SetFit`, `multilingual embedding`, `visual document retrieval`, `agent state persistence`.

---

## Conclusão

O desenho atual não precisa de uma “reinvenção agentic”. Ele já tem dois ativos bons: **roteamento determinístico onde há semântica contratual** e **RAG próprio com Postgres/híbrido/verificação**. O problema é que esses componentes estão conectados por uma camada conversacional sem as garantias de um sistema de produção: estado volátil, ausência de sessão real, media drop, handoff não formalizado e avaliação ainda centrada demais na resposta. Isso corresponde exatamente às decisões que a pesquisa precisava iluminar.

A arquitetura defensável é, portanto, menos “mais agentes” e mais **estado explícito + recuperação tipada + selective prediction + workflow transacional + avaliação de trajetória**. Depois que isso estiver mensurável, DSPy, RouteLLM, visual RAG, Temporal e modelos especializados passam a ser experimentos com hipótese e critério de vitória — em vez de apostas arquiteturais.

O formato e o nível de evidência acima seguem os critérios pedidos: fontes acadêmicas/documentação oficial separadas de demos de repositório, com antipadrões e maturidade explícitos.

Como esse ecossistema está mudando rapidamente — MCP, runtimes duráveis, embeddings e OCR em particular — posso acompanhar apenas mudanças que alterem alguma dessas decisões arquiteturais.

[1]: https://github.com/n8n-io/n8n-docs/blob/main/docs/build/code-in-n8n/cookbook/built-in-methods-and-variables-examples/getworkflowstaticdata.md "https://github.com/n8n-io/n8n-docs/blob/main/docs/build/code-in-n8n/cookbook/built-in-methods-and-variables-examples/getworkflowstaticdata.md"
[2]: https://docs.cloud.google.com/dialogflow/cx/docs/concept/session?hl=pt-BR "https://docs.cloud.google.com/dialogflow/cx/docs/concept/session?hl=pt-BR"
[3]: https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/ "https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/"
[4]: https://proceedings.neurips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html "https://proceedings.neurips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html"
[5]: https://docs.langchain.com/langsmith/evaluate-with-opentelemetry "https://docs.langchain.com/langsmith/evaluate-with-opentelemetry"
[6]: https://mlanthology.org/iclr/2025/wu2025iclr-longmemeval/ "https://mlanthology.org/iclr/2025/wu2025iclr-longmemeval/"
[7]: https://aclanthology.org/2024.acl-long.747/ "https://aclanthology.org/2024.acl-long.747/"
[8]: https://ojs.aaai.org/index.php/AAAI/article/view/6394 "https://ojs.aaai.org/index.php/AAAI/article/view/6394"
[9]: https://aclanthology.org/D19-1131/ "https://aclanthology.org/D19-1131/"
[10]: https://proceedings.iclr.cc/paper_files/paper/2024/hash/f1cf02ce09757f57c3b93c0db83181e0-Abstract-Conference.html "https://proceedings.iclr.cc/paper_files/paper/2024/hash/f1cf02ce09757f57c3b93c0db83181e0-Abstract-Conference.html"
[11]: https://mlanthology.org/iclr/2025/ong2025iclr-routellm/ "https://mlanthology.org/iclr/2025/ong2025iclr-routellm/"
[12]: https://github.com/beir-cellar/beir "https://github.com/beir-cellar/beir"
[13]: https://arxiv.org/abs/2004.12832 "https://arxiv.org/abs/2004.12832"
[14]: https://bge-model.com/bge/bge_m3.html "https://bge-model.com/bge/bge_m3.html"
[15]: https://qwenlm.github.io/blog/qwen3-embedding/ "https://qwenlm.github.io/blog/qwen3-embedding/"
[16]: https://arxiv.org/abs/2402.05672 "https://arxiv.org/abs/2402.05672"
[17]: https://arxiv.org/abs/2409.10173 "https://arxiv.org/abs/2409.10173"
[18]: https://arxiv.org/abs/2404.16130 "https://arxiv.org/abs/2404.16130"
[19]: https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html "https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html"
[20]: https://www.nature.com/articles/s41586-024-07421-0 "https://www.nature.com/articles/s41586-024-07421-0"
[21]: https://aclanthology.org/2024.eacl-demo.16/ "https://aclanthology.org/2024.eacl-demo.16/"
[22]: https://aclanthology.org/2024.naacl-long.20/ "https://aclanthology.org/2024.naacl-long.20/"
[23]: https://docs.langchain.com/oss/python/langgraph/persistence "https://docs.langchain.com/oss/python/langgraph/persistence"
[24]: https://openai.github.io/openai-agents-python/ref/run_state/ "https://openai.github.io/openai-agents-python/ref/run_state/"
[25]: https://strandsagents.com/docs/user-guide/concepts/agents/interventions/human-in-the-loop/ "https://strandsagents.com/docs/user-guide/concepts/agents/interventions/human-in-the-loop/"
[26]: https://learn.microsoft.com/en-us/agent-framework/overview/ "https://learn.microsoft.com/en-us/agent-framework/overview/"
[27]: https://openaccess.thecvf.com/content/CVPR2021/html/Singh_TextOCR_Towards_Large-Scale_End-to-End_Reasoning_for_Arbitrary-Shaped_Scene_Text_CVPR_2021_paper.html "https://openaccess.thecvf.com/content/CVPR2021/html/Singh_TextOCR_Towards_Large-Scale_End-to-End_Reasoning_for_Arbitrary-Shaped_Scene_Text_CVPR_2021_paper.html"
[28]: https://openaccess.thecvf.com/content/WACV2021/html/Mathew_DocVQA_A_Dataset_for_VQA_on_Document_Images_WACV_2021_paper.html "https://openaccess.thecvf.com/content/WACV2021/html/Mathew_DocVQA_A_Dataset_for_VQA_on_Document_Images_WACV_2021_paper.html"
[29]: https://doi.org/10.1145/3503161.3548112 "https://doi.org/10.1145/3503161.3548112"
[30]: https://arxiv.org/abs/2408.09869 "https://arxiv.org/abs/2408.09869"
[31]: https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PaddleOCR-VL/PaddleOCR-VL.en.md "https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PaddleOCR-VL/PaddleOCR-VL.en.md"
[32]: https://proceedings.iclr.cc/paper_files/paper/2025/hash/99e9e141aafc314f76b0ca3dd66898b3-Abstract-Conference.html "https://proceedings.iclr.cc/paper_files/paper/2025/hash/99e9e141aafc314f76b0ca3dd66898b3-Abstract-Conference.html"
[33]: https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html "https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html"
[34]: https://huggingface.co/papers/2506.07982 "https://huggingface.co/papers/2506.07982"
[35]: https://github.com/amazon-agi/tau2-bench-verified "https://github.com/amazon-agi/tau2-bench-verified"
[36]: https://aclanthology.org/2023.emnlp-main.153/ "https://aclanthology.org/2023.emnlp-main.153/"
[37]: https://docs.langchain.com/langsmith/trace-with-opentelemetry "https://docs.langchain.com/langsmith/trace-with-opentelemetry"
[38]: https://mlanthology.org/tmlr/2024/chen2024tmlr-frugalgpt/ "https://mlanthology.org/tmlr/2024/chen2024tmlr-frugalgpt/"
[39]: https://proceedings.mlsys.org/paper_files/paper/2024/hash/a66caa1703fe34705a4368c3014c1966-Abstract-Conference.html "https://proceedings.mlsys.org/paper_files/paper/2024/hash/a66caa1703fe34705a4368c3014c1966-Abstract-Conference.html"
[40]: https://www.postman.com/meta/whatsapp-business-platform/folder/fuaee8l/statuses-object "https://www.postman.com/meta/whatsapp-business-platform/folder/fuaee8l/statuses-object"
[41]: https://www.postman.com/meta/whatsapp-business-platform/request/x0kd1at/send-reply-button "https://www.postman.com/meta/whatsapp-business-platform/request/x0kd1at/send-reply-button"
[42]: https://blog.modelcontextprotocol.io/posts/2026-07-28/ "https://blog.modelcontextprotocol.io/posts/2026-07-28/"
[43]: https://openai.github.io/openai-agents-python/ "https://openai.github.io/openai-agents-python/"
