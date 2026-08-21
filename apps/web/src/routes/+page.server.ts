import type { PageServerLoad } from './$types';
import { loadFeaturedCandidateSummary } from '$lib/server/tse';

export const load: PageServerLoad = async ({ fetch }) => {
  const summary = await loadFeaturedCandidateSummary(fetch);

  return {
    summary,
  };
};
