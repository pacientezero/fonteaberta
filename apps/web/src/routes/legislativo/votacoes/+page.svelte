<script lang="ts">
  import type { PageData } from './$types';
  import {
    camaraVoteRoute,
    dataRoute,
    homeRoute,
    legislativeRoute,
    legislativeVotesRoute,
    sourcesRoute,
  } from '$lib/navigation';
  import { formatPtBrNumber } from '$lib/format';

  export let data: PageData;

  const filters = [
    { value: 'all' as const, label: 'Todas' },
    { value: 'nominal' as const, label: 'Nominais' },
    { value: 'symbolic' as const, label: 'Simbólicas' },
  ];
</script>

<svelte:head>
  <title>Votações | FonteAberta</title>
  <meta
    name="description"
    content="Catalogo filtravel das votacoes aprovadas da Camara dos Deputados com detalhe e fonte oficial."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Legislativo</p>
      <h1>Catálogo de votações</h1>
    </div>

    <p class="lead">
      Busque por título, tipo de proposição, resultado ou texto da votação para abrir a decisão
      oficial e, quando existir, a lista nominal de quem votou a favor e contra.
    </p>

    <form class="search-form" action={legislativeVotesRoute()} method="get">
      <label class="sr-only" for="vote-q">Buscar votação por texto, título ou resultado</label>
      <input
        id="vote-q"
        name="q"
        placeholder="Ex.: PLP 230/2025, aprovado, urgência..."
        value={data.query}
        autocomplete="off"
      />
      <input type="hidden" name="kind" value={data.kind} />
      <button class="button" type="submit">Filtrar</button>
    </form>

    <div class="toolbar filter-toolbar">
      {#each filters as filter}
        <a
          class={data.kind === filter.value ? 'button filter-chip' : 'button-secondary filter-chip'}
          href={legislativeVotesRoute({
            q: data.query || undefined,
            kind: filter.value,
          })}
        >
          {filter.label}
        </a>
      {/each}
    </div>

    <div class="toolbar">
      <a class="button-secondary" href={legislativeRoute()}>Ver resumo</a>
      <a class="button-secondary" href={dataRoute()}>Abrir cobertura</a>
      <a class="button-secondary" href={sourcesRoute()}>Ver fontes</a>
      <a class="button-secondary" href={homeRoute()}>Início</a>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Filtro atual</p>
      <h2>{data.kindLabel}</h2>
      <p class="note">
        {#if data.normalizedQuery}
          Resultado de busca por "{data.query}".
        {:else if data.kind === 'all'}
          Mostrando o catálogo carregado sem termo adicional.
        {:else}
          Mostrando apenas votações {data.kindLabel.toLowerCase()}.
        {/if}
      </p>
    </div>

    <dl class="stack stats">
      <div class="metric">
        <dt class="metric-label">Carregadas</dt>
        <dd class="metric-value">{formatPtBrNumber(data.loadedCount)}</dd>
        <p class="metric-note">Votações aprovadas retornadas pela API.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Nominais</dt>
        <dd class="metric-value">{formatPtBrNumber(data.nominalCount)}</dd>
        <p class="metric-note">Com lista de membros e voto individual.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Simbólicas</dt>
        <dd class="metric-value">{formatPtBrNumber(data.symbolicCount)}</dd>
        <p class="metric-note">Sem lista nominal no portal oficial.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Visíveis</dt>
        <dd class="metric-value">{formatPtBrNumber(data.votes.length)}</dd>
        <p class="metric-note">Após aplicar o filtro atual.</p>
      </div>
    </dl>
  </aside>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">{data.kindLabel}</p>
      <h2>{data.query ? 'Resultados filtrados' : 'Votações aprovadas recentes'}</h2>
      <p class="note">
        {#if data.normalizedQuery}
          {formatPtBrNumber(data.votes.length)} votação(ões) correspondem ao filtro atual.
        {:else}
          O catálogo expõe a trilha oficial para abrir cada decisão e navegar até a proposição.
        {/if}
      </p>
    </div>
    <span class="badge badge-accent">{formatPtBrNumber(data.votes.length)} registros</span>
  </div>

  {#if data.votes.length}
    <div class="vote-grid">
      {#each data.votes as item}
        <article class="vote-card">
          <div class="vote-head">
            <div>
              <p class="eyebrow">
                {item.proposition.sigla_tipo} {item.proposition.number}/{item.proposition.year}
              </p>
              <h3>{item.proposition.title}</h3>
            </div>
            <span class={item.vote.approved ? 'badge badge-accent' : 'badge'}>
              {item.vote.approved ? 'Aprovado' : 'Rejeitado'}
            </span>
          </div>

          <p class="vote-summary">{item.vote.description}</p>
          <p class="note">{item.vote.result ?? 'Resultado oficial não informado'}</p>

          <dl class="vote-metrics">
            <div>
              <dt>Sim</dt>
              <dd>{formatPtBrNumber(item.vote.yes_votes)}</dd>
            </div>
            <div>
              <dt>Não</dt>
              <dd>{formatPtBrNumber(item.vote.no_votes)}</dd>
            </div>
            <div>
              <dt>Outros</dt>
              <dd>{formatPtBrNumber(item.vote.other_votes)}</dd>
            </div>
            <div>
              <dt>Registros</dt>
              <dd>{formatPtBrNumber(item.member_count)}</dd>
            </div>
          </dl>

          <p class="note">
            {#if item.member_count > 0}
              Votação nominal com lista de parlamentares.
            {:else}
              Aprovação simbólica sem lista nominal no portal oficial.
            {/if}
          </p>

          <div class="toolbar vote-toolbar">
            <a class="button" href={camaraVoteRoute(item.vote.external_id)}>Abrir detalhe</a>
            <a class="button-secondary" href={item.vote.source_url ?? '#'} target="_blank" rel="noreferrer">
              Abrir fonte oficial
            </a>
            <a class="button-secondary" href={item.proposition.source_url ?? '#'} target="_blank" rel="noreferrer">
              Ver proposição
            </a>
          </div>
        </article>
      {/each}
    </div>
  {:else}
    <p class="note">
      Nenhuma votação corresponde ao filtro atual. Tente remover o termo de busca ou alternar entre
      votações nominais e simbólicas.
    </p>
  {/if}
</section>

<style>
  .vote-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .vote-card {
    padding: 1rem;
    border: 1px solid rgba(124, 58, 237, 0.15);
    border-radius: 1.35rem;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.7)),
      var(--surface-strong);
    box-shadow: var(--shadow);
    display: grid;
    gap: 0.85rem;
  }

  .vote-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .vote-head h3 {
    margin: 0.2rem 0 0;
    font-size: 1.15rem;
    line-height: 1.1;
  }

  .vote-summary {
    margin: 0;
    font-size: 1.03rem;
    line-height: 1.45;
    font-weight: 600;
  }

  .vote-metrics {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .vote-metrics dt {
    color: var(--muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .vote-metrics dd {
    margin: 0.15rem 0 0;
    font-size: 1rem;
    font-weight: 700;
  }

  .filter-toolbar {
    flex-wrap: wrap;
  }

  .filter-chip {
    min-width: 9.5rem;
    justify-content: center;
  }

  @media (max-width: 1100px) {
    .vote-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .vote-metrics {
      grid-template-columns: 1fr;
    }
  }
</style>
