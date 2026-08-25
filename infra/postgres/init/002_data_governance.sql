BEGIN;

CREATE TABLE IF NOT EXISTS sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    institution text,
    description text,
    base_url text,
    documentation_url text,
    source_type text,
    scope text,
    official boolean NOT NULL DEFAULT true,
    update_frequency text,
    license text,
    enabled boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS datasets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    name text NOT NULL,
    slug text NOT NULL,
    external_id text,
    format text,
    resource_url text,
    scope text,
    period_start date,
    period_end date,
    update_frequency text,
    enabled boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT datasets_source_slug_unique UNIQUE (source_id, slug)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    pipeline text NOT NULL,
    run_type text NOT NULL,
    started_at timestamptz,
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'pending',
    records_read bigint NOT NULL DEFAULT 0,
    records_created bigint NOT NULL DEFAULT 0,
    records_updated bigint NOT NULL DEFAULT 0,
    records_unchanged bigint NOT NULL DEFAULT 0,
    records_failed bigint NOT NULL DEFAULT 0,
    source_checksum text,
    error_summary text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ingestion_runs_status_check
        CHECK (status IN ('pending', 'running', 'success', 'partial', 'failed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS raw_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    ingestion_run_id uuid REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    external_id text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    payload_hash text NOT NULL,
    source_updated_at timestamptz,
    collected_at timestamptz NOT NULL DEFAULT now(),
    processing_status text NOT NULL DEFAULT 'pending',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT raw_records_unique_external UNIQUE (source_id, dataset_id, external_id),
    CONSTRAINT raw_records_processing_status_check
        CHECK (processing_status IN ('pending', 'processed', 'normalized', 'failed'))
);

CREATE TABLE IF NOT EXISTS evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    dataset_id uuid NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    raw_record_id uuid REFERENCES raw_records(id) ON DELETE SET NULL,
    external_id text,
    source_url text,
    page integer,
    section text,
    collected_at timestamptz NOT NULL DEFAULT now(),
    payload_hash text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT evidence_unique_external UNIQUE (source_id, dataset_id, external_id)
);

CREATE TABLE IF NOT EXISTS facts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type text NOT NULL,
    subject_id uuid NOT NULL,
    predicate text NOT NULL,
    object_type text,
    object_id uuid,
    value_text text,
    value_numeric numeric(18, 2),
    value_boolean boolean,
    value_date date,
    unit text,
    effective_date date,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    evidence_id uuid REFERENCES evidence(id) ON DELETE SET NULL,
    calculation_method text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claims (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_type text NOT NULL,
    statement text NOT NULL,
    subject_type text NOT NULL,
    subject_id uuid NOT NULL,
    calculation_method text,
    model_provider text,
    model_name text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT claims_claim_type_check
        CHECK (claim_type IN ('official_fact', 'computed_fact'))
);

CREATE TABLE IF NOT EXISTS claims_evidence (
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    evidence_id uuid NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (claim_id, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_datasets_source_id ON datasets(source_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_dataset_id ON ingestion_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_raw_records_source_external ON raw_records(source_id, external_id);
CREATE INDEX IF NOT EXISTS idx_raw_records_payload_hash ON raw_records(payload_hash);
CREATE INDEX IF NOT EXISTS idx_evidence_raw_record_id ON evidence(raw_record_id);
CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject_type, subject_id, predicate);
CREATE INDEX IF NOT EXISTS idx_claims_subject ON claims(subject_type, subject_id);

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sources_touch_updated_at ON sources;
CREATE TRIGGER trg_sources_touch_updated_at
BEFORE UPDATE ON sources
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_datasets_touch_updated_at ON datasets;
CREATE TRIGGER trg_datasets_touch_updated_at
BEFORE UPDATE ON datasets
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
    ('catalogo', 'Pasta para catálogo de fontes e datasets', false, false, false, 'open', 'all', false, 'active', 0, 'database', '#475569'),
    ('ingestao', 'Pasta para histórico de execuções de ingestão', false, false, false, 'open', 'all', false, 'active', 3, 'tray-arrow-down', '#d97706'),
    ('proveniencia', 'Pasta para registros brutos, evidências, fatos e claims', false, false, false, 'open', 'all', false, 'active', 5, 'shield-check', '#059669'),
    ('transparencia', 'Pasta reservada para o Portal da Transparência', false, false, false, 'open', 'all', false, 'active', 27, 'file-eye', '#0f766e')
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
    ('sources', 'Cadastro canônico de fontes oficiais', false, false, true, 'open', 'all', false, 'active', 1, 'catalogo', 'database', '#2563eb'),
    ('datasets', 'Catálogo canônico de datasets', false, false, true, 'open', 'all', false, 'active', 2, 'catalogo', 'table', '#14b8a6'),
    ('ingestion_runs', 'Histórico de execuções de ingestão', false, false, true, 'open', 'all', false, 'active', 4, 'ingestao', 'sync', '#d97706'),
    ('raw_records', 'Registros brutos de ingestão', false, false, true, 'open', 'all', false, 'active', 6, 'proveniencia', 'archive', '#64748b'),
    ('evidence', 'Evidências ligadas aos registros brutos', false, false, true, 'open', 'all', false, 'active', 7, 'proveniencia', 'shield-search', '#10b981'),
    ('facts', 'Fatos normalizados', false, false, true, 'open', 'all', false, 'active', 8, 'proveniencia', 'calculator', '#059669'),
    ('claims', 'Afirmações com proveniência', false, false, true, 'open', 'all', false, 'active', 9, 'proveniencia', 'comment-text-outline', '#8b5cf6')
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
        ('sources'),
        ('datasets'),
        ('ingestion_runs'),
        ('raw_records'),
        ('evidence'),
        ('facts'),
        ('claims')
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

UPDATE directus_collections
SET "group" = 'catalogo'
WHERE "group" = 'cadastros';

UPDATE directus_collections
SET "group" = 'ingestao'
WHERE "group" = 'operacao';

UPDATE directus_collections
SET "group" = 'proveniencia'
WHERE "group" = 'auditoria';

DELETE FROM directus_collections
WHERE collection IN ('cadastros', 'operacao', 'auditoria');

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
          AND collection = 'sources'
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
            ('sources', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id),
            ('datasets', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id),
            ('facts', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id),
            ('evidence', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id),
            ('claims', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id);
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
          AND collection = 'sources'
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
            ('sources', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('datasets', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('ingestion_runs', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('raw_records', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('facts', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('evidence', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('claims', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id),
            ('claims_evidence', 'read', '{}'::json, '{}'::json, '{}'::json, '*', researcher_policy_id);
    END IF;
END $$;

COMMIT;
