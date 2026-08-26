import type { PageServerLoad } from './$types';
import { normalizeSearchText } from '$lib/search';
import { loadRecentCamaraVoteCatalog } from '$lib/server/legislative';

type VoteKind = 'all' | 'nominal' | 'symbolic';

const KIND_LABELS: Record<VoteKind, string> = {
  all: 'Todas',
  nominal: 'Nominais',
  symbolic: 'Simbólicas',
};

function parseKind(value: string | null): VoteKind {
  if (value === 'nominal' || value === 'symbolic') {
    return value;
  }

  return 'all';
}

function buildSearchText(item: {
  proposition: {
    external_id: string;
    sigla_tipo: string;
    number: number;
    year: number;
    title: string;
    summary: string | null;
  };
  vote: {
    external_id: string;
    description: string;
    result: string | null;
    vote_type: string | null;
  };
  source: {
    name: string;
    institution: string;
  };
  dataset: {
    slug: string;
  };
}): string {
  return normalizeSearchText(
    [
      item.proposition.external_id,
      item.proposition.sigla_tipo,
      item.proposition.number,
      item.proposition.year,
      item.proposition.title,
      item.proposition.summary ?? '',
      item.vote.external_id,
      item.vote.description,
      item.vote.result ?? '',
      item.vote.vote_type ?? '',
      item.source.name,
      item.source.institution,
      item.dataset.slug,
    ]
      .map(String)
      .join(' '),
  );
}

export const load: PageServerLoad = async ({ fetch, url }) => {
  const catalog = await loadRecentCamaraVoteCatalog(fetch, 100);
  const query = url.searchParams.get('q')?.trim() ?? '';
  const kind = parseKind(url.searchParams.get('kind'));
  const normalizedQuery = normalizeSearchText(query);

  const votes = catalog.votes.filter((item) => {
    const matchesKind =
      kind === 'all' ? true : kind === 'nominal' ? item.member_count > 0 : item.member_count === 0;
    if (!matchesKind) {
      return false;
    }

    if (!normalizedQuery) {
      return true;
    }

    const searchableText = buildSearchText(item);
    return searchableText.includes(normalizedQuery) || normalizedQuery.includes(searchableText);
  });

  const nominalCount = catalog.votes.filter((item) => item.member_count > 0).length;
  const symbolicCount = catalog.votes.length - nominalCount;

  return {
    query,
    normalizedQuery,
    kind,
    kindLabel: KIND_LABELS[kind],
    loadedCount: catalog.count,
    nominalCount,
    symbolicCount,
    votes,
  };
};
