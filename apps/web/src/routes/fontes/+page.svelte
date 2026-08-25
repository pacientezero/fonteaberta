<script lang="ts">
  import type { PageData } from './$types';
  import {
    candidateRoute,
    candidateAssetsRoute,
    dataRoute,
    homeRoute,
    methodologyRoute,
    searchRoute,
  } from '$lib/navigation';
  import { formatPtBrDateTime, formatPtBrNumber } from '$lib/format';

  export let data: PageData;

  const summary = data.summary;
  const registryCards = data.coverage.cards.filter((card) => card.key !== 'tse-v1');
  const sourceMetadata = summary.source.metadata as Record<string, string | undefined>;

  function datasetMetadata(
    value: Record<string, unknown>,
  ): Record<string, string | undefined> {
    return value as Record<string, string | undefined>;
  }
</script>

<svelte:head>
  <title>Fontes oficiais | FonteAberta</title>
  <meta
    name="description"
    content="Pagina de fontes oficiais e datasets usados pela V1 presidencial 2026."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Fontes oficiais</p>
      <h1>Fonte, dataset e evidencia</h1>
      <p class="lead">
        Esta pagina mostra a base oficial que sustenta a resposta publica atual da V1.
        A cobertura viva das demais frentes aparece logo abaixo e em <a href={dataRoute()}>Dados</a>.
      </p>
    </div>

    <div class="toolbar">
      <a class="button" href={candidateRoute(summary.candidate.external_id)}>Abrir candidato</a>
      <a class="button-secondary" href={candidateAssetsRoute(summary.candidate.external_id)}>
        Abrir bens
      </a>
      <a class="button-secondary" href={searchRoute(summary.person.canonical_name)}>Buscar nome</a>
      <a class="button-secondary" href={dataRoute()}>Dados</a>
      <a class="button-secondary" href={methodologyRoute()}>Metodologia</a>
      <a class="button-secondary" href={homeRoute()}>Inicio</a>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Source registry</p>
      <h2>{summary.source.name}</h2>
      <p class="note">
        {summary.source.institution} · {summary.source.scope} · {summary.source.update_frequency}
      </p>
    </div>

    <div class="metric">
      <p class="metric-label">Base indexada</p>
      <p class="metric-value">{formatPtBrNumber(summary.datasets.length)}</p>
      <p class="metric-note">No momento, a V1 usa dois datasets do TSE.</p>
    </div>
  </aside>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Fonte</p>
        <h2>Registro oficial</h2>
      </div>
      <span class="badge badge-accent">{summary.source.slug}</span>
    </div>

    <ul class="list">
      <li>
        <span>Institution</span>
        <span>{summary.source.institution}</span>
      </li>
      <li>
        <span>Base URL</span>
        <span>{summary.source.base_url}</span>
      </li>
      <li>
        <span>Documentation</span>
        <span>{summary.source.documentation_url}</span>
      </li>
      <li>
        <span>License</span>
        <span>{summary.source.license}</span>
      </li>
      <li>
        <span>Official</span>
        <span>{summary.source.official ? 'yes' : 'no'}</span>
      </li>
    </ul>

    <p class="note">Portal: {sourceMetadata.portal_url}</p>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Evidence model</p>
        <h2>O que a UI deixa visivel</h2>
      </div>
      <span class="badge">{summary.provenance.candidate_raw_record.processing_status}</span>
    </div>

    <ul class="list">
      <li>
        <span>Source</span>
        <span>visible</span>
      </li>
      <li>
        <span>Dataset</span>
        <span>visible</span>
      </li>
      <li>
        <span>Raw records</span>
        <span>visible</span>
      </li>
      <li>
        <span>Claim evidence</span>
        <span>visible</span>
      </li>
    </ul>
  </article>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Datasets</p>
      <h2>Base oficial usada na V1</h2>
    </div>
    <span class="badge">{summary.datasets.length}</span>
  </div>

  <div class="grid grid-2">
    {#each summary.datasets as dataset}
      {@const metadata = datasetMetadata(dataset.metadata)}
      <article class="metric dataset-card">
        <p class="metric-label">{dataset.slug}</p>
        <p class="metric-value">{dataset.name}</p>
        <p class="metric-note">
          {dataset.resource_url}
        </p>
        <ul class="dataset-details">
          <li><span>External id</span><span>{dataset.external_id}</span></li>
          <li><span>Format</span><span>{dataset.format}</span></li>
          <li><span>Enabled</span><span>{dataset.enabled ? 'yes' : 'no'}</span></li>
          <li><span>Portal dataset</span><span>{metadata.portal_dataset_url}</span></li>
          <li><span>Resource kind</span><span>{metadata.resource_kind}</span></li>
        </ul>
      </article>
    {/each}
  </div>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Raw records</p>
        <h2>Primeiro registro rastreado</h2>
      </div>
      <span class="badge">{formatPtBrDateTime(summary.provenance.candidate_raw_record.collected_at)}</span>
    </div>

    <ul class="list">
      <li>
        <span>Record id</span>
        <span>{summary.provenance.candidate_raw_record.id}</span>
      </li>
      <li>
        <span>Dataset id</span>
        <span>{summary.provenance.candidate_raw_record.dataset_id}</span>
      </li>
      <li>
        <span>Payload hash</span>
        <span>{summary.provenance.candidate_raw_record.payload_hash}</span>
      </li>
      <li>
        <span>Source updated at</span>
        <span>{formatPtBrDateTime(summary.provenance.candidate_raw_record.source_updated_at)}</span>
      </li>
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Official narrative</p>
        <h2>O que esta fonte permite afirmar</h2>
      </div>
      <span class="badge badge-accent">claim</span>
    </div>

    <p class="quote">{summary.claim?.statement}</p>

    <p class="note">
      A UI publica a resposta, a origem e o calculo. Ela nao esconde a cadeia de provenance.
    </p>
  </article>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Cobertura viva</p>
      <h2>Fontes, APIs e documentos que já aparecem na UI</h2>
    </div>
    <span class="badge badge-accent">{registryCards.length} cards</span>
  </div>

  <div class="grid registry-grid">
    {#each registryCards as card}
      <article class="registry-card" style={`--accent:${card.accent};`}>
        <div class="registry-head">
          <div>
            <p class="eyebrow">{card.eyebrow}</p>
            <h3>{card.title}</h3>
          </div>
          <span class={card.status === 'ok' ? 'badge badge-accent' : 'badge'}>{card.statusLabel}</span>
        </div>

        <p class="registry-headline">{card.headline}</p>
        <p class="note">{card.description}</p>

        <dl class="registry-metrics">
          {#each card.metrics as metric}
            <div>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
            </div>
          {/each}
        </dl>

        <div class="toolbar registry-toolbar">
          <a
            class="button"
            href={card.primaryHref}
            target={card.primaryExternal ? '_blank' : undefined}
            rel={card.primaryExternal ? 'noreferrer' : undefined}
          >
            {card.primaryLabel}
          </a>
          {#if card.secondaryHref && card.secondaryLabel}
            <a
              class="button-secondary"
              href={card.secondaryHref}
              target={card.secondaryExternal ? '_blank' : undefined}
              rel={card.secondaryExternal ? 'noreferrer' : undefined}
            >
              {card.secondaryLabel}
            </a>
          {/if}
        </div>
      </article>
    {/each}
  </div>
</section>

<style>
  .dataset-card {
    padding: 1rem;
  }

  .dataset-details {
    margin: 0.8rem 0 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 0.5rem;
  }

  .dataset-details li {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    border-bottom: 1px solid var(--line);
    padding-bottom: 0.5rem;
  }

  .dataset-details li:last-child {
    border-bottom: 0;
    padding-bottom: 0;
  }

  .dataset-details span:last-child {
    text-align: right;
    color: var(--text);
  }

  .registry-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .registry-card {
    padding: 1rem;
    display: grid;
    gap: 0.85rem;
    border-top: 4px solid var(--accent);
    background: var(--surface-strong);
    box-shadow: inset 0 4px 0 var(--accent), var(--shadow);
  }

  .registry-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .registry-card h3 {
    margin: 0;
    font-size: 1.18rem;
    line-height: 1.1;
    letter-spacing: -0.04em;
  }

  .registry-headline {
    margin: 0;
    color: var(--text);
    font-size: 1.35rem;
    line-height: 1.05;
    font-weight: 700;
    letter-spacing: -0.04em;
  }

  .registry-metrics {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .registry-metrics dt {
    color: var(--muted);
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .registry-metrics dd {
    margin: 0.2rem 0 0;
    color: var(--text);
    font-weight: 600;
    line-height: 1.4;
  }

  .registry-toolbar {
    margin-top: 0.15rem;
  }

  .registry-toolbar .button,
  .registry-toolbar .button-secondary {
    flex: 1 1 10rem;
    justify-content: center;
  }

  @media (max-width: 1100px) {
    .registry-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
