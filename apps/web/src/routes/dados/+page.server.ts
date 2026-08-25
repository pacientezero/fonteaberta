import type { PageServerLoad } from './$types';
import { loadCoverageDashboard } from '$lib/server/coverage';

export const load: PageServerLoad = async ({ fetch }) => {
  return loadCoverageDashboard(fetch);
};
