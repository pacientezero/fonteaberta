import { getApiBaseUrl } from '$lib/server/api';

export type JsonRecord = Record<string, unknown>;

export interface DocumentCitation {
  document_id: string;
  document_title: string;
  document_type: string;
  source_name: string;
  source_slug: string;
  source_url: string;
  page: number | null;
  section: string | null;
  chunk_index: number;
  quote: string;
}

export interface DocumentEvidence {
  chunk_id: string;
  distance: number;
  lexical_overlap: number;
  quote: string;
}

export interface DocumentQueryResult {
  question: string;
  answer: string | null;
  citations: DocumentCitation[];
  evidence: DocumentEvidence[];
  resolved_scope: {
    source_slug: string;
    document_external_id: string;
    document_type: string;
    keywords: string[];
  };
  retrieval_mode: string;
  status: string;
}

const API_BASE_URL = getApiBaseUrl();

async function fetchJson<T>(fetchFn: typeof fetch, path: string, init?: RequestInit): Promise<T> {
  const response = await fetchFn(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(response.status === 404 ? 'Documentos oficiais não encontrados' : 'Falha ao carregar documentos oficiais');
  }
  return (await response.json()) as T;
}

export async function queryOfficialDocuments(
  fetchFn: typeof fetch,
  question: string,
  limit = 3,
): Promise<DocumentQueryResult> {
  return fetchJson<DocumentQueryResult>(fetchFn, '/v1/query', {
    method: 'POST',
    body: JSON.stringify({ question, limit }),
  });
}
