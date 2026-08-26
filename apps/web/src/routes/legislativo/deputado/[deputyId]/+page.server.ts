import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { loadCamaraDeputySummary } from '$lib/server/legislative';

export const load: PageServerLoad = async ({ fetch, params }) => {
  const summary = await loadCamaraDeputySummary(fetch, params.deputyId);

  if (summary.status !== 'ok' || !summary.mandate) {
    throw error(404, 'Deputado não encontrado');
  }

  return {
    deputyId: params.deputyId,
    ...summary,
  };
};
