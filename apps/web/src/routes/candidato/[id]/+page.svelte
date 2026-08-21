<script lang="ts">
  import type { PageData } from './$types';
  import { candidateAssetsRoute, homeRoute, searchRoute, sourcesRoute } from '$lib/navigation';
  import { formatPtBrDateTime, formatPtBrMoney, formatPtBrNumber } from '$lib/format';

  export let data: PageData;

  const summary = data.summary;
  const sourceMetadata = summary.source.metadata as Record<string, string | undefined>;
  const urnaName = String(summary.candidate.raw_payload.NM_URNA_CANDIDATO ?? 'Nao informado');
</script>

<svelte:head>
  <title>{summary.person.canonical_name} | FonteAberta</title>
  <meta
    name="description"
    content="Detalhe publico do candidato com answer, fonte, dataset, registros usados e evidencia."
  />
</svelte:head>

<section class="hero">
  <div class="card card-strong card-pad stack">
    <div>
      <p class="eyebrow">Candidato</p>
      <h1>{summary.person.canonical_name}</h1>
      <p class="lead">
        {summary.candidate.position} · {summary.party?.acronym} #{summary.candidate.ballot_number}
        · eleicao {summary.election.year}
      </p>
    </div>

    {#if summary.claim}
      <p class="quote">{summary.claim.statement}</p>
    {/if}

    <div class="toolbar">
      <a class="button" href={candidateAssetsRoute(summary.candidate.external_id)}>Ver bens</a>
      <a class="button-secondary" href={sourcesRoute()}>Ver fontes</a>
      <a class="button-secondary" href={searchRoute(summary.person.canonical_name)}>Buscar este nome</a>
      <a class="button-secondary" href={homeRoute()}>Inicio</a>
    </div>
  </div>

  <aside class="card card-pad stack">
    <div>
      <p class="eyebrow">Resposta</p>
      <h2>{summary.declared_assets_total.formatted}</h2>
      <p class="note">
        Somatorio de {formatPtBrNumber(summary.assets.length)} bens declarados.
      </p>
    </div>

    <dl class="stack stats">
      <div class="metric">
        <dt class="metric-label">SQ_CANDIDATO</dt>
        <dd class="metric-value">{summary.candidate.external_id}</dd>
        <p class="metric-note">Identificador oficial do candidato na base do TSE.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Coleta</dt>
        <dd class="metric-value">{formatPtBrDateTime(summary.provenance.candidate_raw_record.collected_at)}</dd>
        <p class="metric-note">Janela em que o raw record foi coletado.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Calculation</dt>
        <dd class="metric-value">{summary.fact?.calculation_method}</dd>
        <p class="metric-note">Mesma formula aplicada ao total e a claim publica.</p>
      </div>

      <div class="metric">
        <dt class="metric-label">Evidencias</dt>
        <dd class="metric-value">{summary.provenance.claim_evidence.length}</dd>
        <p class="metric-note">
          {summary.provenance.claim_evidence.length} evidencias oficiais na claim publica.
        </p>
      </div>
    </dl>
  </aside>
</section>

<section class="grid grid-2">
  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Provenience</p>
        <h2>Fonte, dataset e raw record</h2>
      </div>
      <span class="badge badge-accent">{summary.source.slug}</span>
    </div>

    <ul class="list">
      <li>
        <span>
          <strong>Source</strong>
          <span class="soft">{summary.source.name}</span>
        </span>
        <span>{summary.source.official ? 'official' : 'internal'}</span>
      </li>
      <li>
        <span>
          <strong>Dataset</strong>
          <span class="soft">{summary.datasets.map((dataset) => dataset.name).join(' + ')}</span>
        </span>
        <span>{summary.datasets.length}</span>
      </li>
      <li>
        <span>
          <strong>Raw record</strong>
          <span class="soft">{summary.provenance.candidate_raw_record.id}</span>
        </span>
        <span>{summary.provenance.candidate_raw_record.processing_status}</span>
      </li>
      <li>
        <span>
          <strong>Payload hash</strong>
          <span class="soft">{summary.provenance.candidate_raw_record.payload_hash}</span>
        </span>
        <span>{summary.provenance.candidate_raw_record.dataset_id}</span>
      </li>
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Official facts</p>
        <h2>Camada factual do candidato</h2>
      </div>
      <span class="badge">{summary.fact?.unit}</span>
    </div>

    <ul class="list">
      <li>
        <span>Patrimonio total calculado</span>
        <span>{summary.declared_assets_total.formatted}</span>
      </li>
      <li>
        <span>Valor numerico do fact</span>
        <span>{formatPtBrMoney(summary.fact?.value_numeric)}</span>
      </li>
      <li>
        <span>Numero de bens</span>
        <span>{formatPtBrNumber(summary.assets.length)}</span>
      </li>
      <li>
        <span>Metodo</span>
        <span>{summary.claim?.calculation_method}</span>
      </li>
    </ul>
  </article>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Identity</p>
      <h2>Perfil oficial do candidato</h2>
    </div>
    <span class="badge">{summary.party?.acronym}</span>
  </div>

  <div class="grid grid-3 identity-grid">
    <div class="metric">
      <p class="metric-label">Nome oficial</p>
      <p class="metric-value">{summary.person.canonical_name}</p>
      <p class="metric-note">Nome consolidado no pipeline de normalizacao.</p>
    </div>
    <div class="metric">
      <p class="metric-label">Nome de urna</p>
      <p class="metric-value">{urnaName}</p>
      <p class="metric-note">Nome exibido na candidatura oficial.</p>
    </div>
    <div class="metric">
      <p class="metric-label">Partido</p>
      <p class="metric-value">{summary.party?.acronym}</p>
      <p class="metric-note">{summary.party?.name}</p>
    </div>
  </div>
</section>

<section class="card section">
  <div class="section-title">
    <div>
      <p class="panel-title">Assets preview</p>
      <h2>Bens declarados</h2>
    </div>
    <a class="button-secondary" href={candidateAssetsRoute(summary.candidate.external_id)}>
      Abrir pagina completa
    </a>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Bem</th>
          <th>Valor</th>
          <th>Evidencia</th>
          <th>Raw record</th>
        </tr>
      </thead>
      <tbody>
        {#each summary.assets as asset, index}
          <tr>
            <td>
              <strong>{index + 1}. {asset.description}</strong>
              <div class="soft">{asset.asset_type}</div>
            </td>
            <td>{asset.value_brl}</td>
            <td>
              <div class="soft">{asset.provenance.evidence_id}</div>
              <div class="soft">{asset.provenance.evidence_section}</div>
            </td>
            <td>
              <div class="soft">{asset.provenance.raw_record_id}</div>
              <div class="soft">{asset.provenance.raw_payload_hash}</div>
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
        <p class="panel-title">Evidence chain</p>
        <h2>Records usados na claim</h2>
      </div>
      <span class="badge">{summary.provenance.claim_evidence.length}</span>
    </div>

    <ul class="list">
      <li>
        <span>Candidate evidence</span>
        <span>{summary.provenance.candidate_evidence.id}</span>
      </li>
      {#each summary.provenance.asset_evidence as assetEvidence, index}
        <li>
          <span>Asset evidence {index + 1}</span>
          <span>{assetEvidence.id}</span>
        </li>
      {/each}
    </ul>
  </article>

  <article class="card section">
    <div class="section-title">
      <div>
        <p class="panel-title">Dataset URLs</p>
        <h2>Origens oficiais do slice</h2>
      </div>
      <span class="badge badge-accent">{summary.source.institution}</span>
    </div>

    <ul class="list">
      <li>
        <span>Candidate dataset</span>
        <span>{sourceMetadata.candidate_dataset_url}</span>
      </li>
      <li>
        <span>Asset dataset</span>
        <span>{sourceMetadata.candidate_assets_dataset_url}</span>
      </li>
      <li>
        <span>Portal URL</span>
        <span>{sourceMetadata.portal_url}</span>
      </li>
      <li>
        <span>Source updated at</span>
        <span>{formatPtBrDateTime(summary.candidate.source_updated_at)}</span>
      </li>
    </ul>
  </article>
</section>

<style>
  .stats {
    gap: 0.75rem;
  }

  .identity-grid {
    gap: 0.75rem;
  }

  .identity-grid .metric {
    background: rgba(255, 255, 255, 0.74);
  }

  .soft {
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.5;
  }
</style>
