BEGIN;

INSERT INTO sources (
    name,
    slug,
    institution,
    description,
    base_url,
    documentation_url,
    source_type,
    scope,
    official,
    update_frequency,
    license,
    enabled,
    metadata
) VALUES (
    'Instituto Brasileiro de Geografia e Estatística',
    'ibge',
    'Instituto Brasileiro de Geografia e Estatística',
    'API oficial de agregados do IBGE / SIDRA',
    'https://servicodados.ibge.gov.br/api/v3/agregados/1737',
    'https://servicodados.ibge.gov.br/api/docs/agregados?versao=3',
    'official_registry',
    'federal',
    true,
    'monthly',
    'open data',
    true,
    jsonb_build_object(
        'api_docs_url', 'https://servicodados.ibge.gov.br/api/docs/agregados?versao=3',
        'table_url', 'https://sidra.ibge.gov.br/tabela/1737',
        'aggregate_id', 1737,
        'variable_id', 63
    )
) ON CONFLICT (slug) DO UPDATE
SET
    name = EXCLUDED.name,
    institution = EXCLUDED.institution,
    description = EXCLUDED.description,
    base_url = EXCLUDED.base_url,
    documentation_url = EXCLUDED.documentation_url,
    source_type = EXCLUDED.source_type,
    scope = EXCLUDED.scope,
    official = EXCLUDED.official,
    update_frequency = EXCLUDED.update_frequency,
    license = EXCLUDED.license,
    enabled = EXCLUDED.enabled,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO datasets (
    source_id,
    name,
    slug,
    external_id,
    format,
    resource_url,
    scope,
    period_start,
    period_end,
    update_frequency,
    enabled,
    metadata
)
SELECT
    s.id,
    'IPCA - Variação mensal 2024',
    'ipca-variacao-mensal-2024',
    'ibge-agregado-1737-variavel-63',
    'json',
    'https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/202401|202412/variaveis/63?localidades=N1[all]',
    'federal',
    DATE '2024-01-01',
    DATE '2024-12-01',
    'monthly',
    true,
    jsonb_build_object(
        'aggregate_id', 1737,
        'variable_id', 63,
        'aggregate_name', 'IPCA - Série histórica com número-índice, variação mensal e variações acumuladas em 3 meses, em 6 meses, no ano e em 12 meses (a partir de dezembro/1979)',
        'table_url', 'https://sidra.ibge.gov.br/tabela/1737'
    )
FROM sources AS s
WHERE s.slug = 'ibge'
ON CONFLICT (source_id, slug) DO UPDATE
SET
    name = EXCLUDED.name,
    external_id = EXCLUDED.external_id,
    format = EXCLUDED.format,
    resource_url = EXCLUDED.resource_url,
    scope = EXCLUDED.scope,
    period_start = EXCLUDED.period_start,
    period_end = EXCLUDED.period_end,
    update_frequency = EXCLUDED.update_frequency,
    enabled = EXCLUDED.enabled,
    metadata = EXCLUDED.metadata,
    updated_at = now();

COMMIT;
