<script lang="ts">
  import type { PageData } from './$types';

  export let data: PageData;

  const scope = data.result?.resolved_scope;
</script>

<svelte:head>
  <title>Documentos | FonteAberta</title>
  <meta
    name="description"
    content="Busca oficial de documentos com recuperação vetorial, citações e evidência rastreavel."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Documentos oficiais</p>
      <h1>RAG com citação, sem extrapolação</h1>
    </div>

    <p class="lead">
      Esta frente indexa um documento oficial do TSE, resolve escopo antes da busca e retorna
      resposta, evidência e citações. O objetivo aqui é simples: mostrar de onde a resposta veio.
    </p>

    <form class="search-form" action="/documentos" method="get">
      <label class="sr-only" for="doc-q">Perguntar sobre documentos oficiais</label>
      <input
        id="doc-q"
        name="q"
        placeholder="Ex.: Para que o CANDex é utilizado?"
        value={data.query}
        autocomplete="off"
      />
      <button class="button" type="submit">Consultar</button>
    </form>

    <div class="toolbar">
      <span class="badge badge-accent">escopo oficial</span>
      <span class="badge">pgvector</span>
      <span class="badge">citações</span>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Estado da consulta</p>
      <h2>{data.result ? data.result.status : 'fallback'}</h2>
      <p class="note">
        {#if data.result}
          {data.result.resolved_scope.source_slug} · {data.result.resolved_scope.document_external_id}
        {:else}
          {data.errorMessage}
        {/if}
      </p>
    </div>

    {#if data.result}
      <div class="metric">
        <p class="metric-label">Modo de busca</p>
        <p class="metric-value">{data.result.retrieval_mode}</p>
        <p class="metric-note">
          {data.result.citations.length} citações e {data.result.evidence.length} evidências.
        </p>
      </div>
    {:else}
      <div class="metric">
        <p class="metric-label">Sem resposta</p>
        <p class="metric-value">0 citações</p>
        <p class="metric-note">
          A página continua renderizando para não quebrar a navegação pública.
        </p>
      </div>
    {/if}
  </aside>
</section>

{#if data.result}
  <section class="grid stack">
    <article class="card card-strong card-pad stack">
      <div class="section-title">
        <div>
          <p class="panel-title">Resposta recuperada</p>
          <h2>{data.result.question}</h2>
        </div>
        <span class="badge badge-accent">{data.result.citations.length} citações</span>
      </div>

      <p class="answer">{data.result.answer}</p>

      {#if scope}
        <div class="scope-row">
          <span class="scope-title">Escopo resolvido</span>
          <span class="badge">{scope.source_slug}</span>
          <span class="badge">{scope.document_external_id}</span>
          <span class="badge">{scope.document_type}</span>
        </div>

        <div class="keyword-row">
          {#each scope.keywords as keyword}
            <span class="chip">{keyword}</span>
          {/each}
        </div>
      {/if}
    </article>

    <div class="grid grid-2">
      {#each data.result.citations as citation, index}
        <article class="card card-pad citation-card stack">
          <div class="section-title">
            <div>
              <p class="panel-title">Citação {index + 1}</p>
              <h2>{citation.section ?? citation.document_title}</h2>
            </div>
            <span class="badge">{citation.page ? `p. ${citation.page}` : 'sem página'}</span>
          </div>

          <p class="quote">{citation.quote}</p>

          <div class="citation-meta">
            <span>{citation.source_name}</span>
            <a href={citation.source_url} target="_blank" rel="noreferrer">Abrir fonte oficial</a>
          </div>
        </article>
      {/each}
    </div>

    <article class="card card-pad stack">
      <div class="section-title">
        <div>
          <p class="panel-title">Evidência</p>
          <h2>Ranking híbrido</h2>
        </div>
        <span class="badge">{data.result.evidence.length} linhas</span>
      </div>

      <div class="evidence-list">
        {#each data.result.evidence as evidence, index}
          <div class="evidence-item">
            <div class="evidence-head">
              <span class="badge badge-accent">#{index + 1}</span>
              <span class="note">overlap {evidence.lexical_overlap} · distance {evidence.distance.toFixed(3)}</span>
            </div>
            <p>{evidence.quote}</p>
          </div>
        {/each}
      </div>
    </article>
  </section>
{/if}

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

  .answer,
  .quote,
  .evidence-item p {
    margin: 0;
    color: var(--text);
    line-height: 1.75;
  }

  .scope-row,
  .citation-meta,
  .evidence-head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    align-items: center;
  }

  .scope-row {
    padding-top: 0.45rem;
    border-top: 1px solid var(--line);
  }

  .scope-title {
    color: var(--muted);
    font-size: 0.88rem;
    font-weight: 600;
  }

  .keyword-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    padding: 0.45rem 0.75rem;
    border-radius: 999px;
    background: rgba(15, 118, 110, 0.08);
    color: var(--accent-strong);
    font-size: 0.82rem;
    font-weight: 600;
  }

  .citation-card {
    min-height: 100%;
  }

  .citation-meta {
    justify-content: space-between;
    color: var(--muted);
    font-size: 0.88rem;
  }

  .evidence-list {
    display: grid;
    gap: 0.85rem;
  }

  .evidence-item {
    padding-top: 0.85rem;
    border-top: 1px solid var(--line);
  }

  .evidence-head {
    justify-content: space-between;
    margin-bottom: 0.45rem;
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

    .citation-meta {
      align-items: flex-start;
    }
  }
</style>
