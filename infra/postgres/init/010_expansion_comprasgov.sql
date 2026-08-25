BEGIN;

CREATE TABLE IF NOT EXISTS comprasgov_supplier_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    cnpj text,
    cpf text,
    identity_confidence text NOT NULL DEFAULT 'weak',
    licensed_to_bid boolean NOT NULL DEFAULT false,
    cnae_code integer,
    cnae_name text,
    municipality text,
    nature_id integer,
    nature_name text,
    company_size_id integer,
    company_size_name text,
    supplier_name text NOT NULL,
    uf text,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT comprasgov_supplier_records_source_external_unique UNIQUE (source_id, external_id),
    CONSTRAINT comprasgov_supplier_records_identity_confidence_check
        CHECK (identity_confidence IN ('strong', 'weak'))
);

CREATE INDEX IF NOT EXISTS idx_comprasgov_supplier_records_source_id ON comprasgov_supplier_records(source_id);
CREATE INDEX IF NOT EXISTS idx_comprasgov_supplier_records_dataset_id ON comprasgov_supplier_records(dataset_id);
CREATE INDEX IF NOT EXISTS idx_comprasgov_supplier_records_cnpj ON comprasgov_supplier_records(cnpj);
CREATE INDEX IF NOT EXISTS idx_comprasgov_supplier_records_supplier_name ON comprasgov_supplier_records(supplier_name);
CREATE INDEX IF NOT EXISTS idx_comprasgov_supplier_records_municipality ON comprasgov_supplier_records(municipality);

DROP TRIGGER IF EXISTS trg_comprasgov_supplier_records_touch_updated_at ON comprasgov_supplier_records;
CREATE TRIGGER trg_comprasgov_supplier_records_touch_updated_at
BEFORE UPDATE ON comprasgov_supplier_records
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

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
    'Compras.gov.br',
    'comprasgov',
    'Ministerio da Gestao e da Inovacao em Servicos Publicos',
    'Portal oficial de dados abertos do Compras.gov.br',
    'https://dadosabertos.compras.gov.br/',
    'https://www.gov.br/compras/pt-br/cidadao/portal-de-dados-abertos',
    'official_registry',
    'federal',
    true,
    'daily',
    'open data',
    true,
    jsonb_build_object(
        'portal_url', 'https://www.gov.br/compras/',
        'api_docs_url', 'https://www.gov.br/compras/pt-br/cidadao/portal-de-dados-abertos',
        'api_base_url', 'https://dadosabertos.compras.gov.br/',
        'module', 'fornecedor',
        'endpoint', '/modulo-fornecedor/1_consultarFornecedor',
        'default_page', 1,
        'default_page_size', 10,
        'default_active', true
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
    'Fornecedores ativos - pagina 1',
    'fornecedores-ativos-page-1',
    'comprasgov-fornecedores-page-1',
    'json',
    'https://dadosabertos.compras.gov.br/modulo-fornecedor/1_consultarFornecedor?pagina=1&tamanhoPagina=10&ativo=true',
    'federal',
    DATE '2026-08-24',
    DATE '2026-08-24',
    'daily',
    true,
    jsonb_build_object(
        'module', 'fornecedor',
        'page', 1,
        'page_size', 10,
        'active', true,
        'total_registros', 826570,
        'total_pages', 82657,
        'remaining_pages', 82656,
        'source_items', 10,
        'source_url', 'https://dadosabertos.compras.gov.br/modulo-fornecedor/1_consultarFornecedor?pagina=1&tamanhoPagina=10&ativo=true',
        'snapshot_date', '2026-08-24',
        'slice', 'fornecedores_ativos_p01_t10'
    )
FROM sources AS s
WHERE s.slug = 'comprasgov'
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

INSERT INTO directus_collections (
    collection,
    note,
    hidden,
    singleton,
    archive_app_filter,
    collapse,
    accountability,
    versioning,
    status,
    sort,
    icon,
    color
) VALUES
    ('comprasgov', 'Pasta para compras públicas, licitações e fornecedores', false, false, false, 'open', 'all', false, 'active', 31, 'cart-outline', '#ca8a04')
ON CONFLICT (collection) DO UPDATE
SET
    note = EXCLUDED.note,
    hidden = EXCLUDED.hidden,
    singleton = EXCLUDED.singleton,
    archive_app_filter = EXCLUDED.archive_app_filter,
    collapse = EXCLUDED.collapse,
    accountability = EXCLUDED.accountability,
    versioning = EXCLUDED.versioning,
    status = EXCLUDED.status,
    sort = EXCLUDED.sort,
    icon = EXCLUDED.icon,
    color = EXCLUDED.color;

INSERT INTO directus_collections (
    collection,
    note,
    hidden,
    singleton,
    archive_app_filter,
    collapse,
    accountability,
    versioning,
    status,
    sort,
    "group",
    icon,
    color
) VALUES
    ('comprasgov_supplier_records', 'Cadastro de fornecedores ativos do Compras.gov', false, false, true, 'open', 'all', false, 'active', 32, 'comprasgov', 'storefront-outline', '#f59e0b')
ON CONFLICT (collection) DO UPDATE
SET
    note = EXCLUDED.note,
    hidden = EXCLUDED.hidden,
    singleton = EXCLUDED.singleton,
    archive_app_filter = EXCLUDED.archive_app_filter,
    collapse = EXCLUDED.collapse,
    accountability = EXCLUDED.accountability,
    versioning = EXCLUDED.versioning,
    status = EXCLUDED.status,
    sort = EXCLUDED.sort,
    "group" = EXCLUDED."group",
    icon = EXCLUDED.icon,
    color = EXCLUDED.color;

WITH managed_tables(collection) AS (
    VALUES
        ('comprasgov_supplier_records')
)
INSERT INTO directus_fields (
    collection,
    field,
    readonly,
    hidden,
    searchable,
    required,
    sort
)
SELECT
    columns.table_name AS collection,
    columns.column_name AS field,
    columns.column_name IN ('id', 'created_at', 'updated_at') AS readonly,
    columns.column_name = 'id' AS hidden,
    columns.data_type NOT IN ('json', 'jsonb') AS searchable,
    columns.is_nullable = 'NO' AS required,
    columns.ordinal_position AS sort
FROM information_schema.columns AS columns
JOIN managed_tables ON managed_tables.collection = columns.table_name
WHERE columns.table_schema = 'public'
  AND NOT EXISTS (
      SELECT 1
      FROM directus_fields
      WHERE collection = columns.table_name
        AND field = columns.column_name
  )
ORDER BY columns.table_name, columns.ordinal_position;

DO $$
DECLARE
    public_policy_id uuid;
    researcher_role_id uuid;
    researcher_policy_id uuid;
BEGIN
    SELECT id INTO public_policy_id
    FROM directus_policies
    WHERE name IN ('Public', '$t:public_label')
       OR (admin_access = false AND app_access = false)
    LIMIT 1;

    IF public_policy_id IS NULL THEN
        RAISE EXCEPTION 'Directus public policy not found';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM directus_permissions
        WHERE policy = public_policy_id
          AND collection = 'comprasgov_supplier_records'
          AND action = 'read'
    ) THEN
        INSERT INTO directus_permissions (
            collection,
            action,
            permissions,
            validation,
            presets,
            fields,
            policy
        ) VALUES
            ('comprasgov_supplier_records', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id);
    END IF;

    INSERT INTO directus_roles (id, name, icon, description)
    SELECT gen_random_uuid(), 'Researcher', 'search', 'Read-only access to provenance tables'
    WHERE NOT EXISTS (
        SELECT 1 FROM directus_roles WHERE name = 'Researcher'
    );

    SELECT id INTO researcher_role_id
    FROM directus_roles
    WHERE name = 'Researcher'
    LIMIT 1;

    INSERT INTO directus_policies (id, name, icon, description, admin_access, app_access)
    SELECT gen_random_uuid(), 'Researcher', 'search', 'Read-only access to provenance tables', false, true
    WHERE NOT EXISTS (
        SELECT 1 FROM directus_policies WHERE name = 'Researcher'
    );

    SELECT id INTO researcher_policy_id
    FROM directus_policies
    WHERE name = 'Researcher'
    LIMIT 1;

    IF NOT EXISTS (
        SELECT 1
        FROM directus_access
        WHERE role = researcher_role_id
          AND policy = researcher_policy_id
    ) THEN
        INSERT INTO directus_access (id, role, "user", policy, sort)
        VALUES (gen_random_uuid(), researcher_role_id, NULL, researcher_policy_id, 1);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM directus_permissions
        WHERE policy = researcher_policy_id
          AND collection = 'comprasgov_supplier_records'
          AND action = 'read'
    ) THEN
        INSERT INTO directus_permissions (
            collection,
            action,
            permissions,
            validation,
            presets,
            fields,
            policy
        ) VALUES
            ('comprasgov_supplier_records', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id);
    END IF;
END $$;

COMMIT;
