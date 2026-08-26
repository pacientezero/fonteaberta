import type { PageServerLoad } from './$types';
import {
  loadFeaturedCamaraVoteSummary,
  loadRecentCamaraVoteCatalog,
} from '$lib/server/legislative';

export const load: PageServerLoad = async ({ fetch }) => {
  const [featured, recent] = await Promise.all([
    loadFeaturedCamaraVoteSummary(fetch),
    loadRecentCamaraVoteCatalog(fetch, 100),
  ]);

  return {
    ...featured,
    recentVotes: recent.votes,
  };
};
