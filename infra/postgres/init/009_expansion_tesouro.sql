BEGIN;

CREATE TABLE IF NOT EXISTS rreo_rows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    exercise integer NOT NULL,
    period integer NOT NULL,
    periodicity text NOT NULL,
    demonstrative text NOT NULL,
    institution text NOT NULL,
    entity_code integer NOT NULL,
    uf text,
    population bigint,
    annex text NOT NULL,
    sphere text NOT NULL,
    label text NOT NULL,
    column_label text NOT NULL,
    account_code text NOT NULL,
    account_name text NOT NULL,
    value_numeric numeric(24, 2) NOT NULL,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT rreo_rows_source_external_unique UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_rreo_rows_source_id ON rreo_rows(source_id);
CREATE INDEX IF NOT EXISTS idx_rreo_rows_dataset_id ON rreo_rows(dataset_id);
CREATE INDEX IF NOT EXISTS idx_rreo_rows_exercise_period ON rreo_rows(exercise, period);
CREATE INDEX IF NOT EXISTS idx_rreo_rows_entity_code ON rreo_rows(entity_code);
CREATE INDEX IF NOT EXISTS idx_rreo_rows_account_code ON rreo_rows(account_code);
CREATE INDEX IF NOT EXISTS idx_rreo_rows_value_numeric ON rreo_rows(value_numeric);

DROP TRIGGER IF EXISTS trg_rreo_rows_touch_updated_at ON rreo_rows;
CREATE TRIGGER trg_rreo_rows_touch_updated_at
BEFORE UPDATE ON rreo_rows
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
    'Tesouro Nacional / SICONFI',
    'tesouro',
    'Tesouro Nacional',
    'Portal oficial de dados abertos do Tesouro Nacional / SICONFI',
    'https://siconfi.tesouro.gov.br/',
    'https://apidatalake.tesouro.gov.br/docs/siconfi/',
    'official_registry',
    'federal',
    true,
    'bimonthly',
    'open data',
    true,
    jsonb_build_object(
        'portal_url', 'https://siconfi.tesouro.gov.br/',
        'api_docs_url', 'https://apidatalake.tesouro.gov.br/docs/siconfi/',
        'api_base_url', 'https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/'
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
    'RREO Anexo 01 - São Paulo 2024 6º bimestre',
    'rreo-sp-2024-p06-anexo01',
    'siconfi-rreo-sp-3550308-2024-p06-anexo01',
    'json',
    'https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/rreo?an_exercicio=2024&nr_periodo=6&co_tipo_demonstrativo=RREO&id_ente=3550308&no_anexo=RREO-Anexo%2001',
    'municipal',
    DATE '2024-11-01',
    DATE '2024-12-31',
    'bimonthly',
    true,
    jsonb_build_object(
        'api_path', '/rreo',
        'exercise', 2024,
        'period', 6,
        'entity_code', 3550308,
        'entity_name', 'São Paulo',
        'report_type', 'RREO',
        'annex', 'RREO-Anexo 01',
        'period_label', '6º bimestre de 2024'
    )
FROM sources AS s
WHERE s.slug = 'tesouro'
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
    ('tesouro', 'Pasta para dados fiscais do Tesouro / SICONFI', false, false, false, 'open', 'all', false, 'active', 29, 'bank', '#1e3a8a')
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
    ('rreo_rows', 'Linhas do RREO do SICONFI', false, false, true, 'open', 'all', false, 'active', 30, 'tesouro', 'table', '#3b82f6')
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
        ('rreo_rows')
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
          AND collection = 'rreo_rows'
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
            ('rreo_rows', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id);
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
