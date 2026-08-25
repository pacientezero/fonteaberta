<script lang="ts">
  import type { PageData } from './$types';
  import { dataRoute, homeRoute, sourcesRoute } from '$lib/navigation';
  import { formatPtBrDate, formatPtBrDateTime, formatPtBrNumber } from '$lib/format';

  export let data: PageData;

  const summary = data.vote;
  const propositionMetadata = summary.proposition;
  const vote = summary.vote;
  const members = summary.members;
  const recentVotes = data.recentVotes ?? [];
  const nominalRecentVotes = recentVotes.filter((item) => item.member_count > 0);
  const symbolicRecentVotes = recentVotes.filter((item) => item.member_count === 0);
  const counts = {
    yes: vote.yes_votes,
    no: vote.no_votes,
    other: vote.other_votes,
    counted: vote.total_votes,
    members: members.length,
  };
  const voteLabel = vote.approved ? 'Aprovado' : 'Rejeitado';
</script>

<svelte:head>
  <title>Legislativo | FonteAberta</title>
  <meta
    name="description"
    content="Projeto aprovado, votacao nominal e lista de votos oficiais da Camara dos Deputados."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Legislativo</p>
      <h1>{propositionMetadata.sigla_tipo} {propositionMetadata.number}/{propositionMetadata.year}</h1>
      <p class="lead">
        {vote.description}
      </p>
    </div>

    <p class="quote">{summary.claim?.statement}</p>

    <div class="toolbar">
      <a class="button" href={dataRoute()}>Abrir cobertura</a>
      <a class="button-secondary" href={sourcesRoute()}>Ver fontes</a>
      <a class="button-secondary" href={homeRoute()}>Inicio</a>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Resultado</p>
      <h2>{voteLabel}</h2>
      <p class="note">
        {formatPtBrDate(vote.vote_date)} · {formatPtBrDateTime(vote.vote_timestamp)}
      </p>
    </div>

    <dl class="stack stats">
      <div class="metric">
        <dt class="metric-label">Sim</dt>
        <dd class="metric-value">{formatPtBrNumber(counts.yes)}</dd>
        <p class="metric-note">Votos favoráveis contabilizados.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Não</dt>
        <dd class="metric-value">{formatPtBrNumber(counts.no)}</dd>
        <p class="metric-note">Votos contrários contabilizados.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Outros</dt>
        <dd class="metric-value">{formatPtBrNumber(counts.other)}</dd>
        <p class="metric-note">Registros fora de sim/não.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Total contado</dt>
        <dd class="metric-value">{formatPtBrNumber(counts.counted)}</dd>
        <p class="metric-note">Base usada no resultado oficial.</p>
      </div>
    </dl>
  </aside>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Proposição</p>
        <h2>{propositionMetadata.title}</h2>
      </div>
      <span class="badge badge-accent">{propositionMetadata.sigla_tipo}</span>
    </div>

    <ul class="list">
      <li>
        <span>Resumo</span>
        <span>{propositionMetadata.summary}</span>
      </li>
      <li>
        <span>Status</span>
        <span>{propositionMetadata.status}</span>
      </li>
      <li>
        <span>Apresentada em</span>
        <span>{formatPtBrDateTime(propositionMetadata.presented_at)}</span>
      </li>
      <li>
        <span>Fonte</span>
        <span>{summary.source.name}</span>
      </li>
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Votação</p>
        <h2>{vote.result}</h2>
      </div>
      <span class="badge">{formatPtBrNumber(counts.members)} votos nominais</span>
    </div>

    <ul class="list">
      <li>
        <span>Descrição</span>
        <span>{vote.description}</span>
      </li>
      <li>
        <span>Órgão</span>
        <span>{vote.house}</span>
      </li>
      <li>
        <span>Coleta</span>
        <span>{formatPtBrDateTime(vote.collected_at)}</span>
      </li>
      <li>
        <span>Resultado oficial</span>
        <span>{vote.approved ? 'aprovado' : 'rejeitado'}</span>
      </li>
    </ul>
  </article>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Votos nominais</p>
      <h2>Quem votou a favor e contra</h2>
    </div>
    <span class="badge badge-accent">{formatPtBrNumber(members.length)} registros</span>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Parlamentar</th>
          <th>Partido</th>
          <th>UF</th>
          <th>Voto</th>
          <th>Registro</th>
        </tr>
      </thead>
      <tbody>
        {#each members as member}
          <tr>
            <td>
              <strong>{member.canonical_name}</strong>
              <div class="soft">{member.external_id}</div>
            </td>
            <td>
              <strong>{member.party_acronym ?? 'N/I'}</strong>
              <div class="soft">{member.party_name ?? 'Sem partido resolvido'}</div>
            </td>
            <td>
              {(member.person_metadata['state'] as string | undefined) ?? member.birth_place ?? 'N/I'}
            </td>
            <td>
              <strong>{member.vote_label}</strong>
              <div class="soft">{member.vote_value}</div>
            </td>
            <td>
              <div class="soft">{formatPtBrDateTime(member.source_updated_at)}</div>
              <div class="soft">{member.source_url}</div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Cobertura recente</p>
      <h2>Votações aprovadas recentes</h2>
      <p class="note">
        {formatPtBrNumber(nominalRecentVotes.length)} nominais com lista de membros e
        {formatPtBrNumber(symbolicRecentVotes.length)} simbólicas sem voto individual.
      </p>
    </div>
    <span class="badge badge-accent">{formatPtBrNumber(recentVotes.length)} votações</span>
  </div>

  {#if recentVotes.length}
    <div class="recent-grid">
      {#each recentVotes as item}
        <article class="recent-card">
          <div class="recent-head">
            <div>
              <p class="eyebrow">{item.proposition.sigla_tipo} {item.proposition.number}/{item.proposition.year}</p>
              <h3>{item.proposition.title}</h3>
            </div>
            <span class={item.vote.approved ? 'badge badge-accent' : 'badge'}>
              {item.vote.approved ? 'Aprovado' : 'Rejeitado'}
            </span>
          </div>

          <p class="recent-headline">{item.vote.description}</p>
          <p class="note">
            {#if item.member_count > 0}
              {item.vote.result ?? 'Resultado oficial não informado'}
            {:else}
              Aprovação simbólica sem lista nominal no portal oficial
            {/if}
          </p>

          <dl class="recent-metrics">
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

          {#if item.member_count === 0}
            <p class="note">
              Este registro é simbólico, sem votos individuais. Ele ainda preserva fonte,
              proposição e claim oficial.
            </p>
          {/if}

          <div class="toolbar recent-toolbar">
            <a class="button" href={item.vote.source_url ?? '#'} target="_blank" rel="noreferrer">
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
    <p class="note">Nenhuma votação nominal recente foi carregada ainda.</p>
  {/if}
</section>

<style>
  .soft {
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.45;
    word-break: break-word;
  }

  .table-wrap table {
    min-width: 980px;
  }

  .recent-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
  }

  .recent-card {
    padding: 1rem;
    border-radius: 1.35rem;
    border: 1px solid var(--line);
    background: var(--surface-strong);
    box-shadow: var(--shadow);
    display: grid;
    gap: 0.85rem;
  }

  .recent-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
  }

  .recent-head h3 {
    margin: 0.2rem 0 0;
    font-size: 1.15rem;
    line-height: 1.1;
  }

  .recent-headline {
    margin: 0;
    font-size: 1.05rem;
    line-height: 1.45;
    font-weight: 600;
  }

  .recent-metrics {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .recent-metrics dt {
    color: var(--muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .recent-metrics dd {
    margin: 0.15rem 0 0;
    font-size: 1rem;
    font-weight: 700;
  }

  .recent-toolbar {
    margin-top: 0.05rem;
  }

  .recent-toolbar .button,
  .recent-toolbar .button-secondary {
    flex: 1 1 10rem;
    justify-content: center;
  }

  @media (max-width: 1100px) {
    .recent-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .recent-grid,
    .recent-metrics {
      grid-template-columns: 1fr;
    }
  }
</style>
