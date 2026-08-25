<script lang="ts">
  import type { PageData } from './$types';
  import {
    candidateAssetsRoute,
    candidateRoute,
    dataRoute,
    methodologyRoute,
    searchRoute,
    sourcesRoute,
  } from '$lib/navigation';
  import { formatPtBrDateTime, formatPtBrNumber } from '$lib/format';

  export let data: PageData;

  const summary = data.summary;
  const sourceMetadata = summary.source.metadata as Record<string, string | undefined>;
</script>

<svelte:head>
  <title>FonteAberta | V1 presidencial 2026</title>
  <meta
    name="description"
    content="Consulta publica com provenance rastreavel para a V1 presidencial 2026."
  />
</svelte:head>

<div class="hero">
  <section class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Fato &gt; Evidencia &gt; Fonte oficial</p>
      <h1>Quanto o candidato declarou em patrimonio?</h1>
    </div>

    <p class="lead">
      A primeira resposta publica da V1 usa dados oficiais do TSE, calculo reproduzivel e
      trilha de evidencia visivel.
    </p>

    <form class="search-form" action={searchRoute()} method="get">
      <label class="sr-only" for="home-search">Buscar candidato por nome ou SQ_CANDIDATO</label>
      <input
        id="home-search"
        name="q"
        placeholder="Busque por nome ou SQ_CANDIDATO"
        autocomplete="off"
      />
      <button class="button" type="submit">Buscar</button>
    </form>

    <div class="toolbar">
      <a class="button" href={candidateRoute(summary.candidate.external_id)}>Abrir candidato</a>
      <a class="button-secondary" href={candidateAssetsRoute(summary.candidate.external_id)}>
        Ver bens
      </a>
      <a class="button-secondary" href={sourcesRoute()}>Ver fontes</a>
      <a class="button-secondary" href={dataRoute()}>Dados</a>
      <a class="button-secondary" href={methodologyRoute()}>Metodologia</a>
    </div>
  </section>

  <aside class="card card-pad stack answer-card">
    <div>
      <p class="eyebrow">Resposta em destaque</p>
      <h2>{summary.declared_assets_total.formatted}</h2>
      <p class="note">
        Patrimonio declarado de {summary.person.canonical_name}, calculado a partir de
        {formatPtBrNumber(summary.assets.length)} bens oficiais.
      </p>
    </div>

    {#if summary.claim}
      <p class="quote">{summary.claim.statement}</p>
    {/if}

    <dl class="stack stats">
      <div class="metric">
        <dt class="metric-label">Candidato</dt>
        <dd class="metric-value">{summary.person.canonical_name}</dd>
        <p class="metric-note">
          {summary.candidate.position} #{summary.candidate.ballot_number} · {summary.party?.acronym}
        </p>
      </div>

      <div class="metric">
        <dt class="metric-label">Coleta</dt>
        <dd class="metric-value">{formatPtBrDateTime(summary.provenance.candidate_raw_record.collected_at)}</dd>
        <p class="metric-note">Fonte oficial coletada na janela do pipeline.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Base oficial</dt>
        <dd class="metric-value">{summary.source.slug.toUpperCase()}</dd>
        <p class="metric-note">{summary.source.institution}</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Calculo</dt>
        <dd class="metric-value">{summary.declared_assets_total.calculation_method}</dd>
        <p class="metric-note">Somatorio dos bens declarados no dataset de patrimonio.</p>
      </div>
    </dl>
  </aside>
</div>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Provenience chain</p>
        <h2>Como a resposta e montada</h2>
      </div>
      <span class="badge badge-accent">{summary.provenance.claim_evidence.length} evidencias</span>
    </div>

    <ol class="list chain">
      <li>
        <span>
          <strong>Fonte oficial</strong>
          <span class="soft">TSE, portal de dados abertos</span>
        </span>
        <span>{summary.source.official ? 'official' : 'internal'}</span>
      </li>
      <li>
        <span>
          <strong>Datasets</strong>
          <span class="soft">
            {summary.datasets.map((dataset) => dataset.slug).join(' + ')}
          </span>
        </span>
        <span>{summary.datasets.length}</span>
      </li>
      <li>
        <span>
          <strong>Raw record</strong>
          <span class="soft">{summary.provenance.candidate_raw_record.id}</span>
        </span>
        <span>{summary.provenance.candidate_raw_record.processing_status}</span>
      </li>
      <li>
        <span>
          <strong>Claim</strong>
          <span class="soft">{summary.claim?.id}</span>
        </span>
        <span>{summary.provenance.asset_evidence.length} asset evidences</span>
      </li>
    </ol>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Escopo da V1</p>
        <h2>O que esta tela cobre agora</h2>
      </div>
      <span class="badge">Public UI</span>
    </div>

    <ul class="list">
      <li>
        <span>Resposta, fonte, dataset e registros usados</span>
        <span>visivel</span>
      </li>
      <li>
        <span>Busca por nome oficial ou SQ_CANDIDATO</span>
        <span>ativa</span>
      </li>
      <li>
        <span>Pagina do candidato e pagina de bens</span>
        <span>ativa</span>
      </li>
      <li>
        <span>Pagina de fontes oficiais</span>
        <span>ativa</span>
      </li>
    </ul>
  </article>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Cobertura completa</p>
      <h2>V1, documentos, economia e dados administrativos</h2>
    </div>
    <span class="badge badge-accent">novo</span>
  </div>

  <div class="grid grid-2">
    <div class="metric">
      <p class="metric-label">Dados</p>
      <p class="metric-value">Cobertura viva</p>
      <p class="metric-note">
        BCB, IBGE, Câmara, Senado, Transparência, Tesouro e Compras.gov agora aparecem
        juntos.
      </p>
    </div>

    <div class="metric">
      <p class="metric-label">Metodologia</p>
      <p class="metric-value">Contrato explícito</p>
      <p class="metric-note">
        A página metodológica explica atualização, cálculo, entidades, IA e correções.
      </p>
    </div>
  </div>

  <div class="toolbar" style="margin-top: 1rem;">
    <a class="button" href={dataRoute()}>Abrir dados</a>
    <a class="button-secondary" href={methodologyRoute()}>Ver metodologia</a>
  </div>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Fonte</p>
        <h2>{summary.source.name}</h2>
      </div>
      <span class="badge">official</span>
    </div>

    <ul class="list">
      <li>
        <span>Base URL</span>
        <span>{summary.source.base_url}</span>
      </li>
      <li>
        <span>Documentation</span>
        <span>{summary.source.documentation_url}</span>
      </li>
      <li>
        <span>Scope</span>
        <span>{summary.source.scope}</span>
      </li>
      <li>
        <span>License</span>
        <span>{summary.source.license}</span>
      </li>
    </ul>

    <p class="note">
      Portal:
      {sourceMetadata.portal_url}
    </p>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Datasets</p>
        <h2>Base indexada no slice atual</h2>
      </div>
      <span class="badge">{formatPtBrNumber(summary.datasets.length)} datasets</span>
    </div>

    <ul class="list">
      {#each summary.datasets as dataset}
        <li>
          <span>
            <strong>{dataset.name}</strong>
            <span class="soft">{dataset.resource_url}</span>
          </span>
          <span>{dataset.slug}</span>
        </li>
      {/each}
    </ul>
  </article>
</section>

<style>
  .search-form {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  .search-form input {
    flex: 1 1 18rem;
    min-width: 0;
    padding: 0.95rem 1rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.82);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
  }

  .search-form input:focus {
    outline: 2px solid rgba(15, 118, 110, 0.24);
    outline-offset: 2px;
  }

  .answer-card h2 {
    margin-top: 0.15rem;
  }

  .stats {
    gap: 0.75rem;
  }

  .stats .metric {
    background: rgba(255, 255, 255, 0.74);
  }

  .chain {
    gap: 0;
  }

  .chain li span {
    display: block;
  }

  .chain strong {
    display: block;
    margin-bottom: 0.15rem;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  @media (max-width: 900px) {
    .search-form input {
      flex-basis: 100%;
    }
  }
</style>
