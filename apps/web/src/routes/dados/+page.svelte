<script lang="ts">
  import type { PageData } from './$types';
  import {
    documentsRoute,
    homeRoute,
    methodologyRoute,
    searchRoute,
    sourcesRoute,
  } from '$lib/navigation';

  export let data: PageData;
</script>

<svelte:head>
  <title>Dados | FonteAberta</title>
  <meta
    name="description"
    content="Cobertura auditada das frentes publicas do FonteAberta: V1, RAG, economia, legislativo, transparencia, tesouro e compras."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Cobertura pública</p>
      <h1>Cobertura pública verificada</h1>
    </div>

    <p class="lead">
      A interface pública mostra as frentes já cobertas e o que ainda depende de complementação
      externa. A expansão legislativa está navegável; o TSE oficial já foi importado e a busca
      agora percorre o catálogo completo de candidatos e bens.
    </p>

    <div class="toolbar">
      <a class="button" href={homeRoute()}>Inicio</a>
      <a class="button-secondary" href={searchRoute()}>Busca</a>
      <a class="button-secondary" href={documentsRoute()}>Documentos</a>
      <a class="button-secondary" href={sourcesRoute()}>Fontes</a>
      <a class="button-secondary" href={methodologyRoute()}>Metodologia</a>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Resumo</p>
      <h2>{data.summary[2].value}</h2>
      <p class="note">{data.summary[2].note}</p>
    </div>

    {#each data.summary as item}
      <div class="metric">
        <p class="metric-label">{item.label}</p>
        <p class="metric-value">{item.value}</p>
        <p class="metric-note">{item.note}</p>
      </div>
    {/each}
  </aside>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Auditoria de cobertura</p>
      <h2>Estado real do sistema</h2>
    </div>
    <span class="badge badge-accent">auditado</span>
  </div>

  <div class="audit-grid">
    {#each data.audit as item}
      <article class="audit-card">
        <div class="audit-head">
          <div>
            <p class="eyebrow">
              {item.status === 'ok' ? 'Coberto' : item.status === 'partial' ? 'Parcial' : 'Bloqueado'}
            </p>
            <h3>{item.title}</h3>
          </div>
          <span class={item.status === 'ok' ? 'badge badge-accent' : 'badge'}>{item.status}</span>
        </div>

        <p class="note">{item.detail}</p>
        <p class="audit-evidence">{item.evidence}</p>

        <div class="toolbar audit-toolbar">
          <a class="button-secondary" href={item.href}>{item.label}</a>
        </div>
      </article>
    {/each}
  </div>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Leitura rápida</p>
      <h2>O que já está exposto publicamente</h2>
    </div>
    <span class="badge badge-accent">live</span>
  </div>

  <div class="grid grid-2 summary-grid">
    {#each data.summary as item}
      <article class="metric summary-card">
        <p class="metric-label">{item.label}</p>
        <p class="metric-value">{item.value}</p>
        <p class="metric-note">{item.note}</p>
      </article>
    {/each}
  </div>
</section>

<section class="grid coverage-grid">
  {#each data.cards as card}
    <article class="card coverage-card stack" style={`--accent:${card.accent};`}>
      <div class="coverage-head">
        <div>
          <p class="eyebrow">{card.eyebrow}</p>
          <h2>{card.title}</h2>
        </div>
        <span class={card.status === 'ok' ? 'badge badge-accent' : 'badge'}>{card.statusLabel}</span>
      </div>

      <div class="coverage-headline">{card.headline}</div>
      <p class="note">{card.description}</p>

      <dl class="coverage-metrics">
        {#each card.metrics as metric}
          <div>
            <dt>{metric.label}</dt>
            <dd>{metric.value}</dd>
          </div>
        {/each}
      </dl>

      <div class="toolbar coverage-toolbar">
        <a class="button" href={card.primaryHref}>{card.primaryLabel}</a>
        {#if card.secondaryHref && card.secondaryLabel}
          <a class="button-secondary" href={card.secondaryHref}>{card.secondaryLabel}</a>
        {/if}
      </div>
    </article>
  {/each}
</section>

<style>
  .summary-grid {
    margin-top: 1rem;
  }

  .summary-card {
    padding: 1rem;
  }

  .audit-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .audit-card {
    padding: 1rem;
    border-radius: 1.35rem;
    border: 1px solid var(--line);
    background: var(--surface-strong);
    box-shadow: var(--shadow);
    display: grid;
    gap: 0.85rem;
  }

  .audit-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .audit-head h3 {
    margin: 0.2rem 0 0;
    font-size: 1.1rem;
    line-height: 1.15;
  }

  .audit-evidence {
    margin: 0;
    color: var(--muted);
    font-size: 0.95rem;
    line-height: 1.45;
  }

  .audit-toolbar {
    margin-top: 0.05rem;
  }

  .audit-toolbar .button-secondary {
    width: fit-content;
  }

  .coverage-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .coverage-card {
    padding: 1.1rem;
    border-top: 4px solid var(--accent);
    background: var(--surface-strong);
    box-shadow: inset 0 4px 0 var(--accent), var(--shadow);
  }

  .coverage-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .coverage-headline {
    font-size: clamp(1.2rem, 2vw, 1.75rem);
    line-height: 1.05;
    font-weight: 700;
    letter-spacing: -0.04em;
  }

  .coverage-metrics {
    margin: 0.2rem 0 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .coverage-metrics dt {
    color: var(--muted);
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .coverage-metrics dd {
    margin: 0.2rem 0 0;
    color: var(--text);
    font-weight: 600;
    line-height: 1.4;
  }

  .coverage-toolbar {
    margin-top: 0.2rem;
  }

  .coverage-toolbar .button,
  .coverage-toolbar .button-secondary {
    flex: 1 1 10rem;
    justify-content: center;
  }

  @media (max-width: 1100px) {
    .audit-grid,
    .coverage-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .audit-grid,
    .coverage-grid,
    .coverage-metrics {
      grid-template-columns: 1fr;
    }
  }
</style>
