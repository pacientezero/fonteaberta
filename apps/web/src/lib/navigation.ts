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
