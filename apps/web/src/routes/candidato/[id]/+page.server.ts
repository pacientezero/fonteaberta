import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { loadCandidateSummary } from '$lib/server/tse';

export const load: PageServerLoad = async ({ fetch, params }) => {
  try {
    const summary = await loadCandidateSummary(fetch, params.id);

    return {
      summary,
    };
  } catch {
    throw error(404, 'Candidato nao encontrado');
  }
};
