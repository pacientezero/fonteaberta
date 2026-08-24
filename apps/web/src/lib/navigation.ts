export function homeRoute(): string {
  return '/';
}

export function searchRoute(query?: string): string {
  if (!query) {
    return '/buscar';
  }

  const params = new URLSearchParams({ q: query });
  return `/buscar?${params.toString()}`;
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
