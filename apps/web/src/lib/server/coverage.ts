import { getApiBaseUrl } from '$lib/server/api';
import { formatPtBrDate, formatPtBrDateTime, formatPtBrMoney, formatPtBrNumber } from '$lib/format';
import { candidateAssetsRoute, candidateRoute, documentsRoute, legislativeRoute } from '$lib/navigation';
import { loadFeaturedCamaraVoteSummary, loadRecentCamaraVoteCatalog } from '$lib/server/legislative';
import { loadCandidateCatalog, loadFeaturedCandidateSummary } from '$lib/server/tse';
import { queryOfficialDocuments } from '$lib/server/documents';

const API_BASE_URL = getApiBaseUrl();
const DEFAULT_DOCUMENT_QUESTION = 'Para que o CANDex é utilizado?';
const CAMARA_DEPUTY_ID = '73433';
const SENADO_MANDATE_IDENTIFIER = '596-exercicio-3028';
const TESOURO_ROUTE = '/v1/government/tesouro/rreo/2024/6/3550308';
const COMPRASGOV_ROUTE = '/v1/government/comprasgov/fornecedores';
const CAMARA_ROUTE = `/v1/government/camara/deputados/${CAMARA_DEPUTY_ID}`;
const SENADO_ROUTE = `/v1/government/senado/senadores/${SENADO_MANDATE_IDENTIFIER}`;
const TRANSPARENCIA_ROUTE = '/v1/government/transparencia/despesas';
const BCB_ROUTE = '/v1/economic/bcb/selic';
const IBGE_ROUTE = '/v1/economic/ibge/ipca';

type CardVariant = 'web' | 'api';
type CardStatus = 'ok' | 'error';

export interface CoverageMetric {
  label: string;
  value: string;
}

export interface CoverageCard {
  key: string;
  variant: CardVariant;
  eyebrow: string;
  title: string;
  headline: string;
  description: string;
  metrics: CoverageMetric[];
  primaryLabel: string;
  primaryHref: string;
  primaryExternal: boolean;
  secondaryLabel?: string;
  secondaryHref?: string;
  secondaryExternal?: boolean;
  accent: string;
  status: CardStatus;
  statusLabel: string;
}

export interface CoverageSummary {
  label: string;
  value: string;
  note: string;
}

export interface CoverageDashboard {
  summary: CoverageSummary[];
  cards: CoverageCard[];
}

interface SafeResult<T> {
  data: T | null;
  error: string | null;
}

async function fetchJson<T>(fetchFn: typeof fetch, path: string): Promise<T> {
  const response = await fetchFn(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Falha ao carregar ${path}`);
  }
  return (await response.json()) as T;
}

async function safeLoad<T>(loader: Promise<T>): Promise<SafeResult<T>> {
  try {
    return {
      data: await loader,
      error: null,
    };
  } catch (cause) {
    return {
      data: null,
      error: cause instanceof Error ? cause.message : 'Falha ao carregar cobertura',
    };
  }
}

function apiHref(path: string): string {
  return `${API_BASE_URL}${path}`;
}

function externalHref(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return value;
}

function buildErrorCard(
  key: string,
  eyebrow: string,
  title: string,
  accent: string,
  primaryHref: string,
  primaryLabel: string,
  error: string,
  secondaryHref?: string,
  secondaryLabel?: string,
): CoverageCard {
  return {
    key,
    variant: 'api',
    eyebrow,
    title,
    headline: 'Indisponível',
    description: error,
    metrics: [],
    primaryLabel,
    primaryHref,
    primaryExternal: primaryHref.startsWith('http'),
    secondaryLabel,
    secondaryHref,
    secondaryExternal: Boolean(secondaryHref?.startsWith('http')),
    accent,
    status: 'error',
    statusLabel: 'Falha',
  };
}

function formatMaybeMoney(value: unknown): string {
  if (typeof value === 'number') {
    return formatPtBrMoney(String(value));
  }
  if (typeof value === 'string') {
    return formatPtBrMoney(value);
  }
  return 'Não informado';
}

function formatLegislatureLabel(value: string | null | undefined): string {
  if (!value) {
    return 'Não informado';
  }
  const match = value.match(/(\d+)/);
  if (!match) {
    return value;
  }
  return `${match[1]}ª legislatura`;
}

export async function loadCoverageDashboard(fetchFn: typeof fetch): Promise<CoverageDashboard> {
  const [
    candidateResult,
    candidateCatalogResult,
    documentResult,
    bcbResult,
    ibgeResult,
    camaraResult,
    legislativeResult,
    recentLegislativeResult,
    senadoResult,
    transparenciaResult,
    tesouroResult,
    comprasgovResult,
  ] = await Promise.all([
    safeLoad(loadFeaturedCandidateSummary(fetchFn)),
    safeLoad(loadCandidateCatalog(fetchFn, 20)),
    safeLoad(queryOfficialDocuments(fetchFn, DEFAULT_DOCUMENT_QUESTION, 3)),
    safeLoad(fetchJson<Record<string, any>>(fetchFn, BCB_ROUTE)),
    safeLoad(fetchJson<Record<string, any>>(fetchFn, IBGE_ROUTE)),
    safeLoad(fetchJson<Record<string, any>>(fetchFn, CAMARA_ROUTE)),
    safeLoad(loadFeaturedCamaraVoteSummary(fetchFn)),
    safeLoad(loadRecentCamaraVoteCatalog(fetchFn, 15)),
    safeLoad(fetchJson<Record<string, any>>(fetchFn, SENADO_ROUTE)),
    safeLoad(fetchJson<Record<string, any>>(fetchFn, TRANSPARENCIA_ROUTE)),
    safeLoad(fetchJson<Record<string, any>>(fetchFn, TESOURO_ROUTE)),
    safeLoad(fetchJson<Record<string, any>>(fetchFn, COMPRASGOV_ROUTE)),
  ]);

  const cards: CoverageCard[] = [];

  if (candidateResult.data) {
    const summary = candidateResult.data;
    const candidateCount = candidateCatalogResult.data?.count ?? 0;
    cards.push({
      key: 'tse-v1',
      variant: 'web',
      eyebrow: 'V1 presidencial',
      title: 'Tribunal Superior Eleitoral',
      headline: summary.person.canonical_name,
      description: `${summary.declared_assets_total.formatted} somados a partir de ${formatPtBrNumber(summary.assets.length)} bens oficiais e ${formatPtBrNumber(candidateCount)} candidato(s) indexado(s).`,
      metrics: [
        { label: 'Fonte', value: summary.source.name },
        { label: 'Datasets', value: summary.datasets.map((dataset) => dataset.slug).join(' + ') },
        { label: 'Candidatos', value: formatPtBrNumber(candidateCount) },
        { label: 'Coleta', value: formatPtBrDateTime(summary.provenance.candidate_raw_record.collected_at) },
      ],
      primaryLabel: 'Abrir candidato',
      primaryHref: candidateRoute(summary.candidate.external_id),
      primaryExternal: false,
      secondaryLabel: 'Ver bens',
      secondaryHref: candidateAssetsRoute(summary.candidate.external_id),
      secondaryExternal: false,
      accent: '#2563eb',
      status: 'ok',
      statusLabel: 'V1 ativa',
    });
  } else {
    cards.push(
      buildErrorCard(
        'tse-v1',
        'V1 presidencial',
        'Tribunal Superior Eleitoral',
        '#2563eb',
        candidateRoute('280002540694'),
        'Abrir candidato',
        candidateResult.error || 'Falha ao carregar o candidato em destaque.',
        candidateAssetsRoute('280002540694'),
        'Ver bens',
      ),
    );
  }

  if (documentResult.data) {
    const result = documentResult.data;
    cards.push({
      key: 'documents-rag',
      variant: 'web',
      eyebrow: 'Documentos e RAG',
      title: 'Recuperação oficial',
      headline: result.answer ?? result.question,
      description: `${result.citations.length} citações e ${result.evidence.length} evidências no escopo ${result.resolved_scope.document_external_id}.`,
      metrics: [
        { label: 'Fonte', value: result.resolved_scope.source_slug },
        { label: 'Modo', value: result.retrieval_mode },
        { label: 'Status', value: result.status },
      ],
      primaryLabel: 'Abrir RAG',
      primaryHref: documentsRoute(DEFAULT_DOCUMENT_QUESTION),
      primaryExternal: false,
      secondaryLabel: 'Ver fonte oficial',
      secondaryHref: result.citations[0]?.source_url,
      secondaryExternal: Boolean(result.citations[0]?.source_url?.startsWith('http')),
      accent: '#0ea5e9',
      status: 'ok',
      statusLabel: 'RAG ativo',
    });
  } else {
    cards.push(
      buildErrorCard(
        'documents-rag',
        'Documentos e RAG',
        'Recuperação oficial',
        '#0ea5e9',
        documentsRoute(DEFAULT_DOCUMENT_QUESTION),
        'Abrir RAG',
        documentResult.error || 'Falha ao carregar a busca documental.',
      ),
    );
  }

  if (bcbResult.data) {
    const summary = bcbResult.data;
    const observation = summary.observations[summary.observations.length - 1];
    cards.push({
      key: 'bcb-selic',
      variant: 'api',
      eyebrow: 'Economia',
      title: 'BCB / Selic',
      headline: summary.latest_value_formatted,
      description: summary.claim?.statement ?? 'Taxa Selic oficial com série diária rastreável.',
      metrics: [
        { label: 'Observações', value: formatPtBrNumber(summary.observations.length) },
        { label: 'Última coleta', value: formatPtBrDateTime(summary.raw_record?.collected_at) },
        { label: 'Fechamento', value: formatPtBrDate(observation?.observation_date) },
      ],
      primaryLabel: 'Abrir JSON',
      primaryHref: apiHref(BCB_ROUTE),
      primaryExternal: true,
      secondaryLabel: 'Fonte oficial',
      secondaryHref: externalHref(summary.dataset?.resource_url ?? summary.source?.base_url),
      secondaryExternal: true,
      accent: '#0891b2',
      status: 'ok',
      statusLabel: 'Série viva',
    });
  } else {
    cards.push(
      buildErrorCard('bcb-selic', 'Economia', 'BCB / Selic', '#0891b2', apiHref(BCB_ROUTE), 'Abrir JSON', bcbResult.error || 'Falha ao carregar a Selic.'),
    );
  }

  if (ibgeResult.data) {
    const summary = ibgeResult.data;
    const observation = summary.observations[summary.observations.length - 1];
    cards.push({
      key: 'ibge-ipca',
      variant: 'api',
      eyebrow: 'Economia',
      title: 'IBGE / IPCA',
      headline: summary.latest_value_formatted,
      description: summary.claim?.statement ?? 'IPCA mensal com observações oficiais e rastreáveis.',
      metrics: [
        { label: 'Observações', value: formatPtBrNumber(summary.observations.length) },
        { label: 'Última coleta', value: formatPtBrDateTime(summary.raw_record?.collected_at) },
        { label: 'Período', value: formatPtBrDate(observation?.observation_date) },
      ],
      primaryLabel: 'Abrir JSON',
      primaryHref: apiHref(IBGE_ROUTE),
      primaryExternal: true,
      secondaryLabel: 'Fonte oficial',
      secondaryHref: externalHref(summary.dataset?.resource_url ?? summary.source?.base_url),
      secondaryExternal: true,
      accent: '#14b8a6',
      status: 'ok',
      statusLabel: 'Série viva',
    });
  } else {
    cards.push(
      buildErrorCard('ibge-ipca', 'Economia', 'IBGE / IPCA', '#14b8a6', apiHref(IBGE_ROUTE), 'Abrir JSON', ibgeResult.error || 'Falha ao carregar o IPCA.'),
    );
  }

  if (camaraResult.data) {
    const mandate = camaraResult.data.mandate;
    const legislature = formatLegislatureLabel(String(mandate.legislature_external_id ?? ''));
    cards.push({
      key: 'camara-deputados',
      variant: 'api',
      eyebrow: 'Legislativo',
      title: 'Câmara dos Deputados',
      headline: String(mandate.canonical_name ?? mandate.electoral_name ?? 'Mandato oficial'),
      description: `${mandate.party_acronym ?? 'Sem partido'} · ${mandate.state ?? 'BR'} · ${legislature}`,
      metrics: [
        { label: 'Status', value: String(mandate.status ?? 'Não informado') },
        { label: 'Perfil', value: String(mandate.profile_url ?? 'Não informado') },
        { label: 'Coleta', value: formatPtBrDateTime(mandate.collected_at) },
      ],
      primaryLabel: 'Abrir JSON',
      primaryHref: apiHref(CAMARA_ROUTE),
      primaryExternal: true,
      secondaryLabel: 'Perfil oficial',
      secondaryHref: externalHref(mandate.profile_url),
      secondaryExternal: Boolean(mandate.profile_url),
      accent: '#7c3aed',
      status: 'ok',
      statusLabel: 'Mandato vivo',
    });
  } else {
    cards.push(
      buildErrorCard('camara-deputados', 'Legislativo', 'Câmara dos Deputados', '#7c3aed', apiHref(CAMARA_ROUTE), 'Abrir JSON', camaraResult.error || 'Falha ao carregar a Câmara.'),
    );
  }

  if (legislativeResult.data) {
    const response = legislativeResult.data;
    const recentVotes = recentLegislativeResult.data?.votes ?? [];
    const nominalRecentVotes = recentVotes.filter((item) => item.member_count > 0);
    const symbolicRecentVotes = recentVotes.filter((item) => item.member_count === 0);
    const totals = recentVotes.reduce(
      (acc, item) => {
        acc.yes += item.vote.yes_votes;
        acc.no += item.vote.no_votes;
        acc.other += item.vote.other_votes;
        acc.memberCount += item.member_count;
        return acc;
      },
      { yes: 0, no: 0, other: 0, memberCount: 0 },
    );
    const vote = response.vote?.vote;
    const proposition = response.vote?.proposition;
    cards.push({
      key: 'camara-votacao',
      variant: 'web',
      eyebrow: 'Legislativo',
      title: 'Câmara / votações aprovadas',
      headline: recentVotes[0]
        ? `${recentVotes[0].proposition.sigla_tipo} ${recentVotes[0].proposition.number}/${recentVotes[0].proposition.year}`
        : proposition
          ? `${proposition.sigla_tipo} ${proposition.number}/${proposition.year}`
          : 'Votação oficial',
      description: recentVotes.length
        ? `${recentVotes.length} votações aprovadas já cobertas; ${nominalRecentVotes.length} são nominais com lista de membros e ${symbolicRecentVotes.length} não expõem voto individual no portal oficial.`
        : vote?.description ??
          'Votação nominal oficial com lista de parlamentares que votaram a favor ou contra.',
      metrics: [
        { label: 'Fonte', value: response.vote?.source?.name ?? 'Câmara dos Deputados' },
        { label: 'Cobertas', value: formatPtBrNumber(recentVotes.length || 1) },
        { label: 'Nominais', value: formatPtBrNumber(nominalRecentVotes.length) },
        { label: 'Sem lista', value: formatPtBrNumber(symbolicRecentVotes.length) },
      ],
      primaryLabel: 'Abrir votação',
      primaryHref: legislativeRoute(),
      primaryExternal: false,
      secondaryLabel: 'Ver lista',
      secondaryHref: legislativeRoute(),
      secondaryExternal: false,
      accent: '#7c3aed',
      status: 'ok',
      statusLabel: recentVotes.length > 1 ? 'Cobertura plural' : vote?.approved ? 'Aprovado' : 'Votação viva',
    });
  } else {
    cards.push(
      buildErrorCard(
        'camara-votacao',
        'Legislativo',
        'Câmara / votações aprovadas',
        '#7c3aed',
        legislativeRoute(),
        'Abrir votação',
        legislativeResult.error || 'Falha ao carregar a votação nominal da Câmara.',
        legislativeRoute(),
        'Ver lista',
      ),
    );
  }

  if (senadoResult.data) {
    const mandate = senadoResult.data.mandate;
    const legislature = formatLegislatureLabel(String(mandate.legislature_external_id ?? ''));
    cards.push({
      key: 'senado-federal',
      variant: 'api',
      eyebrow: 'Legislativo',
      title: 'Senado Federal',
      headline: String(mandate.canonical_name ?? 'Mandato oficial'),
      description: `${mandate.party_acronym_resolved ?? mandate.party_acronym ?? 'Sem partido'} · ${mandate.state ?? 'BR'} · ${legislature}`,
      metrics: [
        { label: 'Status', value: String(mandate.status ?? 'Não informado') },
        { label: 'Perfil', value: String(mandate.profile_url ?? 'Não informado') },
        { label: 'Coleta', value: formatPtBrDateTime(mandate.collected_at) },
      ],
      primaryLabel: 'Abrir JSON',
      primaryHref: apiHref(SENADO_ROUTE),
      primaryExternal: true,
      secondaryLabel: 'Perfil oficial',
      secondaryHref: externalHref(mandate.profile_url),
      secondaryExternal: Boolean(mandate.profile_url),
      accent: '#8b5cf6',
      status: 'ok',
      statusLabel: 'Mandato vivo',
    });
  } else {
    cards.push(
      buildErrorCard('senado-federal', 'Legislativo', 'Senado Federal', '#8b5cf6', apiHref(SENADO_ROUTE), 'Abrir JSON', senadoResult.error || 'Falha ao carregar o Senado.'),
    );
  }

  if (transparenciaResult.data) {
    const summary = transparenciaResult.data;
    cards.push({
      key: 'transparencia-despesas',
      variant: 'api',
      eyebrow: 'Transparência',
      title: 'Portal da Transparência',
      headline: summary.paid_amount_formatted,
      description: `Recorte de ${summary.expense_month} com ${formatPtBrNumber(summary.summary.row_count)} despesas validadas.`,
      metrics: [
        { label: 'Empenhado', value: formatMaybeMoney(summary.summary.totals.committed_amount) },
        { label: 'Liquidado', value: formatMaybeMoney(summary.summary.totals.liquidated_amount) },
        { label: 'Pago', value: summary.paid_amount_formatted },
      ],
      primaryLabel: 'Abrir JSON',
      primaryHref: apiHref(TRANSPARENCIA_ROUTE),
      primaryExternal: true,
      secondaryLabel: 'Fonte oficial',
      secondaryHref: externalHref(summary.dataset?.resource_url ?? summary.source?.base_url),
      secondaryExternal: true,
      accent: '#0f766e',
      status: 'ok',
      statusLabel: 'Resumo vivo',
    });
  } else {
    cards.push(
      buildErrorCard('transparencia-despesas', 'Transparência', 'Portal da Transparência', '#0f766e', apiHref(TRANSPARENCIA_ROUTE), 'Abrir JSON', transparenciaResult.error || 'Falha ao carregar despesas públicas.'),
    );
  }

  if (tesouroResult.data) {
    const summary = tesouroResult.data;
    cards.push({
      key: 'tesouro-rreo',
      variant: 'api',
      eyebrow: 'Tesouro',
      title: 'Tesouro / SICONFI',
      headline: summary.headline_value_formatted,
      description: `${summary.report.period_label} · ${formatPtBrNumber(summary.row_count)} linhas do RREO.`,
      metrics: [
        { label: 'Entidade', value: String(summary.report.entity_code) },
        { label: 'Exercício', value: String(summary.report.exercise) },
        { label: 'Anexo', value: summary.report.annex },
      ],
      primaryLabel: 'Abrir JSON',
      primaryHref: apiHref(TESOURO_ROUTE),
      primaryExternal: true,
      secondaryLabel: 'Fonte oficial',
      secondaryHref: externalHref(summary.dataset?.resource_url ?? summary.source?.base_url),
      secondaryExternal: true,
      accent: '#1e3a8a',
      status: 'ok',
      statusLabel: 'RREO vivo',
    });
  } else {
    cards.push(
      buildErrorCard('tesouro-rreo', 'Tesouro', 'Tesouro / SICONFI', '#1e3a8a', apiHref(TESOURO_ROUTE), 'Abrir JSON', tesouroResult.error || 'Falha ao carregar o RREO.'),
    );
  }

  if (comprasgovResult.data) {
    const summary = comprasgovResult.data;
    cards.push({
      key: 'comprasgov-fornecedores',
      variant: 'api',
      eyebrow: 'Compras.gov',
      title: 'Compras.gov / fornecedores',
      headline: summary.headline.supplier_name,
      description: `${summary.headline.municipality} · ${summary.headline.uf} · ${summary.headline.active ? 'ativo' : 'inativo'}`,
      metrics: [
        { label: 'Confiança', value: summary.headline.identity_confidence },
        { label: 'Página', value: summary.report.page_label },
        { label: 'Registros', value: formatPtBrNumber(summary.row_count) },
      ],
      primaryLabel: 'Abrir JSON',
      primaryHref: apiHref(COMPRASGOV_ROUTE),
      primaryExternal: true,
      secondaryLabel: 'Fonte oficial',
      secondaryHref: externalHref(summary.dataset?.resource_url ?? summary.source?.base_url),
      secondaryExternal: true,
      accent: '#ca8a04',
      status: 'ok',
      statusLabel: 'Cadastro vivo',
    });
  } else {
    cards.push(
      buildErrorCard('comprasgov-fornecedores', 'Compras.gov', 'Compras.gov / fornecedores', '#ca8a04', apiHref(COMPRASGOV_ROUTE), 'Abrir JSON', comprasgovResult.error || 'Falha ao carregar fornecedores ativos.'),
    );
  }

  const summary: CoverageSummary[] = [
    {
      label: 'Experiências públicas',
      value: formatPtBrNumber(cards.filter((card) => card.variant === 'web').length),
      note: 'V1 presidencial e RAG documental',
    },
    {
      label: 'Frentes de API',
      value: formatPtBrNumber(cards.filter((card) => card.variant === 'api').length),
      note: 'Expansões econômicas, legislativas e administrativas',
    },
    {
      label: 'Cartões de cobertura',
      value: formatPtBrNumber(cards.length),
      note: 'Leitura rápida do que já está vivo',
    },
  ];

  return {
    summary,
    cards,
  };
}
