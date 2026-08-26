<script lang="ts">
  import type { PageData } from './$types';
  import {
    dataRoute,
    homeRoute,
    legislativeRoute,
    legislativeVotesRoute,
    sourcesRoute,
    camaraVoteRoute,
  } from '$lib/navigation';
  import { formatPtBrDateTime, formatPtBrNumber } from '$lib/format';

  export let data: PageData;

  const summary = data.mandate;
  const history = data.vote_history ?? [];
  const counts = data.vote_history_counts ?? {
    yes_votes: 0,
    no_votes: 0,
    other_votes: 0,
    total_votes: history.length,
  };
  const latestVote = history[0];
  const partyLabel = summary.party_acronym_resolved ?? summary.party_acronym ?? 'Sem partido';
  const legislatureMatch = summary.legislature_external_id?.match(/(\d+)/);
  const legislatureLabel = legislatureMatch
    ? `${legislatureMatch[1]}ª legislatura`
    : summary.legislature_external_id ?? 'Não informado';

  function voteToneLabel(value: string): string {
    if (value === 'sim') {
      return 'A favor';
    }
    if (value === 'nao') {
      return 'Contra';
    }
    return 'Outro';
  }
</script>

<svelte:head>
  <title>{summary.canonical_name} | FonteAberta</title>
  <meta
    name="description"
    content="Histórico nominal de votações aprovadas de um deputado federal com mandato oficial, fonte e evidência."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Legislativo</p>
      <h1>{summary.canonical_name}</h1>
      <p class="lead">
        Deputado federal #{data.deputyId} · {partyLabel} · {summary.state ?? 'BR'}
      </p>
    </div>

    <p class="quote">{summary.claim_statement ?? summary.electoral_name ?? 'Mandato atual da Câmara'}</p>

    <div class="toolbar">
      <a class="button" href={legislativeRoute()}>Ver resumo</a>
      <a class="button-secondary" href={legislativeVotesRoute()}>Abrir catálogo</a>
      <a class="button-secondary" href={dataRoute()}>Abrir cobertura</a>
      <a class="button-secondary" href={sourcesRoute()}>Ver fontes</a>
      <a class="button-secondary" href={homeRoute()}>Início</a>
      {#if summary.profile_url}
        <a class="button-secondary" href={summary.profile_url} target="_blank" rel="noreferrer">
          Perfil oficial
        </a>
      {/if}
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Histórico</p>
      <h2>{formatPtBrNumber(counts.total_votes)}</h2>
      <p class="note">Votações aprovadas com registro nominal.</p>
    </div>

    <dl class="stack stats">
      <div class="metric">
        <dt class="metric-label">A favor</dt>
        <dd class="metric-value">{formatPtBrNumber(counts.yes_votes)}</dd>
        <p class="metric-note">Votos de apoio ao projeto aprovado.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Contra</dt>
        <dd class="metric-value">{formatPtBrNumber(counts.no_votes)}</dd>
        <p class="metric-note">Votos contrários ao projeto aprovado.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Outros</dt>
        <dd class="metric-value">{formatPtBrNumber(counts.other_votes)}</dd>
        <p class="metric-note">Registros fora de sim e não.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Última votação</dt>
        <dd class="metric-value">
          {latestVote ? formatPtBrDateTime(latestVote.vote.vote_timestamp) : 'Não informado'}
        </dd>
        <p class="metric-note">Mais recente no recorte nominal aprovado.</p>
      </div>
    </dl>
  </aside>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Mandato atual</p>
        <h2>Contexto oficial do parlamentar</h2>
      </div>
      <span class="badge badge-accent">{partyLabel}</span>
    </div>

    <ul class="list">
      <li>
        <span>Nome eleitoral</span>
        <span>{summary.electoral_name ?? 'Não informado'}</span>
      </li>
      <li>
        <span>Estado</span>
        <span>{summary.state ?? 'Não informado'}</span>
      </li>
      <li>
        <span>Status</span>
        <span>{summary.status ?? 'Não informado'}</span>
      </li>
      <li>
        <span>Legislatura</span>
        <span>{legislatureLabel}</span>
      </li>
      <li>
        <span>Coleta</span>
        <span>{formatPtBrDateTime(summary.collected_at)}</span>
      </li>
      <li>
        <span>Perfil oficial</span>
        <span>{summary.profile_url ?? 'Não informado'}</span>
      </li>
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Proveniência</p>
        <h2>Fonte, claim e evidências</h2>
      </div>
      <span class="badge">{summary.source_slug}</span>
    </div>

    <ul class="list">
      <li>
        <span>Fonte</span>
        <span>{summary.source_name}</span>
      </li>
      <li>
        <span>Dataset</span>
        <span>{summary.dataset_slug}</span>
      </li>
      <li>
        <span>Claim</span>
        <span>{summary.claim_statement ?? 'Não informado'}</span>
      </li>
      <li>
        <span>Fact</span>
        <span>{summary.fact_value_text ?? 'Não informado'}</span>
      </li>
      <li>
        <span>Evidence</span>
        <span>{summary.evidence_id ?? 'Não informado'}</span>
      </li>
      <li>
        <span>Raw record</span>
        <span>{summary.raw_record_id ?? 'Não informado'}</span>
      </li>
    </ul>
  </article>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Votações aprovadas</p>
      <h2>Onde votou a favor e contra</h2>
      <p class="note">
        {formatPtBrNumber(history.length)} votação(ões) nominais aprovadas no recorte atual.
      </p>
    </div>
    <span class="badge badge-accent">{formatPtBrNumber(history.length)} registros</span>
  </div>

  {#if history.length}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Proposição</th>
            <th>Voto</th>
            <th>Partido</th>
            <th>Resultado</th>
            <th>Registro</th>
          </tr>
        </thead>
        <tbody>
          {#each history as item}
            <tr>
              <td>
                <a class="vote-link" href={camaraVoteRoute(item.vote.external_id)}>
                  <strong>
                    {item.proposition.sigla_tipo} {item.proposition.number}/{item.proposition.year}
                  </strong>
                </a>
                <div class="soft">{item.proposition.title}</div>
              </td>
              <td>
                <strong>{item.member_vote.vote_label}</strong>
                <div class="soft">{voteToneLabel(item.member_vote.vote_value)}</div>
              </td>
              <td>
                <strong>{item.member_vote.party_acronym ?? 'N/I'}</strong>
                <div class="soft">{item.member_vote.party_name ?? 'Sem partido resolvido'}</div>
              </td>
              <td>
                <span class={item.vote.approved ? 'badge badge-accent' : 'badge'}>
                  {item.vote.approved ? 'Aprovado' : 'Rejeitado'}
                </span>
                <div class="soft">{item.vote.result ?? 'Resultado não informado'}</div>
              </td>
              <td>
                <div class="soft">{formatPtBrDateTime(item.vote.vote_timestamp)}</div>
                <div class="soft">{item.vote.source_url}</div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <p class="note">
      Nenhuma votação nominal aprovada foi encontrada para este mandato no recorte atual.
    </p>
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
    min-width: 1100px;
  }

  .vote-link {
    color: inherit;
    text-decoration: none;
  }

  .vote-link:hover strong {
    text-decoration: underline;
  }
</style>
