from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "tse" / "official_2026_presidential_bundle.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "tse" / "official_2026_presidential_bundle.json"

TSE_SOURCE_SLUG = "tse"
TSE_CANDIDATES_DATASET_SLUG = "candidatos-2026"
TSE_ASSETS_DATASET_SLUG = "bens-candidato-2026"


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(stripped.upper().split())


def parse_br_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%d/%m/%Y").date()


def parse_br_datetime(date_value: str | None, time_value: str | None) -> datetime | None:
    if not date_value or not time_value:
        return None
    parsed = datetime.strptime(f"{date_value} {time_value}", "%d/%m/%Y %H:%M:%S")
    return parsed.replace(tzinfo=BRAZIL_TZ)


def parse_decimal(value: str | int | float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text or text in {"#NULO", "#NE", "##################"}:
        return None
    normalized = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    quantized = value.quantize(Decimal("0.01"))
    return f"{quantized:.2f}"


def format_brl(value: Decimal | None) -> str | None:
    if value is None:
        return None
    quantized = value.quantize(Decimal("0.01"))
    whole, fraction = f"{quantized:.2f}".split(".")
    whole_with_thousands = format(int(whole), ",").replace(",", ".")
    return f"R$ {whole_with_thousands},{fraction}"


def format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _fetch_one(conn, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise RuntimeError("Expected row not found")
    return dict(row)


def upsert_source(conn, bundle: Mapping[str, Any]) -> dict[str, Any]:
    metadata = bundle.get("metadata", {})
    return _fetch_one(
        conn,
        """
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
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
            updated_at = now()
        RETURNING id, name, slug, institution, description, base_url, documentation_url, source_type, scope, official, update_frequency, license, enabled, metadata, created_at, updated_at
        """,
        (
            "Tribunal Superior Eleitoral",
            TSE_SOURCE_SLUG,
            "Tribunal Superior Eleitoral",
            "Portal oficial de dados abertos do TSE para candidaturas e bens declarados",
            "https://dadosabertos.tse.jus.br/",
            "https://dadosabertos.tse.jus.br/dataset/candidatos-2026",
            "official_registry",
            "federal",
            True,
            "daily",
            "open data",
            True,
            Jsonb(
                {
                    "portal_url": "https://dadosabertos.tse.jus.br/",
                    "candidate_dataset_url": bundle["metadata"]["candidate_dataset_url"],
                    "candidate_assets_dataset_url": bundle["metadata"]["asset_dataset_url"],
                }
            ),
        ),
    )


def upsert_dataset(
    conn,
    source_id: str,
    name: str,
    slug: str,
    external_id: str,
    resource_url: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return _fetch_one(
        conn,
        """
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL, %s, %s, %s)
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
            updated_at = now()
        RETURNING id, source_id, name, slug, external_id, format, resource_url, scope, period_start, period_end, update_frequency, enabled, metadata, created_at, updated_at
        """,
        (
            source_id,
            name,
            slug,
            external_id,
            "zip/csv",
            resource_url,
            "federal",
            "daily",
            True,
            Jsonb(dict(metadata)),
        ),
    )


def ensure_tse_catalog(conn, bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    source = upsert_source(conn, bundle)
    candidate_dataset = upsert_dataset(
        conn,
        source["id"],
        "Candidatos 2026",
        TSE_CANDIDATES_DATASET_SLUG,
        TSE_CANDIDATES_DATASET_SLUG,
        bundle["metadata"]["candidate_dataset_url"],
        {
            "portal_dataset_url": "https://dadosabertos.tse.jus.br/dataset/candidatos-2026",
            "resource_kind": "consulta_cand_2026",
        },
    )
    asset_dataset = upsert_dataset(
        conn,
        source["id"],
        "Bens de Candidatos 2026",
        TSE_ASSETS_DATASET_SLUG,
        TSE_ASSETS_DATASET_SLUG,
        bundle["metadata"]["asset_dataset_url"],
        {
            "portal_dataset_url": "https://dadosabertos.tse.jus.br/dataset/candidatos-2026",
            "resource_kind": "bem_candidato_2026",
        },
    )
    return {
        "source": source,
        "candidate_dataset": candidate_dataset,
        "asset_dataset": asset_dataset,
    }


def upsert_election(conn, candidate_row: Mapping[str, Any]) -> dict[str, Any]:
    return _fetch_one(
        conn,
        """
        INSERT INTO elections (
            year,
            round,
            election_type,
            scope,
            country,
            state,
            city,
            election_date,
            status,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (year, round, election_type, scope, country, state, city) DO UPDATE
        SET
            election_date = EXCLUDED.election_date,
            status = EXCLUDED.status,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING id, year, round, election_type, scope, country, state, city, election_date, status, metadata, created_at, updated_at
        """,
        (
            int(candidate_row["ANO_ELEICAO"]),
            int(candidate_row["NR_TURNO"]),
            candidate_row["NM_TIPO_ELEICAO"],
            "federal",
            "BR",
            candidate_row["SG_UF"],
            candidate_row["NM_UE"],
            parse_br_date(candidate_row["DT_ELEICAO"]),
            "scheduled",
            Jsonb(
                {
                    "source_election_id": candidate_row["CD_ELEICAO"],
                    "source_election_name": candidate_row["DS_ELEICAO"],
                    "abrangencia": candidate_row["TP_ABRANGENCIA"],
                }
            ),
        ),
    )


def upsert_party(conn, candidate_row: Mapping[str, Any]) -> dict[str, Any]:
    return _fetch_one(
        conn,
        """
        INSERT INTO parties (
            external_id,
            name,
            acronym,
            number,
            official_url,
            logo_url,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (external_id) DO UPDATE
        SET
            name = EXCLUDED.name,
            acronym = EXCLUDED.acronym,
            number = EXCLUDED.number,
            official_url = EXCLUDED.official_url,
            logo_url = EXCLUDED.logo_url,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING id, external_id, name, acronym, number, official_url, logo_url, metadata, created_at, updated_at
        """,
        (
            candidate_row["NR_PARTIDO"],
            candidate_row["NM_PARTIDO"],
            candidate_row["SG_PARTIDO"],
            int(candidate_row["NR_PARTIDO"]),
            None,
            None,
            Jsonb(
                {
                    "source_party_name": candidate_row["NM_PARTIDO"],
                    "source_party_acronym": candidate_row["SG_PARTIDO"],
                }
            ),
        ),
    )


def upsert_person(conn, source_id: str, candidate_row: Mapping[str, Any]) -> dict[str, Any]:
    external_id = candidate_row["SQ_CANDIDATO"]
    alias = conn.execute(
        """
        SELECT p.id
        FROM entity_aliases AS ea
        JOIN people AS p ON p.id = ea.entity_id
        WHERE ea.source_id = %s
          AND ea.entity_type = 'person'
          AND ea.external_id = %s
        LIMIT 1
        """,
        (source_id, external_id),
    ).fetchone()

    person_payload = {
        "canonical_name": candidate_row["NM_CANDIDATO"],
        "normalized_name": normalize_name(candidate_row["NM_CANDIDATO"]),
        "birth_date": parse_br_date(candidate_row["DT_NASCIMENTO"]),
        "birth_place": candidate_row["SG_UF_NASCIMENTO"],
        "metadata": {
            "urna_name": candidate_row["NM_URNA_CANDIDATO"],
            "social_name": None if candidate_row["NM_SOCIAL_CANDIDATO"] == "#NULO" else candidate_row["NM_SOCIAL_CANDIDATO"],
            "gender": candidate_row["DS_GENERO"],
            "gender_code": candidate_row["CD_GENERO"],
            "race": candidate_row["DS_COR_RACA"],
            "race_code": candidate_row["CD_COR_RACA"],
            "education": candidate_row["DS_GRAU_INSTRUCAO"],
            "education_code": candidate_row["CD_GRAU_INSTRUCAO"],
            "marital_status": candidate_row["DS_ESTADO_CIVIL"],
            "marital_status_code": candidate_row["CD_ESTADO_CIVIL"],
            "occupation_code": candidate_row["CD_OCUPACAO"],
        },
    }

    if alias is None:
        person = _fetch_one(
            conn,
            """
            INSERT INTO people (
                canonical_name,
                normalized_name,
                birth_date,
                birth_place,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, canonical_name, normalized_name, birth_date, birth_place, metadata, created_at, updated_at
            """,
            (
                person_payload["canonical_name"],
                person_payload["normalized_name"],
                person_payload["birth_date"],
                person_payload["birth_place"],
                Jsonb(person_payload["metadata"]),
            ),
        )
        conn.execute(
            """
            INSERT INTO entity_aliases (
                entity_type,
                entity_id,
                source_id,
                external_id,
                external_name,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, entity_type, external_id) DO UPDATE
            SET
                entity_id = EXCLUDED.entity_id,
                external_name = EXCLUDED.external_name,
                metadata = EXCLUDED.metadata
            """,
            (
                "person",
                person["id"],
                source_id,
                external_id,
                candidate_row["NM_CANDIDATO"],
                Jsonb(
                    {
                        "urna_name": candidate_row["NM_URNA_CANDIDATO"],
                        "source_nationality": candidate_row["SG_UF_NASCIMENTO"],
                    }
                ),
            ),
        )
        return person

    person_id = alias["id"]
    person = _fetch_one(
        conn,
        """
        UPDATE people
        SET
            canonical_name = %s,
            normalized_name = %s,
            birth_date = %s,
            birth_place = %s,
            metadata = %s
        WHERE id = %s
        RETURNING id, canonical_name, normalized_name, birth_date, birth_place, metadata, created_at, updated_at
        """,
        (
            person_payload["canonical_name"],
            person_payload["normalized_name"],
            person_payload["birth_date"],
            person_payload["birth_place"],
            Jsonb(person_payload["metadata"]),
            person_id,
        ),
    )
    conn.execute(
        """
        UPDATE entity_aliases
        SET
            external_name = %s,
            metadata = %s
        WHERE source_id = %s
          AND entity_type = 'person'
          AND external_id = %s
        """,
        (
            candidate_row["NM_CANDIDATO"],
            Jsonb(
                {
                    "urna_name": candidate_row["NM_URNA_CANDIDATO"],
                    "source_nationality": candidate_row["SG_UF_NASCIMENTO"],
                }
            ),
            source_id,
            external_id,
        ),
    )
    return person


def upsert_candidate(
    conn,
    source_id: str,
    person_id: str,
    election_id: str,
    party_id: str,
    candidate_row: Mapping[str, Any],
    declared_assets_total: Decimal,
    source_updated_at: datetime | None,
    collected_at: datetime,
) -> dict[str, Any]:
    return _fetch_one(
        conn,
        """
        INSERT INTO candidates (
            person_id,
            election_id,
            party_id,
            source_id,
            external_id,
            ballot_number,
            position,
            application_status,
            result_status,
            occupation,
            education,
            declared_assets_total,
            source_updated_at,
            collected_at,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            person_id = EXCLUDED.person_id,
            election_id = EXCLUDED.election_id,
            party_id = EXCLUDED.party_id,
            ballot_number = EXCLUDED.ballot_number,
            position = EXCLUDED.position,
            application_status = EXCLUDED.application_status,
            result_status = EXCLUDED.result_status,
            occupation = EXCLUDED.occupation,
            education = EXCLUDED.education,
            declared_assets_total = EXCLUDED.declared_assets_total,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            raw_payload = EXCLUDED.raw_payload,
            updated_at = now()
        RETURNING id, person_id, election_id, party_id, source_id, external_id, ballot_number, position, application_status, result_status, occupation, education, declared_assets_total, source_updated_at, collected_at, raw_payload, created_at, updated_at
        """,
        (
            person_id,
            election_id,
            party_id,
            source_id,
            candidate_row["SQ_CANDIDATO"],
            int(candidate_row["NR_CANDIDATO"]),
            candidate_row["DS_CARGO"],
            candidate_row["DS_SITUACAO_CANDIDATURA"],
            candidate_row["DS_SIT_TOT_TURNO"],
            candidate_row["DS_OCUPACAO"],
            candidate_row["DS_GRAU_INSTRUCAO"],
            declared_assets_total,
            source_updated_at,
            collected_at,
            Jsonb(dict(candidate_row)),
        ),
    )


def upsert_raw_record(
    conn,
    source_id: str,
    dataset_id: str,
    ingestion_run_id: str,
    external_id: str,
    payload: Mapping[str, Any],
    source_updated_at: datetime | None,
    collected_at: datetime,
    processing_status: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return _fetch_one(
        conn,
        """
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
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, dataset_id, external_id) DO UPDATE
        SET
            ingestion_run_id = EXCLUDED.ingestion_run_id,
            payload = EXCLUDED.payload,
            payload_hash = EXCLUDED.payload_hash,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            processing_status = EXCLUDED.processing_status,
            metadata = EXCLUDED.metadata
        RETURNING id, source_id, dataset_id, ingestion_run_id, external_id, payload, payload_hash, source_updated_at, collected_at, processing_status, metadata, created_at
        """,
        (
            source_id,
            dataset_id,
            ingestion_run_id,
            external_id,
            Jsonb(dict(payload)),
            payload_hash(payload),
            source_updated_at,
            collected_at,
            processing_status,
            Jsonb(dict(metadata)),
        ),
    )


def upsert_evidence(
    conn,
    source_id: str,
    dataset_id: str,
    raw_record_id: str,
    external_id: str,
    source_url: str,
    section: str | None,
    collected_at: datetime,
    payload_hash_value: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return _fetch_one(
        conn,
        """
        INSERT INTO evidence (
            source_id,
            dataset_id,
            raw_record_id,
            external_id,
            source_url,
            section,
            collected_at,
            payload_hash,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, dataset_id, external_id) DO UPDATE
        SET
            raw_record_id = EXCLUDED.raw_record_id,
            source_url = EXCLUDED.source_url,
            section = EXCLUDED.section,
            collected_at = EXCLUDED.collected_at,
            payload_hash = EXCLUDED.payload_hash,
            metadata = EXCLUDED.metadata
        RETURNING id, source_id, dataset_id, raw_record_id, external_id, source_url, page, section, collected_at, payload_hash, metadata, created_at
        """,
        (
            source_id,
            dataset_id,
            raw_record_id,
            external_id,
            source_url,
            section,
            collected_at,
            payload_hash_value,
            Jsonb(dict(metadata)),
        ),
    )


def upsert_candidate_asset(
    conn,
    candidate_id: str,
    source_id: str,
    asset_row: Mapping[str, Any],
    source_updated_at: datetime | None,
) -> dict[str, Any]:
    value = parse_decimal(asset_row["VR_BEM_CANDIDATO"])
    if value is None:
        raise ValueError(f"Invalid asset value for {asset_row['NR_ORDEM_BEM_CANDIDATO']}")
    return _fetch_one(
        conn,
        """
        INSERT INTO candidate_assets (
            candidate_id,
            external_id,
            asset_type,
            description,
            value,
            currency,
            source_id,
            source_updated_at,
            raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (candidate_id, external_id) DO UPDATE
        SET
            asset_type = EXCLUDED.asset_type,
            description = EXCLUDED.description,
            value = EXCLUDED.value,
            currency = EXCLUDED.currency,
            source_id = EXCLUDED.source_id,
            source_updated_at = EXCLUDED.source_updated_at,
            raw_payload = EXCLUDED.raw_payload
        RETURNING id, candidate_id, external_id, asset_type, description, value, currency, source_id, source_updated_at, raw_payload, created_at
        """,
        (
            candidate_id,
            asset_row["NR_ORDEM_BEM_CANDIDATO"],
            asset_row["DS_TIPO_BEM_CANDIDATO"],
            asset_row["DS_BEM_CANDIDATO"],
            value,
            "BRL",
            source_id,
            source_updated_at,
            Jsonb(dict(asset_row)),
        ),
    )


def insert_claim_fact_and_links(
    conn,
    candidate_id: str,
    source_id: str,
    declared_assets_total: Decimal,
    asset_count: int,
    candidate_evidence_id: str,
    asset_evidence_ids: list[str],
    candidate_external_id: str,
) -> dict[str, Any]:
    conn.execute(
        """
        DELETE FROM claims_evidence
        WHERE claim_id IN (
            SELECT id
            FROM claims
            WHERE subject_type = 'candidate'
              AND subject_id = %s
              AND claim_type = 'computed_fact'
        )
        """,
        (candidate_id,),
    )
    conn.execute(
        """
        DELETE FROM claims
        WHERE subject_type = 'candidate'
          AND subject_id = %s
          AND claim_type = 'computed_fact'
        """,
        (candidate_id,),
    )
    conn.execute(
        """
        DELETE FROM facts
        WHERE subject_type = 'candidate'
          AND subject_id = %s
          AND predicate = 'declared_assets_total'
        """,
        (candidate_id,),
    )

    fact = _fetch_one(
        conn,
        """
        INSERT INTO facts (
            subject_type,
            subject_id,
            predicate,
            object_type,
            object_id,
            value_text,
            value_numeric,
            unit,
            effective_date,
            source_id,
            evidence_id,
            calculation_method,
            metadata
        )
        VALUES (%s, %s, %s, %s, NULL, NULL, %s, %s, %s, %s, NULL, %s, %s)
        RETURNING id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric, value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method, metadata, created_at
        """,
        (
            "candidate",
            candidate_id,
            "declared_assets_total",
            "candidate_assets",
            declared_assets_total,
            "BRL",
            None,
            source_id,
            "sum(candidate_assets.value)",
            Jsonb(
                {
                    "asset_count": asset_count,
                    "candidate_external_id": candidate_external_id,
                }
            ),
        ),
    )

    claim = _fetch_one(
        conn,
        """
        INSERT INTO claims (
            claim_type,
            statement,
            subject_type,
            subject_id,
            calculation_method,
            model_provider,
            model_name,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, NULL, NULL, %s)
        RETURNING id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider, model_name, metadata, created_at
        """,
        (
            "computed_fact",
            f"Patrimônio declarado: {format_brl(declared_assets_total)}",
            "candidate",
            candidate_id,
            "sum(candidate_assets.value)",
            Jsonb(
                {
                    "asset_count": asset_count,
                    "candidate_external_id": candidate_external_id,
                }
            ),
        ),
    )

    evidence_ids = [candidate_evidence_id, *asset_evidence_ids]
    for evidence_id in evidence_ids:
        conn.execute(
            """
            INSERT INTO claims_evidence (claim_id, evidence_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (claim["id"], evidence_id),
        )

    return {"fact": fact, "claim": claim}


def ingest_official_bundle(conn, bundle: Mapping[str, Any], *, source_checksum_value: str | None = None) -> dict[str, Any]:
    catalog = ensure_tse_catalog(conn, bundle)
    source = catalog["source"]
    candidate_dataset = catalog["candidate_dataset"]
    asset_dataset = catalog["asset_dataset"]
    candidate_row = bundle["candidate"]
    asset_rows = list(bundle["assets"])
    source_checksum_value = source_checksum_value or payload_hash(bundle)
    now = datetime.now(timezone.utc)
    candidate_source_updated_at = parse_br_datetime(candidate_row["DT_GERACAO"], candidate_row["HH_GERACAO"])
    asset_source_updated_at = parse_br_datetime(asset_rows[0]["DT_ULT_ATUAL_BEM_CANDIDATO"], asset_rows[0]["HH_ULT_ATUAL_BEM_CANDIDATO"])

    ingestion_run = _fetch_one(
        conn,
        """
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
        )
        VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, source_id, dataset_id, pipeline, run_type, started_at, finished_at, status, records_read, records_created, records_updated, records_unchanged, records_failed, source_checksum, error_summary, metadata, created_at
        """,
        (
            source["id"],
            candidate_dataset["id"],
            "connector-tse-v1",
            "fixture",
            now,
            "running",
            1 + len(asset_rows),
            0,
            0,
            0,
            0,
            source_checksum_value,
            Jsonb(
                {
                    "bundle_kind": "official_presidential_sample",
                    "asset_dataset_id": str(asset_dataset["id"]),
                    "candidate_external_id": candidate_row["SQ_CANDIDATO"],
                }
            ),
        ),
    )

    person = upsert_person(conn, source["id"], candidate_row)
    party = upsert_party(conn, candidate_row)
    election = upsert_election(conn, candidate_row)

    declared_assets_total = sum(
        (parse_decimal(asset_row["VR_BEM_CANDIDATO"]) or Decimal("0"))
        for asset_row in asset_rows
    )
    candidate = upsert_candidate(
        conn,
        source["id"],
        person["id"],
        election["id"],
        party["id"],
        candidate_row,
        declared_assets_total,
        candidate_source_updated_at,
        now,
    )

    candidate_raw_record = upsert_raw_record(
        conn,
        source["id"],
        candidate_dataset["id"],
        ingestion_run["id"],
        candidate_row["SQ_CANDIDATO"],
        candidate_row,
        candidate_source_updated_at,
        now,
        "normalized",
        {
            "bundle_kind": "candidate",
            "candidate_id": str(candidate["id"]),
        },
    )
    candidate_evidence = upsert_evidence(
        conn,
        source["id"],
        candidate_dataset["id"],
        candidate_raw_record["id"],
        candidate_row["SQ_CANDIDATO"],
        bundle["metadata"]["candidate_dataset_url"],
        "candidate",
        now,
        candidate_raw_record["payload_hash"],
        {
            "bundle_kind": "candidate",
            "candidate_external_id": candidate_row["SQ_CANDIDATO"],
        },
    )

    asset_records: list[dict[str, Any]] = []
    asset_evidences: list[dict[str, Any]] = []
    for asset_row in asset_rows:
        asset_external_id = f"{candidate_row['SQ_CANDIDATO']}:{asset_row['NR_ORDEM_BEM_CANDIDATO']}"
        raw_record = upsert_raw_record(
            conn,
            source["id"],
            asset_dataset["id"],
            ingestion_run["id"],
            asset_external_id,
            asset_row,
            parse_br_datetime(asset_row["DT_ULT_ATUAL_BEM_CANDIDATO"], asset_row["HH_ULT_ATUAL_BEM_CANDIDATO"]),
            now,
            "normalized",
            {
                "bundle_kind": "candidate_asset",
                "candidate_external_id": candidate_row["SQ_CANDIDATO"],
                "asset_order": asset_row["NR_ORDEM_BEM_CANDIDATO"],
            },
        )
        evidence = upsert_evidence(
            conn,
            source["id"],
            asset_dataset["id"],
            raw_record["id"],
            asset_external_id,
            bundle["metadata"]["asset_dataset_url"],
            "candidate_asset",
            now,
            raw_record["payload_hash"],
            {
                "bundle_kind": "candidate_asset",
                "candidate_external_id": candidate_row["SQ_CANDIDATO"],
                "asset_order": asset_row["NR_ORDEM_BEM_CANDIDATO"],
            },
        )
        asset = upsert_candidate_asset(
            conn,
            candidate["id"],
            source["id"],
            asset_row,
            parse_br_datetime(asset_row["DT_ULT_ATUAL_BEM_CANDIDATO"], asset_row["HH_ULT_ATUAL_BEM_CANDIDATO"]),
        )
        asset_records.append(asset)
        asset_evidences.append(evidence)

    conn.execute(
        """
        UPDATE candidates
        SET declared_assets_total = %s
        WHERE id = %s
        """,
        (declared_assets_total, candidate["id"]),
    )

    provenance = insert_claim_fact_and_links(
        conn,
        candidate["id"],
        source["id"],
        declared_assets_total,
        len(asset_records),
        candidate_evidence["id"],
        [evidence["id"] for evidence in asset_evidences],
        candidate_row["SQ_CANDIDATO"],
    )

    conn.execute(
        """
        UPDATE ingestion_runs
        SET
            finished_at = %s,
            status = 'success',
            records_read = %s,
            records_created = %s,
            records_updated = 0,
            records_unchanged = 0,
            records_failed = 0
        WHERE id = %s
        """,
        (
            datetime.now(timezone.utc),
            1 + len(asset_rows),
            1 + len(asset_rows),
            ingestion_run["id"],
        ),
    )

    return {
        "source": source,
        "candidate_dataset": candidate_dataset,
        "asset_dataset": asset_dataset,
        "ingestion_run_id": ingestion_run["id"],
        "person": person,
        "party": party,
        "election": election,
        "candidate": candidate,
        "candidate_raw_record": candidate_raw_record,
        "candidate_evidence": candidate_evidence,
        "asset_records": asset_records,
        "asset_evidences": asset_evidences,
        "fact": provenance["fact"],
        "claim": provenance["claim"],
        "declared_assets_total": declared_assets_total,
        "source_checksum": source_checksum_value,
    }


def fetch_candidate_summary(conn, candidate_external_id: str) -> dict[str, Any]:
    candidate = conn.execute(
        """
        SELECT
            c.id,
            c.person_id,
            c.election_id,
            c.party_id,
            c.source_id,
            c.external_id,
            c.ballot_number,
            c.position,
            c.application_status,
            c.result_status,
            c.occupation,
            c.education,
            c.declared_assets_total,
            c.source_updated_at,
            c.collected_at,
            c.raw_payload,
            p.canonical_name AS person_canonical_name,
            p.normalized_name AS person_normalized_name,
            p.birth_date AS person_birth_date,
            p.birth_place AS person_birth_place,
            p.metadata AS person_metadata,
            e.year AS election_year,
            e.round AS election_round,
            e.election_type AS election_type,
            e.scope AS election_scope,
            e.country AS election_country,
            e.state AS election_state,
            e.city AS election_city,
            e.election_date AS election_date,
            e.status AS election_status,
            e.metadata AS election_metadata,
            pa.external_id AS party_external_id,
            pa.name AS party_name,
            pa.acronym AS party_acronym,
            pa.number AS party_number,
            pa.official_url AS party_official_url,
            pa.logo_url AS party_logo_url,
            pa.metadata AS party_metadata,
            s.name AS source_name,
            s.slug AS source_slug,
            s.institution AS source_institution,
            s.description AS source_description,
            s.base_url AS source_base_url,
            s.documentation_url AS source_documentation_url,
            s.source_type AS source_type,
            s.scope AS source_scope,
            s.official AS source_official,
            s.update_frequency AS source_update_frequency,
            s.license AS source_license,
            s.metadata AS source_metadata,
            t.asset_count,
            t.declared_assets_total AS computed_assets_total,
            t.first_asset_source_updated_at,
            t.last_asset_source_updated_at,
            f.id AS fact_id,
            f.value_numeric AS fact_value_numeric,
            f.unit AS fact_unit,
            f.calculation_method AS fact_calculation_method,
            f.metadata AS fact_metadata,
            cl.id AS claim_id,
            cl.statement AS claim_statement,
            cl.calculation_method AS claim_calculation_method,
            cl.metadata AS claim_metadata
        FROM candidates AS c
        JOIN people AS p ON p.id = c.person_id
        JOIN elections AS e ON e.id = c.election_id
        LEFT JOIN parties AS pa ON pa.id = c.party_id
        JOIN sources AS s ON s.id = c.source_id
        LEFT JOIN candidate_asset_totals AS t ON t.candidate_id = c.id
        LEFT JOIN facts AS f
            ON f.subject_type = 'candidate'
           AND f.subject_id = c.id
           AND f.predicate = 'declared_assets_total'
        LEFT JOIN claims AS cl
            ON cl.subject_type = 'candidate'
           AND cl.subject_id = c.id
           AND cl.claim_type = 'computed_fact'
        WHERE c.external_id = %s
          AND s.slug = %s
        LIMIT 1
        """,
        (candidate_external_id, TSE_SOURCE_SLUG),
    ).fetchone()
    if candidate is None:
        raise KeyError(candidate_external_id)

    source = {
        "id": candidate["source_id"],
        "name": candidate["source_name"],
        "slug": candidate["source_slug"],
        "institution": candidate["source_institution"],
        "description": candidate["source_description"],
        "base_url": candidate["source_base_url"],
        "documentation_url": candidate["source_documentation_url"],
        "source_type": candidate["source_type"],
        "scope": candidate["source_scope"],
        "official": candidate["source_official"],
        "update_frequency": candidate["source_update_frequency"],
        "license": candidate["source_license"],
        "metadata": candidate["source_metadata"],
    }

    datasets = conn.execute(
        """
        SELECT id, source_id, name, slug, external_id, format, resource_url, scope, period_start, period_end, update_frequency, enabled, metadata, created_at, updated_at
        FROM datasets
        WHERE source_id = (SELECT id FROM sources WHERE slug = %s)
          AND slug IN (%s, %s)
        ORDER BY CASE WHEN slug = %s THEN 0 ELSE 1 END
        """,
        (TSE_SOURCE_SLUG, TSE_CANDIDATES_DATASET_SLUG, TSE_ASSETS_DATASET_SLUG, TSE_CANDIDATES_DATASET_SLUG),
    ).fetchall()

    candidate_dataset_id = None
    asset_dataset_id = None
    serialized_datasets: list[dict[str, Any]] = []
    for row in datasets:
        dataset = dict(row)
        serialized_datasets.append(dataset)
        if dataset["slug"] == TSE_CANDIDATES_DATASET_SLUG:
            candidate_dataset_id = dataset["id"]
        elif dataset["slug"] == TSE_ASSETS_DATASET_SLUG:
            asset_dataset_id = dataset["id"]

    candidate_raw_record = conn.execute(
        """
        SELECT rr.id, rr.source_id, rr.dataset_id, rr.ingestion_run_id, rr.external_id, rr.payload, rr.payload_hash, rr.source_updated_at, rr.collected_at, rr.processing_status, rr.metadata, rr.created_at
        FROM raw_records AS rr
        WHERE rr.source_id = %s
          AND rr.dataset_id = %s
          AND rr.external_id = %s
        LIMIT 1
        """,
        (candidate["source_id"], candidate_dataset_id, candidate_external_id),
    ).fetchone()

    candidate_evidence = conn.execute(
        """
        SELECT e.id, e.source_id, e.dataset_id, e.raw_record_id, e.external_id, e.source_url, e.page, e.section, e.collected_at, e.payload_hash, e.metadata, e.created_at
        FROM evidence AS e
        WHERE e.raw_record_id = %s
        LIMIT 1
        """,
        (candidate_raw_record["id"],),
    ).fetchone()

    asset_rows = conn.execute(
        """
        SELECT
            a.id,
            a.candidate_id,
            a.external_id,
            a.asset_type,
            a.description,
            a.value,
            a.currency,
            a.source_id,
            a.source_updated_at,
            a.raw_payload,
            a.created_at,
            rr.id AS raw_record_id,
            rr.dataset_id AS raw_dataset_id,
            rr.payload_hash AS raw_payload_hash,
            rr.source_updated_at AS raw_source_updated_at,
            rr.collected_at AS raw_collected_at,
            rr.processing_status AS raw_processing_status,
            rr.metadata AS raw_metadata,
            e.id AS evidence_id,
            e.source_url AS evidence_source_url,
            e.section AS evidence_section,
            e.collected_at AS evidence_collected_at,
            e.payload_hash AS evidence_payload_hash,
            e.metadata AS evidence_metadata
        FROM candidate_assets AS a
        JOIN raw_records AS rr
          ON rr.source_id = a.source_id
         AND rr.dataset_id = %s
         AND rr.external_id = %s || ':' || a.external_id
        LEFT JOIN evidence AS e
          ON e.raw_record_id = rr.id
        WHERE a.candidate_id = %s
        ORDER BY a.external_id::integer
        """,
        (asset_dataset_id, candidate["external_id"], candidate["id"]),
    ).fetchall()

    claim_evidence_rows = conn.execute(
        """
        SELECT
            ce.claim_id,
            e.id AS evidence_id,
            e.source_id,
            e.dataset_id,
            e.raw_record_id,
            e.external_id,
            e.source_url,
            e.section,
            e.collected_at,
            e.payload_hash,
            e.metadata,
            rr.dataset_id AS raw_dataset_id,
            rr.external_id AS raw_external_id,
            rr.processing_status AS raw_processing_status,
            rr.metadata AS raw_metadata
        FROM claims_evidence AS ce
        JOIN evidence AS e ON e.id = ce.evidence_id
        LEFT JOIN raw_records AS rr ON rr.id = e.raw_record_id
        WHERE ce.claim_id = %s
        ORDER BY e.external_id
        """,
        (candidate["claim_id"],),
    ).fetchall()

    declared_assets_total = candidate["computed_assets_total"] or Decimal("0")
    assets = []
    for row in asset_rows:
        assets.append(
            {
                "id": row["id"],
                "external_id": row["external_id"],
                "asset_type": row["asset_type"],
                "description": row["description"],
                "value": format_decimal(row["value"]),
                "value_brl": format_brl(row["value"]),
                "currency": row["currency"],
                "source_updated_at": format_datetime(row["source_updated_at"]),
                "raw_payload": row["raw_payload"],
                "provenance": {
                    "raw_record_id": row["raw_record_id"],
                    "raw_payload_hash": row["raw_payload_hash"],
                    "evidence_id": row["evidence_id"],
                    "evidence_source_url": row["evidence_source_url"],
                    "evidence_section": row["evidence_section"],
                },
            }
        )

    return {
        "source": source,
        "datasets": serialized_datasets,
        "person": {
            "id": candidate["person_id"],
            "canonical_name": candidate["person_canonical_name"],
            "normalized_name": candidate["person_normalized_name"],
            "birth_date": candidate["person_birth_date"].isoformat() if candidate["person_birth_date"] else None,
            "birth_place": candidate["person_birth_place"],
            "metadata": candidate["person_metadata"],
        },
        "party": {
            "id": candidate["party_id"],
            "external_id": candidate["party_external_id"],
            "name": candidate["party_name"],
            "acronym": candidate["party_acronym"],
            "number": candidate["party_number"],
            "official_url": candidate["party_official_url"],
            "logo_url": candidate["party_logo_url"],
            "metadata": candidate["party_metadata"],
        },
        "election": {
            "id": candidate["election_id"],
            "year": candidate["election_year"],
            "round": candidate["election_round"],
            "election_type": candidate["election_type"],
            "scope": candidate["election_scope"],
            "country": candidate["election_country"],
            "state": candidate["election_state"],
            "city": candidate["election_city"],
            "election_date": candidate["election_date"].isoformat() if candidate["election_date"] else None,
            "status": candidate["election_status"],
            "metadata": candidate["election_metadata"],
        },
        "candidate": {
            "id": candidate["id"],
            "external_id": candidate["external_id"],
            "ballot_number": candidate["ballot_number"],
            "position": candidate["position"],
            "application_status": candidate["application_status"],
            "result_status": candidate["result_status"],
            "occupation": candidate["occupation"],
            "education": candidate["education"],
            "declared_assets_total": format_decimal(candidate["declared_assets_total"]),
            "declared_assets_total_brl": format_brl(candidate["declared_assets_total"]),
            "source_updated_at": format_datetime(candidate["source_updated_at"]),
            "collected_at": format_datetime(candidate["collected_at"]),
            "raw_payload": candidate["raw_payload"],
        },
        "assets": assets,
        "declared_assets_total": {
            "value": format_decimal(declared_assets_total),
            "formatted": format_brl(declared_assets_total),
            "asset_count": candidate["asset_count"] or 0,
            "calculation_method": candidate["fact_calculation_method"] or candidate["claim_calculation_method"] or "sum(candidate_assets.value)",
        },
        "fact": {
            "id": candidate["fact_id"],
            "value_numeric": format_decimal(candidate["fact_value_numeric"]),
            "unit": candidate["fact_unit"],
            "calculation_method": candidate["fact_calculation_method"],
            "metadata": candidate["fact_metadata"],
        }
        if candidate["fact_id"] is not None
        else None,
        "claim": {
            "id": candidate["claim_id"],
            "statement": candidate["claim_statement"],
            "calculation_method": candidate["claim_calculation_method"],
            "metadata": candidate["claim_metadata"],
        }
        if candidate["claim_id"] is not None
        else None,
        "provenance": {
            "candidate_raw_record": {
                "id": candidate_raw_record["id"],
                "external_id": candidate_raw_record["external_id"],
                "payload_hash": candidate_raw_record["payload_hash"],
                "source_updated_at": format_datetime(candidate_raw_record["source_updated_at"]),
                "collected_at": format_datetime(candidate_raw_record["collected_at"]),
                "processing_status": candidate_raw_record["processing_status"],
                "dataset_id": candidate_raw_record["dataset_id"],
            },
            "candidate_evidence": {
                "id": candidate_evidence["id"],
                "external_id": candidate_evidence["external_id"],
                "source_url": candidate_evidence["source_url"],
                "section": candidate_evidence["section"],
                "payload_hash": candidate_evidence["payload_hash"],
            },
            "asset_evidence": [
                {
                    "id": row["evidence_id"],
                    "external_id": row["external_id"],
                    "source_url": row["evidence_source_url"],
                    "section": row["evidence_section"],
                    "payload_hash": row["evidence_payload_hash"],
                    "raw_record_id": row["raw_record_id"],
                    "raw_dataset_id": row["raw_dataset_id"],
                }
                for row in asset_rows
            ],
            "claim_evidence": [
                {
                    "claim_id": row["claim_id"],
                    "evidence_id": row["evidence_id"],
                    "external_id": row["external_id"],
                    "source_url": row["source_url"],
                    "section": row["section"],
                    "payload_hash": row["payload_hash"],
                    "raw_record_id": row["raw_record_id"],
                    "raw_dataset_id": row["raw_dataset_id"],
                    "raw_external_id": row["raw_external_id"],
                    "raw_processing_status": row["raw_processing_status"],
                }
                for row in claim_evidence_rows
            ],
        },
    }


def query_candidate_catalog_response(conn, limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    rows = conn.execute(
        """
        SELECT c.external_id
        FROM candidates AS c
        JOIN elections AS e ON e.id = c.election_id
        JOIN sources AS s ON s.id = c.source_id
        WHERE s.slug = %s
          AND e.year = 2026
          AND c.position = 'PRESIDENTE'
        ORDER BY c.collected_at DESC, c.external_id DESC
        LIMIT %s
        """,
        (TSE_SOURCE_SLUG, limit),
    ).fetchall()

    candidates: list[dict[str, Any]] = []
    for row in rows:
        try:
            candidates.append(fetch_candidate_summary(conn, row["external_id"]))
        except KeyError:
            continue

    return {
        "status": "ok",
        "count": len(candidates),
        "candidates": candidates,
    }


def ingest_bundle_from_path(conn, path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    bundle = load_fixture_bundle(path)
    return ingest_official_bundle(conn, bundle, source_checksum_value=payload_hash(bundle))
