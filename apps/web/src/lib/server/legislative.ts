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

export async function loadFeaturedCamaraVoteSummary(fetchFn: typeof fetch): Promise<LegislativeVoteResponse> {
  return loadCamaraVoteSummary(fetchFn, FEATURED_CAMARA_VOTE_ID);
}

export async function loadRecentCamaraVoteCatalog(
  fetchFn: typeof fetch,
  limit = 15,
): Promise<LegislativeVoteCatalogResponse> {
  return fetchJson<LegislativeVoteCatalogResponse>(
    fetchFn,
    `/v1/government/camara/votacoes?limit=${limit}`,
  );
}
