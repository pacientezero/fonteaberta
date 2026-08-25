# Blueprint de Arquitetura — Plataforma Open Source de Dados Públicos Oficiais

> Documento inicial para implementação com Codex.
>
> Data de referência: 20/08/2026
> Escopo inicial: Brasil — nível federal — Eleições 2026
> Princípio central: **Fato → Evidência → Fonte oficial**
>
> Este projeto não é um agregador de notícias. O sistema deve priorizar dados públicos oficiais, documentos primários, APIs governamentais, bases abertas e cálculos reproduzíveis.

---

# 1. Objetivo

Construir uma plataforma open source para consulta, cruzamento, auditoria e interpretação de dados públicos oficiais brasileiros.

O usuário poderá fazer perguntas como:

- Quanto determinado candidato declarou em bens?
- Quais bens foram declarados?
- Quanto uma campanha recebeu?
- Quem financiou determinada campanha?
- Quanto foi gasto?
- Como determinado parlamentar votou?
- Quais proposições ele apresentou?
- Quais cargos públicos uma pessoa ocupou?
- Quais contratos uma empresa possui com o Governo Federal?
- Quanto determinado órgão gastou?
- Qual era a inflação, Selic, desemprego ou PIB em determinado período?
- O que consta na proposta oficial de governo de um candidato?
- Qual é a fonte exata dessa afirmação?
- Como o sistema chegou a determinado cálculo?

A plataforma nunca deve tentar responder:

- "quem é o melhor candidato?"
- "quem é mais honesto?"
- "quem é de esquerda ou direita?" com classificação própria
- "em quem devo votar?"
- qualquer pergunta que requeira transformar opinião em fato

O objetivo é responder:

> **"O que os dados oficiais permitem afirmar e qual é a evidência?"**

---

# 2. Regras fundamentais

## 2.1 Fonte primária antes de interpretação

Toda afirmação factual deve apontar para uma fonte oficial.

Cada dado deverá possuir, quando aplicável:

```ts
interface Provenance {
  sourceId: string;
  datasetId?: string;
  externalId?: string;

  sourceUrl?: string;
  documentId?: string;

  sourcePublishedAt?: string;
  sourceUpdatedAt?: string;
  collectedAt: string;

  payloadHash?: string;
  ingestionRunId?: string;

  official: boolean;
}
```

---

## 2.2 Separar fato de inferência

O sistema deverá classificar cada afirmação.

```ts
type ClaimType =
  | "official_fact"
  | "computed_fact"
  | "ai_inference";
```

### `official_fact`

Informação explicitamente presente em uma fonte oficial.

Exemplo:

> Segundo o TSE, o candidato declarou R$ X em bens.

### `computed_fact`

Resultado matemático produzido pela plataforma usando dados oficiais.

Exemplo:

> A soma dos 17 bens declarados resulta em R$ X.

### `ai_inference`

Interpretação não explicitamente declarada pela fonte.

Exemplo:

> O aumento patrimonial pode indicar...

Inferências devem aparecer visualmente separadas dos fatos.

---

# 3. Arquitetura geral

```text
                         INTERNET / FONTES OFICIAIS
                                   |
        +--------------------------+--------------------------+
        |                          |                          |
        v                          v                          v
       TSE                      CAMARA                     SENADO
        |                          |                          |
        +-------------+------------+------------+-------------+
                      |                         |
                      v                         v
                     n8n                     KESTRA
               cargas pequenas            cargas pesadas
               schedules/API              CSV/historico
                      |                         |
                      +------------+------------+
                                   |
                                   v
                        +--------------------+
                        |     POSTGRESQL     |
                        |--------------------|
                        | relational         |
                        | JSONB              |
                        | pgvector           |
                        | views              |
                        | materialized views |
                        +---------+----------+
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
             +-------------+              +-------------+
             |   DIRECTUS  |              | AI SERVICE  |
             |-------------|              |-------------|
             | REST        |              | Ollama      |
             | GraphQL     |              | RAG         |
             | Auth / RBAC |              | pgvector    |
             | Admin       |              | SQL tools   |
             +------+------+              +------+------+
                    |                            |
                    +-------------+--------------+
                                  |
                                  v
                         +----------------+
                         |    SVELTEKIT   |
                         |----------------|
                         | Web            |
                         | Responsive     |
                         | SSR            |
                         | PWA futuro     |
                         +----------------+
```

---

# 4. Stack

## Infraestrutura

Utilizar:

- PostgreSQL
- Directus
- Redis
- n8n
- Kestra
- Ollama
- Docker / Docker Compose

Não adicionar nesta fase:

- RabbitMQ
- Kafka
- Elasticsearch
- OpenSearch
- Kubernetes
- banco de grafos

Essas tecnologias só entram quando houver problema comprovado que justifique a complexidade.

---

# 5. Papel de cada componente

## PostgreSQL

Fonte real dos dados.

Responsável por:

- dados normalizados
- relacionamentos
- JSONB
- índices
- pgvector
- views
- materialized views
- constraints
- agregações
- auditoria
- histórico

---

## Directus

O Directus será a **camada principal de API e administração**.

Responsável por:

- REST API
- GraphQL
- RBAC
- autenticação
- painel administrativo
- CRUD
- filtros
- relacionamentos
- administração de fontes
- inspeção das ingestões
- administração dos documentos
- administração das entidades
- configuração operacional

Evitar criar uma API customizada apenas para reproduzir funções que o Directus já oferece.

---

## n8n

Usar para:

- schedules
- chamadas periódicas de APIs
- webhooks
- notificações
- pequenos ETLs
- integração entre serviços
- tarefas administrativas
- ingestões incrementais

---

## Kestra

Usar para:

- CSVs grandes
- datasets históricos
- processamento paralelo
- reprocessamento
- backfills
- processamento de documentos
- embeddings em lote
- reindexação
- reconstrução de materialized views
- pipelines longos

---

## Redis

Usar para:

- cache
- distributed locks
- idempotência temporária
- rate limiting
- cooldown de APIs externas
- sessões quando necessário

Não usar Redis como banco principal.

---

## Ollama

Provider de IA local.

Responsável inicialmente por:

- embeddings
- chat
- structured output
- classificação simples
- extração estruturada
- interpretação de documentos

A aplicação deve possuir abstração de provider.

```ts
interface LLMProvider {
  chat(input: ChatInput): Promise<ChatResult>;
  embed(texts: string[]): Promise<number[][]>;
  structuredOutput<T>(
    input: StructuredOutputInput<T>
  ): Promise<T>;
}
```

Implementação inicial:

```ts
class OllamaProvider implements LLMProvider {}
```

Possíveis implementações futuras:

```text
OpenAIProvider
AnthropicProvider
GeminiProvider
LocalProvider
```

Nenhuma regra de negócio deve depender diretamente de um modelo.

---

# 6. Frontend

Stack sugerida:

```text
SvelteKit
TypeScript
Tailwind CSS
shadcn-svelte
Lucide
ECharts ou Apache ECharts para visualizações
```

Objetivos:

- leve
- rápido
- SSR
- SEO amigável
- mobile first
- responsivo
- acessível
- moderno
- neutro
- pouco JavaScript desnecessário

---

# 7. Design

Não fazer:

- portal governamental visualmente antiquado
- dashboard cheio de cards sem hierarquia
- excesso de cores
- excesso de animação
- estética partidária

Fazer:

```text
clean
editorial
data-driven
neutral
modern
responsive
accessible
```

Características:

- muito espaço em branco
- ótima tipografia
- números legíveis
- gráficos simples
- tabelas excelentes
- dark mode
- navegação por teclado
- URLs compartilháveis

Não usar cores para classificar ideologia.

Exemplo que deve ser evitado:

```text
vermelho = esquerda
azul = direita
```

Se identidade partidária for exibida, utilizar informação oficial do próprio partido.

---

# 8. Home

A busca é o centro do produto.

```text
+------------------------------------------------------------+

                    O QUE VOCE QUER VERIFICAR?

             [__________________________________]

  Exemplos:

  Quanto X declarou em bens?
  Quanto X recebeu de campanha?
  Como X votou no projeto Y?
  Quais contratos a empresa Z possui com o governo?

+------------------------------------------------------------+
```

Outros blocos:

- candidatos à Presidência
- atualizações recentes das bases
- datasets disponíveis
- indicadores federais
- transparência metodológica

---

# 9. Estratégia Directus-first

Sempre que possível, dados normalizados deverão estar diretamente em collections do Directus.

O Directus utiliza o PostgreSQL existente.

Portanto:

```text
Directus != outro banco
Directus = camada de acesso sobre PostgreSQL
```

Não duplicar:

```text
Postgres -> Directus DB
```

O correto é:

```text
           PostgreSQL
               |
            Directus
```

---

# 10. Collections principais

Sugestão inicial:

```text
sources
datasets
ingestion_runs
raw_records

people
entity_aliases
organizations
locations

parties
elections
candidates
candidate_assets
candidate_social_accounts
candidate_government_plans

campaign_income
campaign_expenses

offices
mandates

legislative_propositions
legislative_votes
legislative_vote_members
legislative_events

government_entities
government_contracts
government_procurements
government_expenses
government_suppliers

documents
document_versions
document_chunks

economic_indicators
economic_series
economic_observations

facts
claims
evidence

audit_events
```

---

# 11. Source registry

Collection:

```text
sources
```

Campos:

```sql
id uuid primary key

name text not null
slug text unique not null

institution text
description text

base_url text
documentation_url text

source_type text
scope text

official boolean default true

update_frequency text
license text

enabled boolean default true

metadata jsonb

created_at timestamptz
updated_at timestamptz
```

Exemplos:

```text
TSE
Camara dos Deputados
Senado Federal
CGU / Portal da Transparencia
Compras.gov.br
IBGE
Banco Central
Tesouro Nacional
TCU
STF
STJ
```

---

# 12. Datasets

Collection:

```text
datasets
```

Campos:

```sql
id uuid primary key

source_id uuid
name text
slug text

external_id text

format text
resource_url text

scope text

period_start date
period_end date

update_frequency text

enabled boolean

metadata jsonb

created_at timestamptz
updated_at timestamptz
```

---

# 13. Ingestion runs

Collection:

```text
ingestion_runs
```

Campos:

```sql
id uuid primary key

source_id uuid
dataset_id uuid

pipeline text
run_type text

started_at timestamptz
finished_at timestamptz

status text

records_read bigint
records_created bigint
records_updated bigint
records_unchanged bigint
records_failed bigint

source_checksum text

error_summary text
metadata jsonb
```

Status:

```text
pending
running
success
partial
failed
cancelled
```

---

# 14. Raw records

Preservar payload original sempre que razoável.

```text
raw_records
```

Campos:

```sql
id uuid primary key

source_id uuid
dataset_id uuid
ingestion_run_id uuid

external_id text

payload jsonb

payload_hash text

source_updated_at timestamptz
collected_at timestamptz

processing_status text

created_at timestamptz
```

Índice:

```sql
CREATE INDEX idx_raw_records_source_external
ON raw_records(source_id, external_id);
```

Payload:

```json
{
  "campo_original_1": "...",
  "campo_original_2": "...",
  "campo_original_3": "..."
}
```

Nunca depender apenas de `raw_records` para consultas de produto.

Dados importantes devem ser normalizados.

---

# 15. Modelo de pessoa

```text
people
```

Campos:

```sql
id uuid primary key

canonical_name text
normalized_name text

birth_date date
birth_place text

metadata jsonb

created_at timestamptz
updated_at timestamptz
```

Evitar usar CPF como identificador público central.

---

# 16. Entity aliases

Fundamental para cruzamento de bases.

```text
entity_aliases
```

Campos:

```sql
id uuid primary key

entity_type text
entity_id uuid

source_id uuid

external_id text
external_name text

metadata jsonb

created_at timestamptz
```

Exemplo:

```text
Pessoa canônica
   |
   +-- TSE: SQ_CANDIDATO
   |
   +-- Camara: idDeputado
   |
   +-- Senado: codigoParlamentar
```

---

# 17. Elections

```text
elections
```

Campos:

```text
id
year
round
election_type
scope
country
state
city
election_date
status
metadata
```

V1:

```text
year = 2026
scope = federal
```

---

# 18. Candidates

```text
candidates
```

Campos mínimos:

```sql
id uuid primary key

person_id uuid not null
election_id uuid not null
party_id uuid

source_id uuid

external_id text

ballot_number integer

position text

application_status text
result_status text

occupation text
education text

declared_assets_total numeric(18,2)

source_updated_at timestamptz
collected_at timestamptz

raw_payload jsonb

created_at timestamptz
updated_at timestamptz
```

---

# 19. Candidate assets

```text
candidate_assets
```

Campos:

```sql
id uuid primary key

candidate_id uuid not null

external_id text

asset_type text
description text

value numeric(18,2)
currency char(3) default 'BRL'

source_id uuid
source_updated_at timestamptz

raw_payload jsonb

created_at timestamptz
```

Índices:

```sql
CREATE INDEX idx_candidate_assets_candidate
ON candidate_assets(candidate_id);

CREATE INDEX idx_candidate_assets_value
ON candidate_assets(value);
```

---

# 20. Partidos

```text
parties
```

Campos:

```text
id
external_id
name
acronym
number
official_url
logo_url
metadata
```

---

# 21. Campaign finance

Collections:

```text
campaign_income
campaign_expenses
```

Receitas:

```text
id
candidate_id
election_id
source_id

external_id

donor_name
donor_type
donor_external_id

amount
date

income_type
description

raw_payload
source_updated_at
```

Despesas:

```text
id
candidate_id
election_id
source_id

external_id

supplier_name
supplier_external_id

amount
date

expense_type
description

document_number

raw_payload
source_updated_at
```

---

# 22. Legislature

Collections:

```text
legislative_propositions
legislative_votes
legislative_vote_members
legislative_events
```

`legislative_propositions`:

```text
id
source_id
external_id

type
number
year

title
summary

presented_at
status

source_url

raw_payload
```

`legislative_votes`:

```text
id
source_id
external_id

proposition_id

date
description
result

raw_payload
```

`legislative_vote_members`:

```text
id
vote_id
person_id

party_id

vote_value
vote_label

raw_payload
```

---

# 23. Government data

Collections:

```text
government_entities
government_contracts
government_procurements
government_expenses
government_suppliers
```

Possibilitar relações:

```text
ORGAO
 |
 +-- realizou --> LICITACAO
 |
 +-- assinou --> CONTRATO
 |
 +-- pagou --> DESPESA


EMPRESA
 |
 +-- participou --> LICITACAO
 |
 +-- possui --> CONTRATO
 |
 +-- recebeu --> PAGAMENTO
```

---

# 24. Document engine

Documentos são entidades de primeira classe.

```text
documents
document_versions
document_chunks
```

Exemplos:

- proposta de governo
- lei
- decreto
- relatório
- parecer
- acórdão
- contrato
- edital
- ata
- documento eleitoral

---

# 25. Documents

```sql
documents

id uuid primary key

source_id uuid

entity_type text
entity_id uuid

document_type text

title text
description text

external_id text
source_url text

published_at timestamptz

mime_type text

latest_version_id uuid

metadata jsonb

created_at timestamptz
updated_at timestamptz
```

---

# 26. Document versions

```text
document_versions
```

Campos:

```text
id
document_id

version_number

file_path
file_url

sha256

text_content

collected_at
source_updated_at

metadata
```

Nunca sobrescrever silenciosamente uma versão.

---

# 27. pgvector

Ativar:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

# 28. Document chunks

```sql
CREATE TABLE document_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    document_id uuid NOT NULL,
    document_version_id uuid,

    chunk_index integer NOT NULL,

    page integer,
    section text,

    content text NOT NULL,

    embedding vector(1024),

    token_count integer,

    metadata jsonb,

    created_at timestamptz DEFAULT now()
);
```

A dimensão do vector deve corresponder ao modelo de embeddings escolhido.

Não fixar `1024` se o modelo usar outra dimensão.

---

# 29. Vector search

Consulta conceitual:

```sql
SELECT
    id,
    document_id,
    page,
    content,
    embedding <=> $1 AS distance
FROM document_chunks
ORDER BY embedding <=> $1
LIMIT 10;
```

O serviço de IA deve poder combinar:

```text
SQL estruturado
+
vector search
+
document metadata
```

---

# 30. RAG

Fluxo:

```text
QUESTION
   |
   v
INTENT
   |
   v
ENTITY RESOLUTION
   |
   +----------------------+
   |                      |
   v                      v
STRUCTURED QUERY       SEMANTIC QUERY
   |                      |
   v                      v
POSTGRES              PGVECTOR
   |                      |
   +-----------+----------+
               |
               v
            EVIDENCE
               |
               v
             OLLAMA
               |
               v
             ANSWER
               |
               v
           CITATIONS
```

---

# 31. Prioridade de consulta

Sempre preferir:

```text
1. SQL / dados estruturados
2. documentos oficiais específicos
3. vector search
4. LLM
```

Nunca perguntar ao LLM algo que o banco consegue calcular diretamente.

Pergunta:

```text
Quanto X declarou em bens?
```

Correto:

```sql
SELECT SUM(value)
FROM candidate_assets
WHERE candidate_id = $1;
```

Errado:

```text
buscar chunks aleatórios
-> mandar para LLM
-> pedir soma
```

---

# 32. AI service

Criar um serviço separado pequeno.

Exemplo:

```text
apps/ai-api
```

Possível stack:

```text
Python + FastAPI
```

ou:

```text
TypeScript + Hono/Fastify
```

Escolher uma.

Para V1, FastAPI é aceitável por facilitar bibliotecas de IA.

Endpoints:

```http
POST /v1/query
POST /v1/embed
POST /v1/documents/index
POST /v1/entities/resolve
GET  /health
```

---

# 33. Copilot response

Formato:

```json
{
  "answer": "Segundo os dados oficiais...",
  "claim_type": "official_fact",

  "facts": [
    {
      "label": "Patrimonio declarado",
      "value": 5284321.9,
      "unit": "BRL"
    }
  ],

  "evidence": [
    {
      "source": "Tribunal Superior Eleitoral",
      "dataset": "Candidatos 2026",
      "external_id": "...",
      "source_url": "...",
      "collected_at": "..."
    }
  ],

  "limitations": []
}
```

---

# 34. Regra anti-alucinação

Prompt de sistema sugerido:

```text
Voce e um assistente de consulta a dados publicos oficiais.

Use exclusivamente as evidencias fornecidas nesta solicitacao para
afirmacoes factuais.

Nao utilize conhecimento interno do modelo como evidência.

Diferencie explicitamente:
- fato oficial;
- calculo produzido pelo sistema;
- inferencia.

Quando as evidencias forem insuficientes, responda:

"Nao encontrei dados oficiais suficientes para responder esta pergunta."

Nao invente datas, valores, pessoas, cargos, relacoes ou conclusoes.
Nao transforme correlacao em causalidade.
```

---

# 35. Facts

Collection:

```text
facts
```

Campos:

```text
id

subject_type
subject_id

predicate

object_type
object_id

value_text
value_numeric
value_boolean
value_date

unit

effective_date

source_id
evidence_id

calculation_method

created_at
```

Exemplo:

```text
subject:
candidate:123

predicate:
declared_assets_total

value_numeric:
5284321.90

unit:
BRL

source:
TSE
```

---

# 36. Evidence

Collection:

```text
evidence
```

Campos:

```text
id

source_id
dataset_id

raw_record_id
document_id
document_version_id
document_chunk_id

external_id

source_url

page
section

collected_at

payload_hash

metadata
```

---

# 37. Claims

Collection:

```text
claims
```

Campos:

```text
id

claim_type

statement

subject_type
subject_id

calculation_method

model_provider
model_name

created_at
```

Relacionamento N:N:

```text
claims_evidence
```

---

# 38. Provenance UI

O frontend deverá mostrar:

```text
R$ 5.284.321,90

Fonte
Tribunal Superior Eleitoral

Dataset
Candidatos 2026

Registros utilizados
17

Data da coleta
20/08/2026

[Ver registros]
[Ver fonte oficial]
[Como foi calculado?]
```

---

# 39. Página do candidato

Rota:

```text
/pessoas/[slug]
```

ou:

```text
/candidatos/[id]
```

Seções:

```text
Visao geral
Eleicoes
Patrimonio
Receitas
Despesas
Propostas
Historico
Atuacao politica
Fontes
```

---

# 40. Comparador

Rota:

```text
/comparar?a=<id>&b=<id>
```

Mostrar:

- dados cadastrais
- patrimônio
- histórico eleitoral
- receitas
- despesas
- propostas
- cargos
- votações
- fatos verificáveis

Não produzir:

```text
vencedor
melhor
pior
mais honesto
score politico
score ideologico
```

---

# 41. Timeline

Exemplo:

```text
2014
|
+-- candidato a ...

2018
|
+-- eleito ...

2022
|
+-- patrimonio declarado ...

2024
|
+-- ...

2026
|
+-- candidato ...
```

A timeline deve ser construída usando fatos normalizados.

---

# 42. Directus permissions

Perfis sugeridos:

```text
Public
Contributor
Researcher
Admin
System
```

### Public

Somente leitura.

Pode acessar:

```text
people
parties
elections
candidates
candidate_assets
campaign_income
campaign_expenses
facts
evidence
public documents
economic data
legislative data
```

Não permitir acesso direto a:

```text
raw_records internos
logs internos
segredos
tokens
configuracoes
audit administrativo
```

---

# 43. API pública

Sempre que possível usar Directus.

Exemplos:

```http
GET /items/candidates
GET /items/candidate_assets
GET /items/people
GET /items/facts
GET /items/evidence
```

Filtro:

```http
/items/candidates
?filter[election][year][_eq]=2026
&fields=*,person.*,party.*
```

Evitar implementar:

```http
/custom-api/candidates
```

se o Directus já resolver a consulta adequadamente.

---

# 44. Custom endpoints

Criar apenas quando houver motivo.

Exemplos:

```http
GET /public/candidates/:id/summary
GET /public/candidates/:id/net-worth-history
GET /public/entities/:id/timeline
POST /ai/query
```

Esses endpoints podem usar:

- Directus extensions
- serviço separado
- SQL views

---

# 45. PostgreSQL views

Views podem simplificar o frontend.

Exemplo:

```sql
CREATE VIEW candidate_asset_totals AS
SELECT
    c.id AS candidate_id,
    c.person_id,
    c.election_id,
    COUNT(a.id) AS assets_count,
    COALESCE(SUM(a.value), 0) AS assets_total
FROM candidates c
LEFT JOIN candidate_assets a
    ON a.candidate_id = c.id
GROUP BY
    c.id,
    c.person_id,
    c.election_id;
```

Expor como collection read-only no Directus.

---

# 46. Materialized views

Para análises pesadas:

```sql
CREATE MATERIALIZED VIEW candidate_asset_history AS
SELECT
    c.person_id,
    e.year,
    COUNT(a.id) AS assets_count,
    COALESCE(SUM(a.value), 0) AS assets_total
FROM candidates c
JOIN elections e
    ON e.id = c.election_id
LEFT JOIN candidate_assets a
    ON a.candidate_id = c.id
GROUP BY
    c.person_id,
    e.year;
```

Atualização via Kestra.

---

# 47. Idempotência

Toda ingestão precisa ser idempotente.

Chave lógica:

```text
source_id
dataset_id
external_id
```

Hash:

```text
sha256(raw_payload)
```

Fluxo:

```text
fetch
  |
  v
calculate hash
  |
  +-- hash igual --> unchanged
  |
  +-- hash diferente --> version + normalize
```

---

# 48. Pipeline padrão

Todos os conectores devem seguir:

```text
discover
fetch
snapshot
validate
normalize
resolve_entities
upsert
create_evidence
index_documents
audit
publish
```

---

# 49. Interface de conector

```ts
interface DataConnector {
  id: string;

  discover(): Promise<Dataset[]>;

  fetch(
    dataset: Dataset,
    cursor?: Cursor
  ): Promise<RawBatch>;

  validate(
    batch: RawBatch
  ): Promise<ValidationResult>;

  normalize(
    batch: RawBatch
  ): Promise<NormalizedRecord[]>;

  checkpoint(): Promise<Cursor>;
}
```

---

# 50. Estratégia API vs bulk

Para cada fonte, suportar quando possível:

```text
API
+
bulk dataset
```

Uso:

```text
API
-> pequenas atualizacoes
-> consultas incrementais
-> baixa latencia

Bulk / CSV / ZIP
-> historico
-> backfill
-> grande volume
-> reconstrução completa
```

---

# 51. Fontes oficiais — prioridade P0

## Tribunal Superior Eleitoral — TSE

Portal:

https://dadosabertos.tse.jus.br/

Candidatos 2026:

https://dadosabertos.tse.jus.br/dataset/candidatos-2026

O conjunto Candidatos 2026 inclui atualmente recursos relacionados a:

- candidatos
- informações complementares
- bens de candidatos
- coligações
- vagas
- motivo de cassação
- redes sociais
- fotos
- proposta de governo

O próprio portal indica atualização diária para o conjunto de candidatos 2026.

Criar:

```text
connector-tse
```

Prioridade de ingestão:

```text
1 candidatos
2 informacoes complementares
3 bens
4 partidos / coligacoes
5 propostas de governo
6 fotos
7 redes sociais
8 prestacao de contas quando datasets correspondentes estiverem disponíveis
9 resultados quando publicados
```

---

# 52. Câmara dos Deputados

Documentação da API:

https://dadosabertos.camara.leg.br/swagger/api.html

API base:

```text
https://dadosabertos.camara.leg.br/api/v2
```

OpenAPI:

```text
https://dadosabertos.camara.leg.br/api/v2/api-docs
```

Endpoints importantes:

```http
GET /deputados
GET /deputados/{id}
GET /deputados/{id}/despesas

GET /proposicoes
GET /proposicoes/{id}
GET /proposicoes/{id}/autores
GET /proposicoes/{id}/tramitacoes
GET /proposicoes/{id}/votacoes

GET /votacoes
GET /votacoes/{id}
GET /votacoes/{id}/orientacoes
GET /votacoes/{id}/votos

GET /eventos
GET /eventos/{id}

GET /orgaos
GET /orgaos/{id}
GET /orgaos/{id}/membros
```

Criar:

```text
connector-camara
```

---

# 53. Senado Federal

Portal de dados abertos:

https://www12.senado.leg.br/dados-abertos

Criar:

```text
connector-senado
```

Prioridades:

```text
senadores
mandatos
materias
autorias
relatorias
votacoes
votos nominais
sessoes
```

A implementação deve tratar os diferentes formatos e webservices disponibilizados pelo Senado como adapters internos do mesmo connector.

---

# 54. Portal da Transparência / CGU

Portal:

https://portaldatransparencia.gov.br/

API:

https://portaldatransparencia.gov.br/api-de-dados

Documentação / Swagger:

https://api.portaldatransparencia.gov.br/

Criar:

```text
connector-transparencia
```

Prioridades:

```text
despesas
contratos
convenios
licitacoes
viagens
servidores
CEIS
CNEP
CEAF
```

Para grandes volumes, preferir arquivos oficiais bulk quando disponíveis.

---

# 55. Compras.gov.br

Portal:

https://www.gov.br/compras/

Dados abertos:

https://www.gov.br/compras/pt-br/cidadao/portal-de-dados-abertos/portal-de-dados-abertos

Criar:

```text
connector-comprasgov
```

Prioridades:

```text
licitacoes
contratos
fornecedores
itens
orgaos
valores
```

Implementar retry, checkpoint e suporte a bulk.

---

# 56. IBGE

Portal:

https://www.ibge.gov.br/

SIDRA:

https://sidra.ibge.gov.br/

API SIDRA:

https://apisidra.ibge.gov.br/

Criar:

```text
connector-ibge
```

Prioridades:

```text
populacao
PIB
PNAD
desemprego
municipios
estados
indicadores socioeconomicos
```

---

# 57. Banco Central do Brasil

Dados abertos:

https://dadosabertos.bcb.gov.br/

Portal BCB:

https://www.bcb.gov.br/acessoinformacao/dadosabertos

Criar:

```text
connector-bcb
```

Prioridades:

```text
Selic
cambio
credito
series temporais
estatisticas financeiras
```

Armazenar séries em:

```text
economic_series
economic_observations
```

---

# 58. Tesouro Nacional

Portal:

https://www.gov.br/tesouronacional/

SICONFI:

https://siconfi.tesouro.gov.br/

Criar futuramente:

```text
connector-tesouro
connector-siconfi
```

Usos:

```text
divida
resultado fiscal
financas publicas
dados estaduais
dados municipais
```

---

# 59. TCU

Portal:

https://portal.tcu.gov.br/

Dados abertos:

https://portal.tcu.gov.br/dados-abertos/

Criar:

```text
connector-tcu
```

---

# 60. Diário Oficial da União

Portal:

https://www.in.gov.br/

Criar futuramente:

```text
connector-dou
```

Documentos do DOU devem passar por pipeline documental.

---

# 61. STF

Portal:

https://portal.stf.jus.br/

Dados abertos / serviços disponíveis deverão ser avaliados durante implementação do connector.

Criar futuramente:

```text
connector-stf
```

---

# 62. STJ

Portal:

https://www.stj.jus.br/

Criar futuramente:

```text
connector-stj
```

---

# 63. Ordem das fontes

## P0

```text
TSE
```

## P1

```text
Camara
Senado
```

## P2

```text
Portal da Transparencia
Compras.gov
```

## P3

```text
IBGE
Banco Central
Tesouro
```

## P4

```text
TCU
DOU
STF
STJ
```

---

# 64. V1

Escopo estrito:

```text
Eleicao presidencial 2026
```

Objetivo mínimo:

Pergunta:

> Quanto o candidato X declarou em patrimônio?

Resposta:

```text
O candidato declarou R$ X em bens.

Foram encontrados N bens declarados.

Fonte:
Tribunal Superior Eleitoral
Dataset Candidatos 2026

Atualizado pela fonte em:
...

Coletado em:
...

[Ver bens]
[Ver dados oficiais]
[Como calculamos]
```

---

# 65. V1 — entregáveis

```text
[ ] docker-compose do projeto

[ ] PostgreSQL
[ ] pgvector
[ ] Directus
[ ] Redis
[ ] n8n
[ ] Kestra
[ ] Ollama

[ ] migrations

[ ] collections Directus

[ ] sources
[ ] datasets
[ ] ingestion_runs
[ ] raw_records

[ ] people
[ ] entity_aliases

[ ] parties
[ ] elections
[ ] candidates
[ ] candidate_assets

[ ] documents
[ ] document_versions
[ ] document_chunks

[ ] facts
[ ] evidence
[ ] claims

[ ] connector TSE

[ ] candidatos 2026
[ ] bens 2026
[ ] propostas 2026

[ ] SvelteKit

[ ] home
[ ] pesquisa
[ ] pagina candidato
[ ] patrimonio
[ ] fontes

[ ] AI service
[ ] Ollama provider
[ ] embeddings
[ ] RAG sobre propostas

[ ] resposta com evidencia
```

---

# 66. Fase 2

Adicionar:

```text
Camara
Senado
```

Entregáveis:

```text
historico parlamentar
mandatos
proposicoes
votacoes
votos nominais
despesas parlamentares
timeline
```

---

# 67. Fase 3

Adicionar:

```text
Portal da Transparencia
Compras.gov
```

Entregáveis:

```text
contratos
licitacoes
fornecedores
despesas
pagamentos
viagens
sancoes
```

---

# 68. Fase 4

Adicionar:

```text
IBGE
BCB
Tesouro
```

Entregáveis:

```text
series economicas
contexto historico
indicadores
comparacoes temporais
```

---

# 69. Fase 5

Construir Knowledge Graph lógico sem adicionar banco de grafos.

Relações no PostgreSQL:

```text
PESSOA
 |
 +-- CANDIDATO_EM --> ELEICAO
 |
 +-- FILIADO_A --> PARTIDO
 |
 +-- OCUPOU --> CARGO
 |
 +-- VOTOU_EM --> PROPOSICAO
 |
 +-- DECLAROU --> BEM


EMPRESA
 |
 +-- DOOU_PARA --> CAMPANHA
 |
 +-- FORNECEU_PARA --> ORGAO
 |
 +-- POSSUI --> CONTRATO
```

Avaliar Neo4j ou outro banco de grafos apenas se PostgreSQL deixar de atender.

---

# 70. Monorepo

Estrutura sugerida:

```text
/
├── apps/
│   ├── web/
│   ├── ai-api/
│   └── scripts/
│
├── packages/
│   ├── domain/
│   ├── database/
│   ├── directus-sdk/
│   ├── provenance/
│   ├── rag/
│   ├── llm/
│   ├── shared/
│   └── ui/
│
├── connectors/
│   ├── core/
│   ├── tse/
│   ├── camara/
│   ├── senado/
│   ├── transparencia/
│   ├── comprasgov/
│   ├── ibge/
│   ├── bcb/
│   └── tesouro/
│
├── pipelines/
│   ├── n8n/
│   └── kestra/
│
├── directus/
│   ├── extensions/
│   ├── snapshots/
│   └── seeds/
│
├── database/
│   ├── migrations/
│   ├── views/
│   └── seeds/
│
├── docs/
│
├── docker/
│
├── tests/
│
├── docker-compose.yml
├── .env.example
├── README.md
└── LICENSE
```

---

# 71. Docker Compose

O Codex deve criar um Compose com:

```text
postgres
directus
redis
n8n
kestra
ollama
web
ai-api
```

Não expor banco publicamente.

---

# 72. Variáveis de ambiente

Criar:

```env
POSTGRES_HOST=
POSTGRES_PORT=5432
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=

DIRECTUS_URL=
DIRECTUS_KEY=
DIRECTUS_SECRET=

REDIS_URL=

OLLAMA_URL=http://ollama:11434
OLLAMA_CHAT_MODEL=
OLLAMA_EMBED_MODEL=

AI_API_URL=

PUBLIC_DIRECTUS_URL=
PUBLIC_AI_API_URL=
```

Segredos nunca devem ser commitados.

---

# 73. Observabilidade

Dashboard administrativo deverá mostrar:

```text
Fonte
Dataset
Status
Ultima coleta
Duracao
Registros processados
Criados
Atualizados
Falhas
Ultimo hash
```

Alertas:

```text
source unavailable
schema changed
volume dropped unexpectedly
error rate increased
authentication failed
dataset disappeared
document changed
```

---

# 74. Schema drift

Datasets governamentais podem alterar campos.

Nunca assumir schema eterno.

Validação:

```text
incoming columns
       |
       v
schema fingerprint
       |
       +-- igual -> continuar
       |
       +-- mudou -> alert + raw snapshot + processamento seguro
```

---

# 75. Data quality

Criar regras:

```text
required field missing
invalid date
invalid currency
invalid ID
duplicate external ID
orphan relation
impossible numeric value
encoding issue
```

Cada pipeline registra:

```text
quality_score
warnings
errors
```

---

# 76. Testes

Obrigatórios:

```text
unit tests
connector contract tests
normalization tests
idempotency tests
integration tests
database tests
RAG citation tests
frontend e2e
```

Um connector nunca deve ser aceito sem fixture real de fonte oficial.

---

# 77. Teste anti-alucinação

Exemplo:

Pergunta:

```text
Qual é o patrimônio do candidato inexistente ABC XYZ?
```

Esperado:

```text
Nao encontrei dados oficiais suficientes para responder essa pergunta.
```

Nunca:

```text
provavelmente...
deve ser...
segundo meu conhecimento...
```

---

# 78. Transparência metodológica

Criar página:

```text
/metodologia
```

Mostrar:

- fontes
- frequência de atualização
- como valores são calculados
- como entidades são relacionadas
- limitações
- modelos de IA utilizados
- política de inferência
- política de correção

---

# 79. Página de fontes

Rota:

```text
/fontes
```

Cada fonte:

```text
Nome
Órgão
URL oficial
Datasets usados
Última atualização
Última ingestão
Status
Licença
Metodologia
```

---

# 80. Correção de dados

Não editar silenciosamente um dado oficial.

Se uma informação estiver incorreta na fonte:

```text
original official value
+
correction note
```

A plataforma poderá registrar observações internas, mas nunca substituir o que a fonte disse sem rastreabilidade.

---

# 81. Versionamento

Exemplo:

```text
candidate_assets

current row
+
raw record history
+
ingestion history
```

Para documentos:

```text
document
  |
  +-- version 1
  |
  +-- version 2
  |
  +-- version 3
```

---

# 82. Segurança

Obrigatório:

- Directus RBAC
- PostgreSQL fechado
- secrets em env/secret manager
- rate limiting público
- CSP
- CSRF quando aplicável
- sanitização de rich text
- validação de upload
- limites de arquivos
- auditoria administrativa

---

# 83. Privacidade

Não construir perfil pessoal com informações irrelevantes.

Coletar apenas dados necessários ao propósito público da plataforma.

Evitar republicar identificadores pessoais sensíveis quando não forem essenciais.

---

# 84. Cache

Redis:

```text
candidate summary
search suggestions
popular facts
economic series
source status
```

Cache deve possuir TTL.

Nunca cachear sem estratégia de invalidação.

---

# 85. Busca

V1:

```text
PostgreSQL
pg_trgm
full text search
```

Ativar:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
```

Vector search é para semântica documental, não substituto universal de search.

---

# 86. Busca híbrida

Futuramente:

```text
query
 |
 +-- lexical search
 |
 +-- trigram
 |
 +-- entity aliases
 |
 +-- semantic search
 |
 +-- rerank
```

---

# 87. URL design

URLs estáveis.

Exemplos:

```text
/candidatos/presidencia/2026
/candidato/<slug>
/pessoa/<slug>
/partido/<sigla>
/eleicao/2026
/comparar
/fontes
/metodologia
/dados
```

---

# 88. SEO e compartilhamento

Cada página pública deve possuir:

```text
title
description
canonical
OpenGraph
JSON-LD quando apropriado
```

Páginas de fatos devem ser linkáveis.

---

# 89. Internacionalização

Estruturar frontend para i18n desde o início.

Idioma inicial:

```text
pt-BR
```

Não precisa traduzir V1.

---

# 90. Acessibilidade

Meta:

```text
WCAG 2.2 AA
```

Obrigatório:

- contraste
- teclado
- focus states
- labels
- alt text
- semântica HTML
- gráficos com tabela alternativa

---

# 91. Licença

Projeto open source.

A licença final do projeto é:

```text
AGPL-3.0
```

Ela obriga derivados oferecidos como serviço a publicar modificações, o que combina com o contrato de provenance auditável e com o objetivo de manter o sistema aberto ao longo do uso em rede.

---

# 92. README público

README inicial deve explicar:

```text
O que é
O que não é
Arquitetura
Fontes
Como executar
Como criar connector
Como contribuir
Metodologia
Licença
```

---

# 93. Instruções para o Codex — ordem de implementação

Não tentar construir tudo de uma vez.

## Sprint 0

```text
1 criar monorepo
2 docker compose
3 postgres + pgvector
4 directus
5 redis
6 ollama
7 n8n
8 kestra
9 sveltekit
10 ai-api
```

## Sprint 1

```text
1 migrations core
2 source registry
3 datasets
4 ingestion runs
5 raw records
6 directus snapshot
7 RBAC
```

## Sprint 2

```text
1 connector core
2 connector TSE
3 importar candidatos 2026
4 importar bens 2026
5 entity mapping
6 testes
```

## Sprint 3

```text
1 frontend home
2 candidatos
3 pagina candidato
4 patrimonio
5 provenance UI
6 pagina fontes
```

## Sprint 4

```text
1 documentos
2 propostas de governo
3 extraction
4 chunks
5 embeddings
6 pgvector
7 RAG
8 citations
```

## Sprint 5

```text
1 Camara connector
2 deputados
3 proposicoes
4 votacoes
5 votos
6 timeline
```

---

# 94. Definition of Done para qualquer dado

Um dataset só é considerado integrado quando:

```text
[ ] source registrada
[ ] dataset registrado
[ ] raw snapshot preservado
[ ] hash calculado
[ ] normalizacao documentada
[ ] IDs externos preservados
[ ] ingestion run registrada
[ ] idempotencia testada
[ ] provenance disponível
[ ] API Directus funcionando
[ ] UI consegue apontar para evidencia
[ ] testes automatizados
```

---

# 95. Definition of Done para resposta da IA

Uma resposta factual só é válida quando:

```text
[ ] pergunta interpretada
[ ] entidades identificadas
[ ] evidencias recuperadas
[ ] fonte oficial conhecida
[ ] resposta não extrapola evidencias
[ ] claims classificados
[ ] citations retornadas
[ ] limitações informadas
```

---

# 96. Regra final

O produto não tenta criar uma nova autoridade sobre a verdade.

Ele fornece uma cadeia auditável:

```text
PERGUNTA
   |
   v
DADO
   |
   v
EVIDENCIA
   |
   v
FONTE OFICIAL
```

Quando houver cálculo:

```text
DADOS OFICIAIS
      |
      v
METODO REPRODUZIVEL
      |
      v
RESULTADO
```

Quando houver IA:

```text
EVIDENCIAS
    |
    v
MODELO
    |
    v
INTERPRETACAO IDENTIFICADA COMO INTERPRETACAO
```

A meta é que o usuário nunca precise confiar cegamente no sistema.

Ele deve conseguir perguntar:

> **"Como vocês chegaram nisso?"**

e receber os dados, o cálculo, os registros, a data de coleta e a fonte oficial.

---

# 97. Primeira tarefa concreta para o Codex

Implementar apenas o caminho vertical abaixo antes de expandir:

```text
TSE Candidatos 2026
        |
        v
Kestra / Connector TSE
        |
        v
raw_records
        |
        v
normalize
        |
        +--> people
        |
        +--> elections
        |
        +--> parties
        |
        +--> candidates
        |
        +--> candidate_assets
        |
        v
Directus
        |
        v
SvelteKit
        |
        v
/candidato/<id>
        |
        v
Patrimonio declarado + evidencia
```

Critério final:

A tela de um candidato deve conseguir exibir:

```text
Patrimonio declarado: R$ X

Quantidade de bens: N

Fonte: Tribunal Superior Eleitoral

Dataset: Candidatos 2026

Ultima coleta: DATA

[Ver bens declarados]
[Ver fonte oficial]
[Ver metodologia]
```

Só depois disso iniciar o connector da Câmara.

---

# 98. Fontes oficiais iniciais — índice rápido

```text
TSE
https://dadosabertos.tse.jus.br/
https://dadosabertos.tse.jus.br/dataset/candidatos-2026

CAMARA DOS DEPUTADOS
https://dadosabertos.camara.leg.br/swagger/api.html
https://dadosabertos.camara.leg.br/api/v2
https://dadosabertos.camara.leg.br/api/v2/api-docs

SENADO FEDERAL
https://www12.senado.leg.br/dados-abertos

PORTAL DA TRANSPARENCIA / CGU
https://portaldatransparencia.gov.br/
https://portaldatransparencia.gov.br/api-de-dados
https://api.portaldatransparencia.gov.br/

COMPRAS.GOV.BR
https://www.gov.br/compras/
https://www.gov.br/compras/pt-br/cidadao/portal-de-dados-abertos/portal-de-dados-abertos

IBGE
https://www.ibge.gov.br/
https://sidra.ibge.gov.br/
https://apisidra.ibge.gov.br/

BANCO CENTRAL
https://dadosabertos.bcb.gov.br/
https://www.bcb.gov.br/acessoinformacao/dadosabertos

TESOURO NACIONAL
https://www.gov.br/tesouronacional/
https://siconfi.tesouro.gov.br/

TCU
https://portal.tcu.gov.br/
https://portal.tcu.gov.br/dados-abertos/

DIARIO OFICIAL DA UNIAO
https://www.in.gov.br/

STF
https://portal.stf.jus.br/

STJ
https://www.stj.jus.br/
```

---

# 99. Nota técnica sobre 2026

Na data de referência deste blueprint, o Portal de Dados Abertos do TSE possui o conjunto **Candidatos - 2026**, contendo recursos de candidatos, informações complementares, bens, coligações, vagas, motivos de cassação, redes sociais, fotos e propostas de governo.

A arquitetura deve, contudo, tratar datasets externos como fontes mutáveis: recursos podem ser adicionados, alterados ou atualizados durante o processo eleitoral.

Por isso, discovery, versionamento, hashes e schema-drift detection são requisitos de arquitetura, não melhorias opcionais.

---

# 100. Filosofia do projeto

```text
NOTICIA       -> fora da cadeia principal de evidência

DADO OFICIAL  -> permitido

DOCUMENTO
OFICIAL       -> permitido

CALCULO
REPRODUZIVEL  -> permitido, identificado como calculado

INFERENCIA IA -> permitido, explicitamente identificado

SEM EVIDENCIA -> não afirmar como fato
```

**Fato → Evidência → Fonte.**
