import { error } from '@sveltejs/kit';
import { getApiBaseUrl } from '$lib/server/api';

export type JsonRecord = Record<string, unknown>;

export interface TseSource {
  id: string;
  name: string;
  slug: string;
  institution: string;
  description: string;
  base_url: string;
  documentation_url: string;
  source_type: string;
  scope: string;
  official: boolean;
  update_frequency: string;
  license: string;
  metadata: JsonRecord;
}

export interface TseDataset {
  id: string;
  source_id: string;
  name: string;
  slug: string;
  external_id: string;
  format: string;
  resource_url: string;
  scope: string;
  period_start: string | null;
  period_end: string | null;
  update_frequency: string;
  enabled: boolean;
  metadata: JsonRecord;
  created_at: string;
  updated_at: string;
}

export interface TsePerson {
  id: string;
  canonical_name: string;
  normalized_name: string;
  birth_date: string | null;
  birth_place: string | null;
  metadata: JsonRecord;
}

export interface TseParty {
  id: string;
  external_id: string;
  name: string;
  acronym: string;
  number: number | null;
  official_url: string | null;
  logo_url: string | null;
  metadata: JsonRecord;
}

export interface TseElection {
  id: string;
  year: number;
  round: number;
  election_type: string;
  scope: string;
  country: string;
  state: string;
  city: string;
  election_date: string | null;
  status: string;
  metadata: JsonRecord;
}

export interface TseCandidate {
  id: string;
  external_id: string;
  ballot_number: number | null;
  position: string | null;
  application_status: string | null;
  result_status: string | null;
  occupation: string | null;
  education: string | null;
  declared_assets_total: string | null;
  declared_assets_total_brl: string | null;
  source_updated_at: string | null;
  collected_at: string | null;
  raw_payload: JsonRecord;
}

export interface TseAsset {
  id: string;
  external_id: string;
  asset_type: string;
  description: string;
  value: string;
  value_brl: string;
  currency: string;
  source_updated_at: string | null;
  raw_payload: JsonRecord;
  provenance: {
    raw_record_id: string;
    raw_payload_hash: string;
    evidence_id: string;
    evidence_source_url: string;
    evidence_section: string | null;
  };
}

export interface TseEvidence {
  id: string;
  external_id: string;
  source_url: string;
  section: string | null;
  payload_hash: string;
  raw_record_id?: string;
  raw_dataset_id?: string;
  raw_external_id?: string;
  raw_processing_status?: string;
}

export interface TseSummary {
  source: TseSource;
  datasets: TseDataset[];
  person: TsePerson;
  party: TseParty | null;
  election: TseElection;
  candidate: TseCandidate;
  assets: TseAsset[];
  declared_assets_total: {
    value: string;
    formatted: string;
    asset_count: number;
    calculation_method: string;
  };
  fact: {
    id: string;
    value_numeric: string;
    unit: string | null;
    calculation_method: string | null;
    metadata: JsonRecord;
  } | null;
  claim: {
    id: string;
    statement: string;
    calculation_method: string | null;
    metadata: JsonRecord;
  } | null;
  provenance: {
    candidate_raw_record: {
      id: string;
      external_id: string;
      payload_hash: string;
      source_updated_at: string | null;
      collected_at: string | null;
      processing_status: string;
      dataset_id: string;
    };
    candidate_evidence: TseEvidence;
    asset_evidence: TseEvidence[];
    claim_evidence: TseEvidence[];
  };
}

export interface TseCandidateCatalogResponse {
  status: string;
  count: number;
  candidates: TseSummary[];
}

const API_BASE_URL = getApiBaseUrl();
export const FEATURED_SQ_CANDIDATO = '280002540694';

async function fetchJson<T>(fetchFn: typeof fetch, path: string): Promise<T> {
  const response = await fetchFn(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw error(response.status, response.status === 404 ? 'Candidato não encontrado' : 'Falha ao carregar dados oficiais');
  }
  return (await response.json()) as T;
}

export function candidatePath(sqCandidato: string): string {
  return `/tse/candidatos/${sqCandidato}`;
}

export async function loadCandidateSummary(fetchFn: typeof fetch, sqCandidato: string): Promise<TseSummary> {
  return fetchJson<TseSummary>(fetchFn, candidatePath(sqCandidato));
}

export async function loadFeaturedCandidateSummary(fetchFn: typeof fetch): Promise<TseSummary> {
  return loadCandidateSummary(fetchFn, FEATURED_SQ_CANDIDATO);
}

export async function loadCandidateCatalog(
  fetchFn: typeof fetch,
  limit = 20,
): Promise<TseCandidateCatalogResponse> {
  return fetchJson<TseCandidateCatalogResponse>(fetchFn, `/tse/candidatos?limit=${limit}`);
}
