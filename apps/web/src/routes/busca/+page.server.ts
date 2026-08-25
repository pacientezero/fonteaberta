import type { PageServerLoad } from './$types';
import { loadCandidateCatalog, loadFeaturedCandidateSummary } from '$lib/server/tse';
import { matchesSummary, normalizeSearchText } from '$lib/search';

export const load: PageServerLoad = async ({ fetch, url }) => {
  const [summary, catalog] = await Promise.all([
    loadFeaturedCandidateSummary(fetch),
    loadCandidateCatalog(fetch, 20),
  ]);
  const query = url.searchParams.get('q')?.trim() ?? '';
  const normalizedQuery = normalizeSearchText(query);
  const candidates = normalizedQuery
    ? catalog.candidates.filter((candidate) => matchesSummary(candidate, normalizedQuery))
    : catalog.candidates;

  return {
    query,
    normalizedQuery,
    summary,
    catalogCount: catalog.count,
    candidates,
    result: candidates[0] ?? null,
  };
};
