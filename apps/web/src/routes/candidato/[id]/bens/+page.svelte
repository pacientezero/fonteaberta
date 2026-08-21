<script lang="ts">
  import type { PageData } from './$types';
  import { candidateRoute, homeRoute, searchRoute, sourcesRoute } from '$lib/navigation';
  import { formatPtBrDateTime, formatPtBrMoney, formatPtBrNumber } from '$lib/format';

  export let data: PageData;

  const summary = data.summary;
  const sourceMetadata = summary.source.metadata as Record<string, string | undefined>;
</script>

<svelte:head>
  <title>Bens de {summary.person.canonical_name} | FonteAberta</title>
  <meta
    name="description"
    content="Pagina de bens declarados com valores, evidencias e raw records oficiais."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Pagina de bens</p>
      <h1>Bens declarados</h1>
      <p class="lead">
        {summary.person.canonical_name} declarou {formatPtBrNumber(summary.assets.length)} bens,
        somando {summary.declared_assets_total.formatted}.
      </p>
    </div>

    <div class="toolbar">
      <a class="button" href={candidateRoute(summary.candidate.external_id)}>Voltar ao candidato</a>
      <a class="button-secondary" href={sourcesRoute()}>Ver fontes</a>
      <a class="button-secondary" href={searchRoute(summary.person.canonical_name)}>Buscar nome</a>
      <a class="button-secondary" href={homeRoute()}>Inicio</a>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Soma verificada</p>
      <h2>{summary.declared_assets_total.formatted}</h2>
      <p class="note">{summary.claim?.calculation_method}</p>
    </div>

    <div class="metric">
      <p class="metric-label">Evidence chain</p>
      <p class="metric-value">{summary.provenance.asset_evidence.length}</p>
      <p class="metric-note">
        Cada bem aponta para um raw record e um hash de payload oficial.
      </p>
    </div>
  </aside>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Tabela de bens</p>
      <h2>Registros usados para o calculo</h2>
    </div>
    <span class="badge badge-accent">{summary.source.slug}</span>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Bem</th>
          <th>Valor</th>
          <th>Atualizado</th>
          <th>Evidencia</th>
        </tr>
      </thead>
      <tbody>
        {#each summary.assets as asset}
          <tr>
            <td>{asset.external_id}</td>
            <td>
              <strong>{asset.description}</strong>
              <div class="soft">{asset.asset_type}</div>
            </td>
            <td>
              <strong>{asset.value_brl}</strong>
              <div class="soft">{formatPtBrMoney(asset.value)}</div>
            </td>
            <td>{formatPtBrDateTime(asset.source_updated_at)}</td>
            <td>
              <div class="soft">raw: {asset.provenance.raw_record_id}</div>
              <div class="soft">hash: {asset.provenance.raw_payload_hash}</div>
              <div class="soft">evidence: {asset.provenance.evidence_id}</div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Source metadata</p>
        <h2>Fonte oficial</h2>
      </div>
      <span class="badge">{summary.source.institution}</span>
    </div>

    <ul class="list">
      <li>
        <span>Source URL</span>
        <span>{summary.source.base_url}</span>
      </li>
      <li>
        <span>Documentation</span>
        <span>{summary.source.documentation_url}</span>
      </li>
      <li>
        <span>Portal</span>
        <span>{sourceMetadata.portal_url}</span>
      </li>
      <li>
        <span>License</span>
        <span>{summary.source.license}</span>
      </li>
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Calculation</p>
        <h2>Como a soma e feita</h2>
      </div>
      <span class="badge">{summary.candidate.external_id}</span>
    </div>

    <p class="quote">{summary.claim?.statement}</p>

    <ul class="list" style="margin-top: 1rem;">
      <li>
        <span>Assets</span>
        <span>{summary.assets.length}</span>
      </li>
      <li>
        <span>Claim evidence</span>
        <span>{summary.provenance.claim_evidence.length}</span>
      </li>
      <li>
        <span>Candidate raw record</span>
        <span>{summary.provenance.candidate_raw_record.id}</span>
      </li>
      <li>
        <span>Collected at</span>
        <span>{formatPtBrDateTime(summary.provenance.candidate_raw_record.collected_at)}</span>
      </li>
    </ul>
  </article>
</section>

<style>
  .soft {
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.45;
  }

  .table-wrap table {
    min-width: 920px;
  }
</style>
