BEGIN;

CREATE TABLE IF NOT EXISTS economic_series (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    name text NOT NULL,
    description text,
    unit text,
    frequency text,
    series_code integer,
    start_date date,
    end_date date,
    active boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT economic_series_source_external_unique UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS economic_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    economic_series_id uuid NOT NULL REFERENCES economic_series(id) ON DELETE CASCADE,
    observation_date date NOT NULL,
    value numeric(18, 6) NOT NULL,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT economic_observations_series_date_unique UNIQUE (economic_series_id, observation_date)
);

CREATE INDEX IF NOT EXISTS idx_economic_series_source_id ON economic_series(source_id);
CREATE INDEX IF NOT EXISTS idx_economic_series_dataset_id ON economic_series(dataset_id);
CREATE INDEX IF NOT EXISTS idx_economic_observations_series_id ON economic_observations(economic_series_id);
CREATE INDEX IF NOT EXISTS idx_economic_observations_date ON economic_observations(observation_date);
CREATE INDEX IF NOT EXISTS idx_economic_observations_value ON economic_observations(value);

DROP TRIGGER IF EXISTS trg_economic_series_touch_updated_at ON economic_series;
CREATE TRIGGER trg_economic_series_touch_updated_at
BEFORE UPDATE ON economic_series
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
    'Banco Central do Brasil',
    'bcb',
    'Banco Central do Brasil',
    'Portal oficial de séries temporais econômicas do BCB',
    'https://dadosabertos.bcb.gov.br/',
    'https://dadosabertos.bcb.gov.br/dataset/11-taxa-de-juros---selic/resource/b73edc07-bbac-430c-a2cb-b1639e605fa8',
    'official_registry',
    'federal',
    true,
    'daily',
    'open data',
    true,
    jsonb_build_object(
        'portal_url', 'https://dadosabertos.bcb.gov.br/',
        'api_base_url', 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados',
        'series_code', 11,
        'series_name', 'Taxa Selic'
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
    'Taxa Selic - SGS 11',
    'selic-sgs-11-2024',
    'sgs-11-selic',
    'json',
    'https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json&dataInicial=01/01/2024&dataFinal=31/12/2024',
    'federal',
    DATE '2024-01-02',
    DATE '2024-12-31',
    'daily',
    true,
    jsonb_build_object(
        'series_code', 11,
        'series_name', 'Taxa Selic',
        'portal_dataset_url', 'https://dadosabertos.bcb.gov.br/dataset/11-taxa-de-juros---selic/resource/b73edc07-bbac-430c-a2cb-b1639e605fa8'
    )
FROM sources AS s
WHERE s.slug = 'bcb'
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
    ('economia', 'Pasta para séries macroeconômicas e observações', false, false, false, 'open', 'all', false, 'active', 21, 'chart-box-outline', '#0891b2')
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
    ('economic_series', 'Séries macroeconômicas oficiais', false, false, true, 'open', 'all', false, 'active', 22, 'economia', 'chart-line', '#0ea5e9'),
    ('economic_observations', 'Observações das séries macroeconômicas', false, false, true, 'open', 'all', false, 'active', 23, 'economia', 'table-clock', '#14b8a6')
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
        ('economic_series'),
        ('economic_observations')
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
          AND collection = 'economic_series'
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
            ('economic_series', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id),
            ('economic_observations', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id);
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
          AND collection = 'economic_series'
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
            ('economic_series', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('economic_observations', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id);
    END IF;
END $$;

COMMIT;
