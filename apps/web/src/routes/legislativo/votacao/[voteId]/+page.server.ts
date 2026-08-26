import type { PageServerLoad } from './$types';
import { loadCamaraVoteSummary } from '$lib/server/legislative';

export const load: PageServerLoad = async ({ fetch, params }) => {
  const summary = await loadCamaraVoteSummary(fetch, params.voteId);

  return {
    ...summary,
  };
};
