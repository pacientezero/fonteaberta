BEGIN;

CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    entity_type text,
    entity_id uuid,
    document_type text NOT NULL,
    title text NOT NULL,
    description text,
    external_id text NOT NULL,
    source_url text NOT NULL,
    published_at timestamptz,
    mime_type text NOT NULL,
    latest_version_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT documents_source_external_unique UNIQUE (source_id, external_id)
);

CREATE TABLE IF NOT EXISTS document_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number integer NOT NULL,
    file_path text,
    file_url text,
    sha256 text NOT NULL,
    text_content text NOT NULL,
    collected_at timestamptz NOT NULL DEFAULT now(),
    source_updated_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT document_versions_document_version_unique UNIQUE (document_id, version_number)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_version_id uuid NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    page integer,
    section text,
    content text NOT NULL,
    embedding vector(384) NOT NULL,
    token_count integer NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT document_chunks_version_chunk_unique UNIQUE (document_version_id, chunk_index)
);

ALTER TABLE documents
    DROP CONSTRAINT IF EXISTS documents_latest_version_id_fkey;

ALTER TABLE documents
    ADD CONSTRAINT documents_latest_version_id_fkey
    FOREIGN KEY (latest_version_id) REFERENCES document_versions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_external_id ON documents(external_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_version_id ON document_chunks(document_version_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_page ON document_chunks(page);

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);

DROP TRIGGER IF EXISTS trg_documents_touch_updated_at ON documents;
CREATE TRIGGER trg_documents_touch_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_document_versions_touch_updated_at ON document_versions;
CREATE TRIGGER trg_document_versions_touch_updated_at
BEFORE UPDATE ON document_versions
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
    'Tribunal Superior Eleitoral',
    'tse',
    'Tribunal Superior Eleitoral',
    'Portal oficial de dados e documentos do TSE',
    'https://www.tse.jus.br/',
    'https://www.tse.jus.br/eleicoes/eleicoes-2026-content/sistema-de-candidaturas-modulo-externo-candex-2026',
    'official_registry',
    'federal',
    true,
    'daily',
    'open data',
    true,
    jsonb_build_object(
        'portal_url', 'https://www.tse.jus.br/',
        'document_catalog_url', 'https://www.tse.jus.br/eleicoes/eleicoes-2026-content/sistema-de-candidaturas-modulo-externo-candex-2026'
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
    ('documentos_rag', 'Folder for document and RAG tables', false, false, false, 'open', 'all', false, 'active', 17, 'file-document-multiple', '#0ea5e9')
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
    ('documents', 'Canonical document registry', false, false, true, 'open', 'all', false, 'active', 18, 'documentos_rag', 'file-document-multiple', '#06b6d4'),
    ('document_versions', 'Document version history', false, false, true, 'open', 'all', false, 'active', 19, 'documentos_rag', 'file-clock', '#0ea5e9'),
    ('document_chunks', 'Chunked document embeddings', false, false, true, 'open', 'all', false, 'active', 20, 'documentos_rag', 'vector-polyline', '#a855f7')
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
        ('documents'),
        ('document_versions'),
        ('document_chunks')
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
          AND collection = 'documents'
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
            ('documents', 'read', '{}'::json, '{}'::json, '{}'::json, '*', public_policy_id);
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
            ('documents'),
            ('document_versions'),
            ('document_chunks')
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
