import type { TseSummary } from '$lib/server/tse';

export function normalizeSearchText(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function matchesSummary(summary: TseSummary, query: string): boolean {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) {
    return false;
  }

  const tokens = [
    summary.candidate.external_id,
    summary.person.canonical_name,
    summary.person.normalized_name,
    summary.candidate.ballot_number ? String(summary.candidate.ballot_number) : '',
    summary.party?.acronym ?? '',
  ]
    .map(normalizeSearchText)
    .filter(Boolean);

  return tokens.some((token) => token === normalizedQuery || token.includes(normalizedQuery) || normalizedQuery.includes(token));
}
