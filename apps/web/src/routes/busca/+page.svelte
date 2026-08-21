<script lang="ts">
  import type { PageData } from './$types';
  import { candidateAssetsRoute, candidateRoute, searchRoute, sourcesRoute } from '$lib/navigation';

  export let data: PageData;

  const summary = data.summary;
</script>

<svelte:head>
  <title>Busca | FonteAberta</title>
  <meta
    name="description"
    content="Busca publica da V1 para localizar o candidato e navegar pela evidencia oficial."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Busca publica</p>
      <h1>Encontre o candidato na base oficial</h1>
    </div>

    <p class="lead">
      A V1 indexa uma pergunta central: patrimonio declarado na eleicao presidencial 2026.
      Busque pelo nome oficial ou pelo SQ_CANDIDATO.
    </p>

    <form class="search-form" action={searchRoute()} method="get">
      <label class="sr-only" for="search-q">Buscar candidato por nome ou SQ_CANDIDATO</label>
      <input
        id="search-q"
        name="q"
        placeholder="Ex.: RENAN ANTONIO FERREIRA DOS SANTOS"
        value={data.query}
        autocomplete="off"
      />
      <button class="button" type="submit">Buscar</button>
    </form>

    <div class="toolbar">
      <a class="button-secondary" href={candidateRoute(summary.candidate.external_id)}>Abrir exemplo</a>
      <a class="button-secondary" href={candidateAssetsRoute(summary.candidate.external_id)}>
        Ver bens
      </a>
      <a class="button-secondary" href={sourcesRoute()}>Ver fontes</a>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Dica</p>
      <h2>{summary.person.canonical_name}</h2>
      <p class="note">
        SQ_CANDIDATO {summary.candidate.external_id} · {summary.party?.acronym} ·
        {summary.declared_assets_total.formatted}
      </p>
    </div>

    {#if data.result}
      <div class="metric">
        <p class="metric-label">Resultado encontrado</p>
        <p class="metric-value">{data.result.declared_assets_total.formatted}</p>
        <p class="metric-note">{data.result.claim?.statement}</p>
      </div>
    {:else if data.query}
      <div class="metric">
        <p class="metric-label">Nenhuma correspondencia</p>
        <p class="metric-value">0 resultados</p>
        <p class="metric-note">
          A V1 responde apenas a este slice oficial no momento. Tente o nome exato ou o
          SQ_CANDIDATO acima.
        </p>
      </div>
    {:else}
      <div class="metric">
        <p class="metric-label">Exemplo indexado</p>
        <p class="metric-value">{summary.assets.length} bens</p>
        <p class="metric-note">
          A busca pode ser usada para entrar na pagina do candidato sem decorar a rota.
        </p>
      </div>
    {/if}
  </aside>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Pesquisa</p>
        <h2>Como usar a busca</h2>
      </div>
      <span class="badge badge-accent">public</span>
    </div>

    <ol class="list">
      <li>
        <span>Digite o nome oficial ou o SQ_CANDIDATO</span>
        <span>1</span>
      </li>
      <li>
        <span>Abra o candidato encontrado</span>
        <span>2</span>
      </li>
      <li>
        <span>Navegue para bens, fonte e registros usados</span>
        <span>3</span>
      </li>
    </ol>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Exemplo oficial</p>
        <h2>{summary.person.canonical_name}</h2>
      </div>
      <span class="badge">{summary.candidate.external_id}</span>
    </div>

    <p class="quote">{summary.claim?.statement}</p>

    <div class="toolbar" style="margin-top: 1rem;">
      <a class="button" href={candidateRoute(summary.candidate.external_id)}>Abrir candidato</a>
      <a class="button-secondary" href={candidateAssetsRoute(summary.candidate.external_id)}>
        Abrir bens
      </a>
    </div>
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
  }

  .search-form input:focus {
    outline: 2px solid rgba(15, 118, 110, 0.24);
    outline-offset: 2px;
  }

  .toolbar {
    margin-top: 0.2rem;
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
