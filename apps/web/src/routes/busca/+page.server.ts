import type { PageServerLoad } from './$types';
import { loadFeaturedCandidateSummary } from '$lib/server/tse';
import { matchesSummary, normalizeSearchText } from '$lib/search';

export const load: PageServerLoad = async ({ fetch, url }) => {
  const summary = await loadFeaturedCandidateSummary(fetch);
  const query = url.searchParams.get('q')?.trim() ?? '';
  const normalizedQuery = normalizeSearchText(query);

  return {
    query,
    normalizedQuery,
    summary,
    result: normalizedQuery && matchesSummary(summary, normalizedQuery) ? summary : null,
  };
};
