BEGIN;

CREATE TABLE IF NOT EXISTS legislative_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    name text NOT NULL,
    event_type text,
    occurred_at timestamptz,
    location text,
    description text,
    source_url text,
    raw_record_id uuid REFERENCES raw_records(id) ON DELETE SET NULL,
    evidence_id uuid REFERENCES evidence(id) ON DELETE SET NULL,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT legislative_events_source_external_unique UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS legislative_propositions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    house text NOT NULL,
    sigla_tipo text NOT NULL,
    number integer NOT NULL,
    year integer NOT NULL,
    title text NOT NULL,
    summary text,
    presented_at timestamptz,
    status text,
    source_url text,
    raw_record_id uuid REFERENCES raw_records(id) ON DELETE SET NULL,
    evidence_id uuid REFERENCES evidence(id) ON DELETE SET NULL,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT legislative_propositions_source_external_unique UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS legislative_votes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    proposition_id uuid NOT NULL REFERENCES legislative_propositions(id) ON DELETE CASCADE,
    external_id text NOT NULL,
    house text NOT NULL,
    vote_date date,
    vote_timestamp timestamptz,
    description text NOT NULL,
    result text,
    vote_type text,
    approved boolean NOT NULL DEFAULT false,
    total_votes integer NOT NULL DEFAULT 0,
    yes_votes integer NOT NULL DEFAULT 0,
    no_votes integer NOT NULL DEFAULT 0,
    other_votes integer NOT NULL DEFAULT 0,
    source_url text,
    raw_record_id uuid REFERENCES raw_records(id) ON DELETE SET NULL,
    evidence_id uuid REFERENCES evidence(id) ON DELETE SET NULL,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT legislative_votes_source_external_unique UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS legislative_vote_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vote_id uuid NOT NULL REFERENCES legislative_votes(id) ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    party_id uuid REFERENCES parties(id) ON DELETE SET NULL,
    external_id text NOT NULL,
    vote_value text NOT NULL,
    vote_label text NOT NULL,
    source_url text,
    raw_record_id uuid REFERENCES raw_records(id) ON DELETE SET NULL,
    evidence_id uuid REFERENCES evidence(id) ON DELETE SET NULL,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT legislative_vote_members_vote_external_unique UNIQUE (vote_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_legislative_events_source_id ON legislative_events(source_id);
CREATE INDEX IF NOT EXISTS idx_legislative_events_dataset_id ON legislative_events(dataset_id);
CREATE INDEX IF NOT EXISTS idx_legislative_propositions_source_id ON legislative_propositions(source_id);
CREATE INDEX IF NOT EXISTS idx_legislative_propositions_dataset_id ON legislative_propositions(dataset_id);
CREATE INDEX IF NOT EXISTS idx_legislative_propositions_year ON legislative_propositions(year);
CREATE INDEX IF NOT EXISTS idx_legislative_votes_source_id ON legislative_votes(source_id);
CREATE INDEX IF NOT EXISTS idx_legislative_votes_dataset_id ON legislative_votes(dataset_id);
CREATE INDEX IF NOT EXISTS idx_legislative_votes_proposition_id ON legislative_votes(proposition_id);
CREATE INDEX IF NOT EXISTS idx_legislative_votes_date ON legislative_votes(vote_date);
CREATE INDEX IF NOT EXISTS idx_legislative_vote_members_vote_id ON legislative_vote_members(vote_id);
CREATE INDEX IF NOT EXISTS idx_legislative_vote_members_person_id ON legislative_vote_members(person_id);
CREATE INDEX IF NOT EXISTS idx_legislative_vote_members_party_id ON legislative_vote_members(party_id);

DROP TRIGGER IF EXISTS trg_legislative_events_touch_updated_at ON legislative_events;
CREATE TRIGGER trg_legislative_events_touch_updated_at
BEFORE UPDATE ON legislative_events
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_legislative_propositions_touch_updated_at ON legislative_propositions;
CREATE TRIGGER trg_legislative_propositions_touch_updated_at
BEFORE UPDATE ON legislative_propositions
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_legislative_votes_touch_updated_at ON legislative_votes;
CREATE TRIGGER trg_legislative_votes_touch_updated_at
BEFORE UPDATE ON legislative_votes
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
    'Camara dos Deputados',
    'camara',
    'Camara dos Deputados',
    'API oficial de dados abertos da Camara dos Deputados',
    'https://dadosabertos.camara.leg.br/api/v2',
    'https://dadosabertos.camara.leg.br/swagger/api.html',
    'official_registry',
    'federal',
    true,
    'daily',
    'open data',
    true,
    jsonb_build_object(
        'api_docs_url', 'https://dadosabertos.camara.leg.br/swagger/api.html',
        'openapi_url', 'https://dadosabertos.camara.leg.br/api/v2/api-docs',
        'legislature', 57,
        'proposition_archives_url', 'https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/proposicoes-2025.json',
        'vote_archives_url', 'https://dadosabertos.camara.leg.br/arquivos/votacoes/json/votacoes-2026.json'
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
            'Proposições 2025',
            'proposicoes-2025',
            'camara-proposicoes-2025',
            'json',
            'https://dadosabertos.camara.leg.br/arquivos/proposicoes/json/proposicoes-2025.json',
            'federal',
            DATE '2025-01-01',
            DATE '2025-12-31',
            'daily',
            true,
            jsonb_build_object(
                'archive_year', 2025,
                'resource_kind', 'proposicoes'
            )
        ),
        (
            'Votações 2026',
            'votacoes-2026',
            'camara-votacoes-2026',
            'json',
            'https://dadosabertos.camara.leg.br/arquivos/votacoes/json/votacoes-2026.json',
            'federal',
            DATE '2026-01-01',
            DATE '2026-12-31',
            'daily',
            true,
            jsonb_build_object(
                'archive_year', 2026,
                'resource_kind', 'votacoes'
            )
        ),
        (
            'Votos nominais 2026',
            'votacoes-votos-2026',
            'camara-votacoes-votos-2026',
            'json',
            'https://dadosabertos.camara.leg.br/arquivos/votacoesVotos/json/votacoesVotos-2026.json',
            'federal',
            DATE '2026-01-01',
            DATE '2026-12-31',
            'daily',
            true,
            jsonb_build_object(
                'archive_year', 2026,
                'resource_kind', 'votacoesVotos'
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
WHERE s.slug = 'camara'
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
    "group",
    icon,
    color
) VALUES
    ('legislative_events', 'Eventos legislativos oficiais', false, false, true, 'open', 'all', false, 'active', 26, 'legislativo', 'calendar-multiselect-outline', '#7c3aed'),
    ('legislative_propositions', 'Proposições legislativas oficiais', false, false, true, 'open', 'all', false, 'active', 27, 'legislativo', 'file-document-outline', '#4f46e5'),
    ('legislative_votes', 'Votações legislativas oficiais', false, false, true, 'open', 'all', false, 'active', 28, 'legislativo', 'scale-balance', '#0891b2'),
    ('legislative_vote_members', 'Votos nominais por parlamentar', false, false, true, 'open', 'all', false, 'active', 29, 'legislativo', 'account-multiple-outline', '#0f766e')
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
        ('legislative_events'),
        ('legislative_propositions'),
        ('legislative_votes'),
        ('legislative_vote_members')
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
          AND collection = 'legislative_events'
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
            ('legislative_events', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id),
            ('legislative_propositions', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id),
            ('legislative_votes', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id),
            ('legislative_vote_members', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id);
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
          AND collection = 'legislative_events'
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
            ('legislative_events', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('legislative_propositions', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('legislative_votes', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('legislative_vote_members', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id);
    END IF;
END $$;

COMMIT;
