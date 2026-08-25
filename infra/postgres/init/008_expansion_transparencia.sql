BEGIN;

CREATE TABLE IF NOT EXISTS government_expenses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    expense_month date NOT NULL,
    superior_org_code text,
    superior_org_name text,
    subordinate_org_code text,
    subordinate_org_name text,
    managing_unit_code text,
    managing_unit_name text,
    management_code text,
    management_name text,
    budget_unit_code text,
    budget_unit_name text,
    function_code text,
    function_name text,
    subfunction_code text,
    subfunction_name text,
    budget_program_code text,
    budget_program_name text,
    action_code text,
    action_name text,
    planning_code text,
    planning_name text,
    government_program_code text,
    government_program_name text,
    uf text,
    municipality text,
    subtitle_code text,
    subtitle_name text,
    locator_code text,
    locator_name text,
    locator_sigla text,
    locator_description text,
    amendment_author_code text,
    amendment_author_name text,
    economic_category_code text,
    economic_category_name text,
    expense_group_code text,
    expense_group_name text,
    expense_element_code text,
    expense_element_name text,
    expense_modality_code text,
    expense_modality_name text,
    committed_amount numeric(18, 2) NOT NULL DEFAULT 0,
    liquidated_amount numeric(18, 2) NOT NULL DEFAULT 0,
    paid_amount numeric(18, 2) NOT NULL DEFAULT 0,
    restos_apagar_inscritos_amount numeric(18, 2) NOT NULL DEFAULT 0,
    restos_apagar_cancelados_amount numeric(18, 2) NOT NULL DEFAULT 0,
    restos_apagar_pagos_amount numeric(18, 2) NOT NULL DEFAULT 0,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT government_expenses_source_external_unique UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_government_expenses_source_id ON government_expenses(source_id);
CREATE INDEX IF NOT EXISTS idx_government_expenses_dataset_id ON government_expenses(dataset_id);
CREATE INDEX IF NOT EXISTS idx_government_expenses_expense_month ON government_expenses(expense_month);
CREATE INDEX IF NOT EXISTS idx_government_expenses_paid_amount ON government_expenses(paid_amount);
CREATE INDEX IF NOT EXISTS idx_government_expenses_superior_org_code ON government_expenses(superior_org_code);

DROP TRIGGER IF EXISTS trg_government_expenses_touch_updated_at ON government_expenses;
CREATE TRIGGER trg_government_expenses_touch_updated_at
BEFORE UPDATE ON government_expenses
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
    'Portal da Transparência / CGU',
    'transparencia',
    'Controladoria-Geral da União',
    'Portal oficial de dados abertos da CGU / Portal da Transparência',
    'https://portaldatransparencia.gov.br/',
    'https://portaldatransparencia.gov.br/api-de-dados',
    'official_registry',
    'federal',
    true,
    'monthly',
    'open data',
    true,
    jsonb_build_object(
        'portal_url', 'https://portaldatransparencia.gov.br/',
        'api_docs_url', 'https://portaldatransparencia.gov.br/api-de-dados',
        'bulk_download_page', 'https://portaldatransparencia.gov.br/download-de-dados/despesas-execucao'
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
    'Despesas Execucao - 2026-08',
    'despesas-execucao-2026-08',
    'despesas-execucao-202608',
    'csv',
    'https://portaldatransparencia.gov.br/download-de-dados/despesas-execucao/202608',
    'federal',
    DATE '2026-08-01',
    DATE '2026-08-31',
    'monthly',
    true,
    jsonb_build_object(
        'portal_url', 'https://portaldatransparencia.gov.br/',
        'bulk_download_page', 'https://portaldatransparencia.gov.br/download-de-dados/despesas-execucao',
        'zip_url', 'https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/despesas-execucao/202608_Despesas.zip',
        'csv_url', 'https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/despesas-execucao/202608_Despesas.csv',
        'slice', 'validated_sample'
    )
FROM sources AS s
WHERE s.slug = 'transparencia'
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
    ('transparencia', 'Pasta para o Portal da Transparência', false, false, false, 'open', 'all', false, 'active', 27, 'file-eye', '#0f766e')
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
    ('government_expenses', 'Despesas publicadas no Portal da Transparência', false, false, true, 'open', 'all', false, 'active', 28, 'transparencia', 'cash-multiple', '#14b8a6')
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
        ('government_expenses')
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
          AND collection = 'government_expenses'
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
            ('government_expenses', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id);
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
END $$;

COMMIT;
