import type { PageServerLoad } from './$types';
import { queryOfficialDocuments } from '$lib/server/documents';

const DEFAULT_QUESTION = 'Para que o CANDex é utilizado?';

export const load: PageServerLoad = async ({ fetch, url }) => {
  const query = url.searchParams.get('q')?.trim() || DEFAULT_QUESTION;

  try {
    const result = await queryOfficialDocuments(fetch, query, 3);
    return {
      query,
      result,
      errorMessage: null,
    };
  } catch (cause) {
    const errorMessage = cause instanceof Error ? cause.message : 'Falha ao consultar documentos oficiais';
    return {
      query,
      result: null,
      errorMessage,
    };
  }
};
