<script lang="ts">
  import {
    dataRoute,
    documentsRoute,
    homeRoute,
    searchRoute,
    sourcesRoute,
  } from '$lib/navigation';
</script>

<svelte:head>
  <title>Metodologia | FonteAberta</title>
  <meta
    name="description"
    content="Transparência metodológica do FonteAberta: fontes, atualização, cálculo, entidades, IA, limitações e correções."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Transparência metodológica</p>
      <h1>Como o sistema calcula, relaciona e limita respostas</h1>
    </div>

    <p class="lead">
      Cada resposta pública precisa apontar fonte oficial, dataset, coleta, evidência e
      cálculo. Quando não houver evidência suficiente, o sistema deve abster-se em vez de
      inferir.
    </p>

    <div class="toolbar">
      <a class="button" href={dataRoute()}>Ver dados</a>
      <a class="button-secondary" href={documentsRoute()}>Documentos</a>
      <a class="button-secondary" href={sourcesRoute()}>Fontes</a>
      <a class="button-secondary" href={searchRoute()}>Busca</a>
      <a class="button-secondary" href={homeRoute()}>Inicio</a>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Contrato operacional</p>
      <h2>Fonte &gt; evidência &gt; claim</h2>
      <p class="note">
        A página resume as regras que a UI usa para manter provenance, atualização e correção
        rastreáveis.
      </p>
    </div>

    <ul class="list">
      <li>
        <span>Fato oficial sempre vem da fonte primária</span>
        <span>sim</span>
      </li>
      <li>
        <span>Claim sem evidence não deve ser promovida</span>
        <span>sim</span>
      </li>
      <li>
        <span>Correções preservam o raw record original</span>
        <span>sim</span>
      </li>
      <li>
        <span>Resumo público deve citar origem e cálculo</span>
        <span>sim</span>
      </li>
    </ul>
  </aside>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Fontes</p>
        <h2>Origem e atualização</h2>
      </div>
      <span class="badge badge-accent">oficial</span>
    </div>

    <ul class="list">
      <li>
        <span>Fontes primárias vêm de portais oficiais e bases abertas</span>
      </li>
      <li>
        <span>Datasets carregam `resource_url`, `external_id` e janela temporal</span>
      </li>
      <li>
        <span>Atualizações entram por ingestões idempotentes e rastreáveis</span>
      </li>
      <li>
        <span>Cada slice preserva o payload bruto antes da normalização</span>
      </li>
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Cálculo</p>
        <h2>Como valores são produzidos</h2>
      </div>
      <span class="badge badge-accent">reprodutível</span>
    </div>

    <ul class="list">
      <li>
        <span>Patrimônio do candidato é soma explícita dos bens declarados</span>
      </li>
      <li>
        <span>Selic e IPCA exibem séries observacionais com última leitura destacada</span>
      </li>
      <li>
        <span>Despesa pública e RREO usam agregação determinística sobre linhas oficiais</span>
      </li>
      <li>
        <span>Compras.gov destaca o primeiro fornecedor da página validada</span>
      </li>
    </ul>
  </article>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Entidades</p>
        <h2>Como dados se relacionam</h2>
      </div>
      <span class="badge">provenance</span>
    </div>

    <ul class="list">
      <li>
        <span>`sources` → `datasets` → `raw_records` → `evidence` → `facts` → `claims`</span>
      </li>
      <li>
        <span>Pessoas, eleições, partidos, candidatos e bens usam IDs oficiais e aliases</span>
      </li>
      <li>
        <span>Mandatos parlamentares ligam pessoa, partido, legislatura e evidência</span>
      </li>
      <li>
        <span>Documentos usam chunks e embeddings, mas continuam ancorados em citação</span>
      </li>
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">IA e inferência</p>
        <h2>Onde o modelo entra</h2>
      </div>
      <span class="badge badge-accent">controlada</span>
    </div>

    <ul class="list">
      <li>
        <span>Os endpoints públicos factuais não fazem geração livre sem evidência</span>
      </li>
      <li>
        <span>Documentos usam busca semântica e citação, não adivinhação de conteúdo</span>
      </li>
      <li>
        <span>O sistema pode abster-se quando a query não tem evidência suficiente</span>
      </li>
      <li>
        <span>Inferência aceita só quando o contrato do dado explicita o método</span>
      </li>
    </ul>
  </article>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Limitações</p>
        <h2>O que a UI não promete</h2>
      </div>
      <span class="badge">limite</span>
    </div>

    <ul class="list">
      <li>
        <span>Não inventa fonte quando o portal oficial não responde</span>
      </li>
      <li>
        <span>Não substitui a leitura do portal oficial quando a fonte é a referência</span>
      </li>
      <li>
        <span>Não mistura slices de períodos ou entidades diferentes na mesma resposta</span>
      </li>
      <li>
        <span>Não trata similaridade semântica como verdade factual</span>
      </li>
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Correções</p>
        <h2>Como o contrato evolui</h2>
      </div>
      <span class="badge badge-accent">auditável</span>
    </div>

    <ul class="list">
      <li>
        <span>Correções chegam como nova ingestão e não apagam o histórico bruto</span>
      </li>
      <li>
        <span>Claim e fact são regravados só quando a evidência muda</span>
      </li>
      <li>
        <span>Versões novas preservam source checksum, timestamp e provenance chain</span>
      </li>
      <li>
        <span>Erro de rota ou evidência vazia deve aparecer explicitamente na UI</span>
      </li>
    </ul>
  </article>
</section>
