import type { PageServerLoad } from './$types';
import { candidateRoute, searchRoute } from '$lib/navigation';
import { loadCandidateCatalog, loadFeaturedCandidateSummary } from '$lib/server/tse';
import { TSE_PRESIDENTIAL_ROSTER_2026 } from '$lib/server/coverage';

export const load: PageServerLoad = async ({ fetch, url }) => {
  const query = url.searchParams.get('q')?.trim() ?? '';
  const [summary, catalog] = await Promise.all([
    loadFeaturedCandidateSummary(fetch),
    loadCandidateCatalog(fetch, query ? 100 : 20, query),
  ]);
  const officialRoster = TSE_PRESIDENTIAL_ROSTER_2026.map((nomination) => {
    const importedCandidateExternalId = nomination.importedCandidateExternalId ?? null;
    const isImported = importedCandidateExternalId !== null;
    const openHref = isImported ? candidateRoute(importedCandidateExternalId) : nomination.sourceUrl;
    const openLabel = isImported ? 'Abrir candidato' : 'Ver ata oficial';
    return {
      ...nomination,
      importedCandidateExternalId,
      imported: isImported,
      openHref,
      openLabel,
      searchHref: searchRoute(nomination.displayName),
    };
  });

  return {
    query,
    summary,
    catalogCount: catalog.count,
    candidates: catalog.candidates,
    result: catalog.candidates[0] ?? null,
    officialRoster,
  };
};
