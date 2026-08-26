import { error } from '@sveltejs/kit';
import { getApiBaseUrl } from '$lib/server/api';

export interface JsonRecord {
  [key: string]: unknown;
}

export interface LegislativeSource {
  id: string;
  slug: string;
  name: string;
  institution: string;
  base_url: string;
  documentation_url: string;
  license: string;
}

export interface LegislativeDataset {
  id: string;
  slug: string;
  name: string;
}

export interface LegislativeProposition {
  id: string;
  external_id: string;
  house: string;
  sigla_tipo: string;
  number: number;
  year: number;
  title: string;
  summary: string | null;
  presented_at: string | null;
  status: string | null;
  source_url: string | null;
  raw_record_id: string | null;
  evidence_id: string | null;
}

export interface LegislativeVoteMember {
  id: string;
  vote_id: string;
  person_id: string;
  party_id: string | null;
  external_id: string;
  vote_value: string;
  vote_label: string;
  source_url: string | null;
  raw_record_id: string | null;
  evidence_id: string | null;
  source_updated_at: string | null;
  collected_at: string | null;
  raw_payload: JsonRecord;
  metadata: JsonRecord;
  canonical_name: string;
  normalized_name: string;
  birth_date: string | null;
  birth_place: string | null;
  person_metadata: JsonRecord;
  party_external_id: string | null;
  party_name: string | null;
  party_acronym: string | null;
  party_number: number | null;
  party_metadata: JsonRecord | null;
}

export interface LegislativeVote {
  id: string;
  external_id: string;
  house: string;
  vote_date: string | null;
  vote_timestamp: string | null;
  description: string;
  result: string | null;
  vote_type: string | null;
  approved: boolean;
  total_votes: number;
  yes_votes: number;
  no_votes: number;
  other_votes: number;
  source_url: string | null;
  raw_record_id: string | null;
  evidence_id: string | null;
  source_updated_at: string | null;
  collected_at: string | null;
  raw_payload: JsonRecord;
  metadata: JsonRecord;
}

export interface LegislativeVoteClaim {
  id: string;
  statement: string;
  calculation_method: string | null;
  metadata: JsonRecord;
}

export interface LegislativeVoteFacts {
  approved: boolean | null;
  approved_evidence_id: string | null;
  yes_votes: number | null;
  no_votes: number | null;
  other_votes: number | null;
  total_votes: number | null;
}

export interface LegislativeVoteCatalogVote {
  id: string;
  external_id: string;
  house: string;
  vote_date: string | null;
  vote_timestamp: string | null;
  description: string;
  result: string | null;
  vote_type: string | null;
  approved: boolean;
  total_votes: number;
  yes_votes: number;
  no_votes: number;
  other_votes: number;
  source_url: string | null;
  raw_record_id: string | null;
  evidence_id: string | null;
}

export interface LegislativeVoteResponse {
  status: string;
  vote: {
    source: LegislativeSource;
    dataset: LegislativeDataset;
    proposition: LegislativeProposition;
    vote: LegislativeVote;
    members: LegislativeVoteMember[];
    claim: LegislativeVoteClaim | null;
    facts: LegislativeVoteFacts;
  } | null;
  citations: Array<{
    evidence_id: string | null;
    source_url: string | null;
    raw_record_id: string | null;
  }>;
}

export interface LegislativeVoteCatalogItem {
  source: LegislativeSource;
  dataset: LegislativeDataset;
  proposition: LegislativeProposition;
  vote: LegislativeVoteCatalogVote;
  member_count: number;
  citations: Array<{
    evidence_id: string | null;
    source_url: string | null;
    raw_record_id: string | null;
  }>;
}

export interface LegislativeVoteCatalogResponse {
  status: string;
  count: number;
  votes: LegislativeVoteCatalogItem[];
}

export interface LegislativeDeputyMandate {
  id: string | null;
  external_id: string | null;
  legislature_external_id: string | null;
  chamber: string | null;
  electoral_name: string | null;
  state: string | null;
  party_acronym: string | null;
  status: string | null;
  email: string | null;
  profile_url: string | null;
  photo_url: string | null;
  started_at: string | null;
  ended_at: string | null;
  source_updated_at: string | null;
  collected_at: string | null;
  raw_payload: JsonRecord;
  metadata: JsonRecord;
  person_id: string;
  canonical_name: string;
  normalized_name: string;
  birth_date: string | null;
  birth_place: string | null;
  person_metadata: JsonRecord;
  party_id: string | null;
  party_name: string | null;
  party_acronym_resolved: string | null;
  party_number: number | null;
  source_id: string;
  source_slug: string;
  source_name: string;
  dataset_id: string;
  dataset_slug: string;
  raw_record_id: string | null;
  raw_record_external_id: string | null;
  raw_record_payload_hash: string | null;
  evidence_id: string | null;
  evidence_external_id: string | null;
  evidence_source_url: string | null;
  fact_id: string | null;
  fact_predicate: string | null;
  fact_value_text: string | null;
  fact_effective_date: string | null;
  claim_id: string | null;
  claim_statement: string | null;
  claim_type: string | null;
  claim_calculation_method: string | null;
}

export interface LegislativeDeputyVoteHistoryItem {
  vote: LegislativeVoteCatalogVote;
  proposition: {
    id: string;
    external_id: string;
    sigla_tipo: string;
    number: number;
    year: number;
    title: string;
    summary: string | null;
    presented_at: string | null;
    status: string | null;
    source_url: string | null;
  };
  member_vote: {
    id: string;
    external_id: string;
    vote_value: string;
    vote_label: string;
    party_acronym: string | null;
    party_name: string | null;
    party_number: number | null;
    source_url: string | null;
    raw_record_id: string | null;
    evidence_id: string | null;
    source_updated_at: string | null;
    collected_at: string | null;
  };
}

export interface LegislativeDeputyResponse {
  status: string;
  mandate: LegislativeDeputyMandate | null;
  vote_history: LegislativeDeputyVoteHistoryItem[];
  vote_history_counts: {
    yes_votes: number;
    no_votes: number;
    other_votes: number;
    total_votes: number;
  } | null;
  citations: Array<{
    evidence_id: string | null;
    source_url: string | null;
    raw_record_id: string | null;
  }>;
}

const API_BASE_URL = getApiBaseUrl();
export const FEATURED_CAMARA_VOTE_ID = '2580259-24';

async function fetchJson<T>(fetchFn: typeof fetch, path: string): Promise<T> {
  const response = await fetchFn(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw error(response.status, response.status === 404 ? 'Votação não encontrada' : 'Falha ao carregar votação legislativa');
  }
  return (await response.json()) as T;
}

export function camaraVotePath(voteId: string): string {
  return `/v1/government/camara/votacoes/${voteId}`;
}

export async function loadCamaraVoteSummary(fetchFn: typeof fetch, voteId: string): Promise<LegislativeVoteResponse> {
  return fetchJson<LegislativeVoteResponse>(fetchFn, camaraVotePath(voteId));
}

export function camaraDeputyPath(deputyId: string): string {
  return `/v1/government/camara/deputados/${deputyId}`;
}

export async function loadCamaraDeputySummary(
  fetchFn: typeof fetch,
  deputyId: string,
): Promise<LegislativeDeputyResponse> {
  const response = await fetchFn(`${API_BASE_URL}${camaraDeputyPath(deputyId)}`);
  if (!response.ok) {
    throw error(response.status, response.status === 404 ? 'Deputado não encontrado' : 'Falha ao carregar histórico do deputado');
  }
  return (await response.json()) as LegislativeDeputyResponse;
}

export async function loadFeaturedCamaraVoteSummary(fetchFn: typeof fetch): Promise<LegislativeVoteResponse> {
  return loadCamaraVoteSummary(fetchFn, FEATURED_CAMARA_VOTE_ID);
}

export async function loadRecentCamaraVoteCatalog(
  fetchFn: typeof fetch,
  limit = 100,
): Promise<LegislativeVoteCatalogResponse> {
  return fetchJson<LegislativeVoteCatalogResponse>(
    fetchFn,
    `/v1/government/camara/votacoes?limit=${limit}`,
  );
}
