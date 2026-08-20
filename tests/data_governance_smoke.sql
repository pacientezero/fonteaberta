BEGIN;

DO $$
DECLARE
    smoke_source_id uuid;
    smoke_dataset_id uuid;
    smoke_run_id uuid;
    smoke_raw_record_id uuid;
    smoke_evidence_id uuid;
    smoke_fact_id uuid;
    smoke_claim_id uuid;
    smoke_fact_subject_id uuid;
    expected_directus_field_count bigint;
    actual_directus_field_count bigint;
BEGIN
    INSERT INTO sources (
        name,
        slug,
        institution,
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
        'https://dadosabertos.tse.jus.br/',
        'https://dadosabertos.tse.jus.br/',
        'official_portal',
        'federal',
        true,
        'daily',
        'open-data',
        true,
        jsonb_build_object('note', 'smoke test source')
    )
    RETURNING id INTO smoke_source_id;

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
    ) VALUES (
        smoke_source_id,
        'Candidatos 2026',
        'candidatos-2026',
        'candidatos-2026',
        'csv',
        'https://dadosabertos.tse.jus.br/dataset/candidatos-2026',
        'federal',
        DATE '2026-01-01',
        DATE '2026-12-31',
        'daily',
        true,
        jsonb_build_object('note', 'smoke test dataset')
    )
    RETURNING id INTO smoke_dataset_id;

    INSERT INTO ingestion_runs (
        source_id,
        dataset_id,
        pipeline,
        run_type,
        started_at,
        finished_at,
        status,
        records_read,
        records_created,
        records_updated,
        records_unchanged,
        records_failed,
        source_checksum,
        metadata
    ) VALUES (
        smoke_source_id,
        smoke_dataset_id,
        'smoke-test',
        'full',
        now(),
        now(),
        'success',
        1,
        1,
        0,
        0,
        0,
        'sha256:smoke-test',
        '{}'::jsonb
    )
    RETURNING id INTO smoke_run_id;

    INSERT INTO raw_records (
        source_id,
        dataset_id,
        ingestion_run_id,
        external_id,
        payload,
        payload_hash,
        source_updated_at,
        collected_at,
        processing_status,
        metadata
    ) VALUES (
        smoke_source_id,
        smoke_dataset_id,
        smoke_run_id,
        'candidate-001',
        jsonb_build_object(
            'nome', 'Candidato de teste',
            'patrimonio_total', 5284321.90
        ),
        'sha256:raw-record-smoke',
        now(),
        now(),
        'normalized',
        '{}'::jsonb
    )
    RETURNING id INTO smoke_raw_record_id;

    INSERT INTO evidence (
        source_id,
        dataset_id,
        raw_record_id,
        external_id,
        source_url,
        page,
        section,
        collected_at,
        payload_hash,
        metadata
    ) VALUES (
        smoke_source_id,
        smoke_dataset_id,
        smoke_raw_record_id,
        'evidence-001',
        'https://dadosabertos.tse.jus.br/dataset/candidatos-2026',
        1,
        'bens',
        now(),
        'sha256:evidence-smoke',
        '{}'::jsonb
    )
    RETURNING id INTO smoke_evidence_id;

    INSERT INTO facts (
        subject_type,
        subject_id,
        predicate,
        object_type,
        object_id,
        value_numeric,
        unit,
        effective_date,
        source_id,
        evidence_id,
        calculation_method,
        metadata
    ) VALUES (
        'candidate',
        gen_random_uuid(),
        'declared_assets_total',
        'numeric',
        NULL,
        5284321.90,
        'BRL',
        DATE '2026-08-20',
        smoke_source_id,
        smoke_evidence_id,
        'sum(candidate_assets.value)',
        '{}'::jsonb
    )
    RETURNING id, subject_id INTO smoke_fact_id, smoke_fact_subject_id;

    INSERT INTO claims (
        claim_type,
        statement,
        subject_type,
        subject_id,
        calculation_method,
        model_provider,
        model_name,
        metadata
    ) VALUES (
        'computed_fact',
        'O candidato de teste declarou R$ 5.284.321,90 em bens.',
        'candidate',
        smoke_fact_subject_id,
        'sum(candidate_assets.value)',
        'manual',
        'smoke-test',
        jsonb_build_object('fact_id', smoke_fact_id)
    )
    RETURNING id INTO smoke_claim_id;

    INSERT INTO claims_evidence (claim_id, evidence_id)
    VALUES (smoke_claim_id, smoke_evidence_id);

    IF NOT EXISTS (
        SELECT 1
        FROM claims c
        JOIN claims_evidence ce ON ce.claim_id = c.id
        JOIN evidence e ON e.id = ce.evidence_id
        JOIN raw_records rr ON rr.id = e.raw_record_id
        JOIN datasets d ON d.id = rr.dataset_id
        JOIN sources s ON s.id = d.source_id
        WHERE c.id = smoke_claim_id
          AND s.id = smoke_source_id
          AND d.id = smoke_dataset_id
          AND rr.id = smoke_raw_record_id
          AND e.id = smoke_evidence_id
    ) THEN
        RAISE EXCEPTION 'Provenance chain failed in smoke test';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('sources'),
                ('datasets'),
                ('ingestion_runs'),
                ('raw_records'),
                ('evidence'),
                ('facts'),
                ('claims')
        ) AS managed(collection)
        LEFT JOIN directus_collections dc ON dc.collection = managed.collection
        WHERE dc.collection IS NULL
    ) THEN
        RAISE EXCEPTION 'Managed Directus collections are missing';
    END IF;

    SELECT count(*) INTO expected_directus_field_count
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name IN (
          'sources',
          'datasets',
          'ingestion_runs',
          'raw_records',
          'evidence',
          'facts',
          'claims'
      );

    SELECT count(*) INTO actual_directus_field_count
    FROM directus_fields
    WHERE collection IN (
        'sources',
        'datasets',
        'ingestion_runs',
        'raw_records',
        'evidence',
        'facts',
        'claims'
    );

    IF expected_directus_field_count <> actual_directus_field_count THEN
        RAISE EXCEPTION 'Managed Directus fields are missing';
    END IF;
END $$;

ROLLBACK;
