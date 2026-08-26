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
      A V1 indexa os candidatos oficiais de 2026 disponíveis no banco.
      Busque pelo nome oficial, partido ou pelo SQ_CANDIDATO e abra a trilha de evidência.
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
      <a class="button-secondary" href={dataRoute()}>Dados</a>
      <a class="button-secondary" href={methodologyRoute()}>Metodologia</a>
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
          Tente o nome oficial, o partido ou o SQ_CANDIDATO.
        </p>
      </div>
    {:else}
      <div class="metric">
        <p class="metric-label">Candidatos indexados</p>
        <p class="metric-value">{formatPtBrNumber(data.catalogCount)}</p>
        <p class="metric-note">
          A busca agora pode percorrer o catálogo, não apenas o destaque fixo.
        </p>
      </div>
    {/if}
  </aside>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Atalhos oficiais</p>
      <h2>Nomes já confirmados em atas públicas</h2>
    </div>
    <span class="badge badge-accent">{data.officialRoster.length} candidatos</span>
  </div>

  <p class="note">
    Estes nomes seguem como atalhos rápidos para as atas públicas do TSE, enquanto a busca percorre o
    catálogo oficial completo importado para o banco.
  </p>

  <div class="roster-grid">
    {#each data.officialRoster as nomination}
      <article class="roster-card">
        <div class="roster-head">
          <div>
            <p class="eyebrow">
              {nomination.partyAcronym} · Nº {nomination.ballotNumber}
            </p>
            <h3>{nomination.displayName}</h3>
          </div>
          <span class={nomination.imported ? 'badge badge-accent' : 'badge'}>
            {nomination.imported ? 'importado' : 'ata pública'}
          </span>
        </div>

        <p class="note">
          {#if nomination.imported}
            Já existe ficha local para este nome. O atalho abre o candidato importado.
          {:else}
            Ainda não existe ficha local. O atalho abre a ata oficial que confirma a indicação.
          {/if}
        </p>

        <div class="toolbar roster-toolbar">
          <a class="button" href={nomination.openHref}>{nomination.openLabel}</a>
          <a class="button-secondary" href={nomination.searchHref}>Buscar nome</a>
        </div>
      </article>
    {/each}
  </div>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">{data.query ? 'Resultados' : 'Catálogo'}</p>
      <h2>{data.query ? 'Candidatos que correspondem à busca' : 'Candidatos oficiais indexados'}</h2>
    </div>
    <span class="badge badge-accent">{formatPtBrNumber(data.candidates.length)} candidatos</span>
  </div>

  {#if data.candidates.length}
    <div class="candidate-grid">
      {#each data.candidates as candidate}
        <article class="candidate-card">
          <div class="candidate-head">
            <div>
              <p class="eyebrow">
                {candidate.candidate.position ?? 'PRESIDENTE'} · {candidate.party?.acronym ?? 'Sem partido'}
              </p>
              <h3>{candidate.person.canonical_name}</h3>
            </div>
            <span class="badge">{candidate.candidate.external_id}</span>
          </div>

          <p class="note">{candidate.claim?.statement ?? 'Patrimônio calculado a partir dos bens oficiais.'}</p>

          <dl class="candidate-metrics">
            <div>
              <dt>Bens</dt>
              <dd>{formatPtBrNumber(candidate.assets.length)}</dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd>{candidate.declared_assets_total.formatted}</dd>
            </div>
            <div>
              <dt>Coleta</dt>
              <dd>{formatPtBrDateTime(candidate.provenance.candidate_raw_record.collected_at)}</dd>
            </div>
          </dl>

          <div class="toolbar candidate-toolbar">
            <a class="button" href={candidateRoute(candidate.candidate.external_id)}>Abrir candidato</a>
            <a class="button-secondary" href={candidateAssetsRoute(candidate.candidate.external_id)}>
              Ver bens
            </a>
          </div>
        </article>
      {/each}
    </div>
  {:else}
    <p class="note">
      Nenhum candidato corresponde ao filtro atual. Tente nome completo, partido ou SQ_CANDIDATO,
      ou limpe a busca para ver o catálogo.
    </p>
  {/if}
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
  .candidate-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .roster-grid {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .roster-card {
    padding: 1rem;
    border: 1px solid rgba(37, 99, 235, 0.15);
    border-radius: 1.35rem;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.7)),
      var(--surface-strong);
    box-shadow: var(--shadow);
  }

  .roster-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .roster-head h3 {
    margin: 0.1rem 0 0;
    font-size: 1.2rem;
  }

  .roster-toolbar {
    margin-top: 0.9rem;
  }

  .roster-toolbar .button,
  .roster-toolbar .button-secondary {
    flex: 1 1 10rem;
    justify-content: center;
  }

  .candidate-card {
    padding: 1rem;
    border: 1px solid rgba(15, 118, 110, 0.15);
    border-radius: 1.35rem;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.7)),
      var(--surface-strong);
    box-shadow: var(--shadow);
  }

  .candidate-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .candidate-head h3 {
    margin: 0.1rem 0 0;
    font-size: 1.35rem;
  }

  .candidate-metrics {
    margin: 0.85rem 0 0;
    display: grid;
    gap: 0.75rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .candidate-metrics dt {
    color: var(--muted);
    font-size: 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .candidate-metrics dd {
    margin: 0.25rem 0 0;
    font-weight: 600;
    color: var(--text);
    line-height: 1.35;
  }

  .candidate-toolbar {
    margin-top: 0.9rem;
  }

  .candidate-toolbar .button,
  .candidate-toolbar .button-secondary {
    flex: 1 1 10rem;
    justify-content: center;
  }

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

    .candidate-grid,
    .roster-grid,
    .candidate-metrics {
      grid-template-columns: 1fr;
    }
  }
</style>
