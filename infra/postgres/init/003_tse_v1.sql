BEGIN;

CREATE TABLE IF NOT EXISTS people (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name text NOT NULL,
    normalized_name text NOT NULL,
    birth_date date,
    birth_place text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    external_name text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT entity_aliases_source_entity_external_unique UNIQUE (source_id, entity_type, external_id)
);

CREATE TABLE IF NOT EXISTS elections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    year integer NOT NULL,
    round integer NOT NULL DEFAULT 1,
    election_type text NOT NULL,
    scope text NOT NULL,
    country text NOT NULL DEFAULT 'BR',
    state text NOT NULL DEFAULT '',
    city text NOT NULL DEFAULT '',
    election_date date,
    status text NOT NULL DEFAULT 'scheduled',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT elections_unique_key UNIQUE (year, round, election_type, scope, country, state, city)
);

CREATE TABLE IF NOT EXISTS parties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id text NOT NULL UNIQUE,
    name text NOT NULL,
    acronym text NOT NULL,
    number integer,
    official_url text,
    logo_url text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id uuid NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    election_id uuid NOT NULL REFERENCES elections(id) ON DELETE RESTRICT,
    party_id uuid REFERENCES parties(id) ON DELETE SET NULL,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    ballot_number integer,
    position text,
    application_status text,
    result_status text,
    occupation text,
    education text,
    declared_assets_total numeric(18,2),
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT candidates_source_external_unique UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS candidate_assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id uuid NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    asset_type text NOT NULL,
    description text NOT NULL,
    value numeric(18,2) NOT NULL,
    currency char(3) NOT NULL DEFAULT 'BRL',
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_updated_at timestamptz,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT candidate_assets_candidate_external_unique UNIQUE (candidate_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_people_normalized_name ON people(normalized_name);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_lookup ON entity_aliases(source_id, entity_type, external_id);
CREATE INDEX IF NOT EXISTS idx_elections_year_scope ON elections(year, scope);
CREATE INDEX IF NOT EXISTS idx_candidates_person_id ON candidates(person_id);
CREATE INDEX IF NOT EXISTS idx_candidates_election_id ON candidates(election_id);
CREATE INDEX IF NOT EXISTS idx_candidates_external_id ON candidates(external_id);
CREATE INDEX IF NOT EXISTS idx_candidate_assets_candidate ON candidate_assets(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_assets_value ON candidate_assets(value);

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_people_touch_updated_at ON people;
CREATE TRIGGER trg_people_touch_updated_at
BEFORE UPDATE ON people
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_elections_touch_updated_at ON elections;
CREATE TRIGGER trg_elections_touch_updated_at
BEFORE UPDATE ON elections
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_parties_touch_updated_at ON parties;
CREATE TRIGGER trg_parties_touch_updated_at
BEFORE UPDATE ON parties
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_candidates_touch_updated_at ON candidates;
CREATE TRIGGER trg_candidates_touch_updated_at
BEFORE UPDATE ON candidates
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

CREATE OR REPLACE VIEW candidate_asset_totals AS
SELECT
    c.id AS candidate_id,
    c.external_id AS candidate_external_id,
    c.person_id,
    c.election_id,
    c.party_id,
    c.source_id,
    COUNT(a.id)::integer AS asset_count,
    COALESCE(SUM(a.value), 0)::numeric(18,2) AS declared_assets_total,
    MIN(a.source_updated_at) AS first_asset_source_updated_at,
    MAX(a.source_updated_at) AS last_asset_source_updated_at
FROM candidates AS c
LEFT JOIN candidate_assets AS a
    ON a.candidate_id = c.id
GROUP BY
    c.id,
    c.external_id,
    c.person_id,
    c.election_id,
    c.party_id,
    c.source_id;

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
    'Tribunal Superior Eleitoral',
    'tse',
    'Tribunal Superior Eleitoral',
    'Portal oficial de dados abertos do TSE para candidaturas e bens declarados',
    'https://dadosabertos.tse.jus.br/',
    'https://dadosabertos.tse.jus.br/dataset/candidatos-2026',
    'official_registry',
    'federal',
    true,
    'daily',
    'open data',
    true,
    jsonb_build_object(
        'portal_url', 'https://dadosabertos.tse.jus.br/',
        'candidate_dataset_url', 'https://dadosabertos.tse.jus.br/dataset/candidatos-2026',
        'candidate_assets_dataset_url', 'https://dadosabertos.tse.jus.br/dataset/candidatos-2026'
    )
)
ON CONFLICT (slug) DO UPDATE
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
    v.name,
    v.slug,
    v.external_id,
    v.format,
    v.resource_url,
    v.scope,
    v.period_start,
    v.period_end,
    v.update_frequency,
    v.enabled,
    v.metadata
FROM sources AS s
CROSS JOIN (
    VALUES
        (
            'Candidatos 2026',
            'candidatos-2026',
            'candidatos-2026',
            'zip/csv',
            'https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip',
            'federal',
            NULL::date,
            NULL::date,
            'daily',
            true,
            jsonb_build_object(
                'portal_dataset_url', 'https://dadosabertos.tse.jus.br/dataset/candidatos-2026',
                'resource_kind', 'consulta_cand_2026'
            )
        ),
        (
            'Bens de Candidatos 2026',
            'bens-candidato-2026',
            'bens-candidato-2026',
            'zip/csv',
            'https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2026.zip',
            'federal',
            NULL::date,
            NULL::date,
            'daily',
            true,
            jsonb_build_object(
                'portal_dataset_url', 'https://dadosabertos.tse.jus.br/dataset/candidatos-2026',
                'resource_kind', 'bem_candidato_2026'
            )
        )
) AS v (
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
WHERE s.slug = 'tse'
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
    sort
) VALUES
    ('people', 'Canonical person registry for candidate mapping', false, false, true, 'open', 'all', false, 'active', 8),
    ('entity_aliases', 'Cross-source entity aliases', false, false, true, 'open', 'all', false, 'active', 9),
    ('elections', 'Canonical elections registry', false, false, true, 'open', 'all', false, 'active', 10),
    ('parties', 'Canonical party registry', false, false, true, 'open', 'all', false, 'active', 11),
    ('candidates', 'Normalized candidate records', false, false, true, 'open', 'all', false, 'active', 12),
    ('candidate_assets', 'Declared candidate assets', false, false, true, 'open', 'all', false, 'active', 13)
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
    sort = EXCLUDED.sort;

WITH managed_tables(collection) AS (
    VALUES
        ('people'),
        ('entity_aliases'),
        ('elections'),
        ('parties'),
        ('candidates'),
        ('candidate_assets')
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

    INSERT INTO directus_permissions (
        collection,
        action,
        permissions,
        validation,
        presets,
        fields,
        policy
    )
    SELECT
        v.collection,
        'read',
        '{}'::json,
        '{}'::json,
        '{}'::json,
        '*',
        public_policy_id
    FROM (
        VALUES
            ('people'),
            ('elections'),
            ('parties'),
            ('candidates'),
            ('candidate_assets')
    ) AS v(collection)
    WHERE NOT EXISTS (
        SELECT 1
        FROM directus_permissions
        WHERE policy = public_policy_id
          AND collection = v.collection
          AND action = 'read'
    );

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

    INSERT INTO directus_permissions (
        collection,
        action,
        permissions,
        validation,
        presets,
        fields,
        policy
    )
    SELECT
        v.collection,
        'read',
        '{}'::json,
        '{}'::json,
        '{}'::json,
        '*',
        researcher_policy_id
    FROM (
        VALUES
            ('people'),
            ('entity_aliases'),
            ('elections'),
            ('parties'),
            ('candidates'),
            ('candidate_assets')
    ) AS v(collection)
    WHERE NOT EXISTS (
        SELECT 1
        FROM directus_permissions
        WHERE policy = researcher_policy_id
          AND collection = v.collection
          AND action = 'read'
    );
END $$;

COMMIT;
