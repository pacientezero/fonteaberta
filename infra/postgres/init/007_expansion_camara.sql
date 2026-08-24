BEGIN;

CREATE TABLE IF NOT EXISTS mandates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    party_id uuid REFERENCES parties(id) ON DELETE SET NULL,
    external_id text NOT NULL,
    legislature_external_id text NOT NULL,
    chamber text NOT NULL DEFAULT 'camara',
    electoral_name text NOT NULL,
    state text NOT NULL,
    party_acronym text,
    status text NOT NULL,
    email text,
    profile_url text,
    photo_url text,
    started_at date,
    ended_at date,
    source_updated_at date,
    collected_at timestamptz NOT NULL DEFAULT now(),
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT mandates_source_external_unique UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_mandates_source_id ON mandates(source_id);
CREATE INDEX IF NOT EXISTS idx_mandates_dataset_id ON mandates(dataset_id);
CREATE INDEX IF NOT EXISTS idx_mandates_person_id ON mandates(person_id);
CREATE INDEX IF NOT EXISTS idx_mandates_party_id ON mandates(party_id);
CREATE INDEX IF NOT EXISTS idx_mandates_legislature ON mandates(legislature_external_id);
CREATE INDEX IF NOT EXISTS idx_mandates_state ON mandates(state);

DROP TRIGGER IF EXISTS trg_mandates_touch_updated_at ON mandates;
CREATE TRIGGER trg_mandates_touch_updated_at
BEFORE UPDATE ON mandates
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

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
    ('legislativo', 'Folder for parliamentary mandates and records', false, false, false, 'open', 'all', false, 'active', 24, 'gavel', '#7c3aed')
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
    ('mandates', 'Current parliamentary mandates for Câmara deputies', false, false, true, 'open', 'all', false, 'active', 25, 'legislativo', 'calendar-range', '#8b5cf6')
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
        ('mandates')
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
          AND collection = 'mandates'
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
            ('mandates', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id);
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
          AND collection = 'mandates'
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
            ('mandates', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id);
    END IF;
END $$;

COMMIT;
