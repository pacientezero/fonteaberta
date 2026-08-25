import type { PageServerLoad } from './$types';
import { loadCoverageDashboard } from '$lib/server/coverage';
import { loadFeaturedCandidateSummary } from '$lib/server/tse';

export const load: PageServerLoad = async ({ fetch }) => {
  const [summary, coverage] = await Promise.all([
    loadFeaturedCandidateSummary(fetch),
    loadCoverageDashboard(fetch),
  ]);

  return {
    summary,
    coverage,
  };
};
