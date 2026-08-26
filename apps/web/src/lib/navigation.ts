export function homeRoute(): string {
  return '/';
}

export function searchRoute(query?: string): string {
  if (!query) {
    return '/busca';
  }

  const params = new URLSearchParams({ q: query });
  return `/busca?${params.toString()}`;
}

export function candidateRoute(sqCandidato: string): string {
  return `/candidato/${encodeURIComponent(sqCandidato)}`;
}

export function candidateAssetsRoute(sqCandidato: string): string {
  return `${candidateRoute(sqCandidato)}/bens`;
}

export function documentsRoute(query?: string): string {
  if (!query) {
    return '/documentos';
  }

  const params = new URLSearchParams({ q: query });
  return `/documentos?${params.toString()}`;
}

export function sourcesRoute(): string {
  return '/fontes';
}

export function dataRoute(): string {
  return '/dados';
}

export function methodologyRoute(): string {
  return '/metodologia';
}

export function legislativeRoute(): string {
  return '/legislativo';
}

export interface LegislativeVotesRouteParams {
  q?: string;
  kind?: 'all' | 'nominal' | 'symbolic';
}

export function legislativeVotesRoute(params?: LegislativeVotesRouteParams): string {
  if (!params) {
    return '/legislativo/votacoes';
  }

  const searchParams = new URLSearchParams();
  if (params.q) {
    searchParams.set('q', params.q);
  }
  if (params.kind && params.kind !== 'all') {
    searchParams.set('kind', params.kind);
  }

  const query = searchParams.toString();
  return query ? `/legislativo/votacoes?${query}` : '/legislativo/votacoes';
}

export function legislativeDeputyRoute(deputyId: string): string {
  return `/legislativo/deputado/${encodeURIComponent(deputyId)}`;
}

export function camaraVoteRoute(voteId: string): string {
  return `/legislativo/votacao/${encodeURIComponent(voteId)}`;
}
