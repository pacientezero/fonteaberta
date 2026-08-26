<script lang="ts">
  import type { PageData } from './$types';
  import {
    dataRoute,
    homeRoute,
    legislativeDeputyRoute,
    legislativeRoute,
    legislativeVotesRoute,
    sourcesRoute,
  } from '$lib/navigation';
  import { formatPtBrDate, formatPtBrDateTime, formatPtBrNumber } from '$lib/format';

  export let data: PageData;

  const summary = data.vote;
  const proposition = summary?.proposition;
  const vote = summary?.vote;
  const members = summary?.members ?? [];
  const voteLabel = vote?.approved ? 'Aprovado' : 'Rejeitado';
  const yesVotes = vote?.yes_votes ?? 0;
  const noVotes = vote?.no_votes ?? 0;
  const otherVotes = vote?.other_votes ?? 0;
  const countedVotes = vote?.total_votes ?? 0;
</script>

<svelte:head>
  <title>{proposition ? `${proposition.sigla_tipo} ${proposition.number}/${proposition.year}` : 'Votação'} | FonteAberta</title>
  <meta
    name="description"
    content="Detalhe navegável da votação nominal da Camara dos Deputados com votos a favor, contra e registros oficiais."
  />
</svelte:head>

{#if summary && proposition && vote}
  <section class="hero">
    <div class="card card-strong card-pad stack">
      <div>
        <p class="eyebrow">Legislativo</p>
        <h1>{proposition.sigla_tipo} {proposition.number}/{proposition.year}</h1>
        <p class="lead">{vote.description}</p>
      </div>

      <p class="quote">{summary.claim?.statement ?? vote.result ?? 'Detalhe da votação nominal'}</p>

      <div class="toolbar">
        <a class="button" href={legislativeVotesRoute()}>Voltar ao catálogo</a>
        <a class="button-secondary" href={legislativeRoute()}>Ver resumo</a>
        <a class="button-secondary" href={dataRoute()}>Abrir cobertura</a>
        <a class="button-secondary" href={sourcesRoute()}>Ver fontes</a>
        <a class="button-secondary" href={homeRoute()}>Início</a>
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
          <dd class="metric-value">{formatPtBrNumber(yesVotes)}</dd>
          <p class="metric-note">Votos favoráveis contabilizados.</p>
        </div>

        <div class="metric">
          <dt class="metric-label">Não</dt>
          <dd class="metric-value">{formatPtBrNumber(noVotes)}</dd>
          <p class="metric-note">Votos contrários contabilizados.</p>
        </div>

        <div class="metric">
          <dt class="metric-label">Outros</dt>
          <dd class="metric-value">{formatPtBrNumber(otherVotes)}</dd>
          <p class="metric-note">Registros fora de sim/não.</p>
        </div>

        <div class="metric">
          <dt class="metric-label">Total contado</dt>
          <dd class="metric-value">{formatPtBrNumber(countedVotes)}</dd>
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
          <h2>{proposition.title}</h2>
        </div>
        <span class="badge badge-accent">{proposition.sigla_tipo}</span>
      </div>

      <ul class="list">
        <li>
          <span>Resumo</span>
          <span>{proposition.summary}</span>
        </li>
        <li>
          <span>Status</span>
          <span>{proposition.status}</span>
        </li>
        <li>
          <span>Apresentada em</span>
          <span>{formatPtBrDateTime(proposition.presented_at)}</span>
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
        <span class="badge">{formatPtBrNumber(members.length)} votos nominais</span>
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

      <div class="toolbar" style="margin-top: 1rem;">
        <a class="button" href={vote.source_url ?? '#'} target="_blank" rel="noreferrer">Abrir fonte oficial</a>
        <a class="button-secondary" href={proposition.source_url ?? '#'} target="_blank" rel="noreferrer">
          Ver proposição
        </a>
      </div>
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
                <a class="member-link" href={legislativeDeputyRoute(member.external_id)}>
                  <strong>{member.canonical_name}</strong>
                </a>
                <div class="soft">{member.external_id}</div>
              </td>
              <td>
                <strong>{member.party_acronym ?? 'N/I'}</strong>
                <div class="soft">{member.party_name ?? 'Sem partido resolvido'}</div>
              </td>
              <td>{(member.person_metadata['state'] as string | undefined) ?? member.birth_place ?? 'N/I'}</td>
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
  {:else}
  <section class="card section">
    <p class="note">Votação não encontrada.</p>
    <div class="toolbar">
      <a class="button" href={legislativeVotesRoute()}>Voltar ao catálogo</a>
      <a class="button-secondary" href={legislativeRoute()}>Ver resumo</a>
    </div>
  </section>
{/if}

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

  .member-link {
    color: inherit;
    text-decoration: none;
  }

  .member-link:hover strong {
    text-decoration: underline;
  }
</style>
