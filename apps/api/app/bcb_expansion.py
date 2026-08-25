from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from psycopg.types.json import Jsonb

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "bcb" / "selic_2024.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "bcb" / "selic_2024.json"
BCB_SOURCE_SLUG = "bcb"
BCB_DATASET_SLUG = "selic-sgs-11-2024"
BCB_SERIES_EXTERNAL_ID = "bcb-sgs-11"
BCB_SERIES_CODE = 11


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%d/%m/%Y").date()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_bcb_decimal(value: str | Decimal | float | int | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def format_percent(value: Decimal) -> str:
    percent = (value * Decimal("100")).quantize(Decimal("0.0001"))
    return f"{percent:.4f}".replace(".", ",") + "%"


def _fetch_one(conn, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise RuntimeError("Expected row not found")
    return dict(row)


def _fetch_optional(conn, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return dict(row)


def upsert_claim_evidence(conn, claim_id: str, evidence_id: str) -> dict[str, Any]:
    existing = _fetch_optional(
        conn,
        """
        SELECT claim_id, evidence_id, created_at
        FROM claims_evidence
        WHERE claim_id = %s
          AND evidence_id = %s
        LIMIT 1
        """,
        (claim_id, evidence_id),
    )
    if existing is not None:
        if existing["evidence_id"] != evidence_id:
            existing = _fetch_one(
                conn,
                """
                UPDATE facts
                SET evidence_id = %s
                WHERE id = %s
                RETURNING id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric,
                          value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method,
                          metadata, created_at
                """,
                (evidence_id, existing["id"]),
            )
        return existing

    return _fetch_one(
        conn,
        """
        INSERT INTO claims_evidence (
            claim_id,
            evidence_id
        )
        VALUES (%s, %s)
        RETURNING claim_id, evidence_id, created_at
        """,
        (claim_id, evidence_id),
    )


def ensure_source(conn, source_payload: Mapping[str, Any]) -> dict[str, Any]:
    existing = _fetch_optional(
        conn,
        """
        SELECT id, name, slug, institution, description, base_url, documentation_url,
               source_type, scope, official, update_frequency, license, enabled, metadata,
               created_at, updated_at
        FROM sources
        WHERE slug = %s
        LIMIT 1
        """,
        (source_payload["slug"],),
    )
    if existing is not None:
        return existing

    metadata = dict(source_payload.get("metadata") or {})
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, name, slug, institution, description, base_url, documentation_url,
                  source_type, scope, official, update_frequency, license, enabled, metadata,
                  created_at, updated_at
        """,
        (
            source_payload["name"],
            source_payload["slug"],
            source_payload.get("institution"),
            source_payload.get("description"),
            source_payload.get("base_url"),
            source_payload.get("documentation_url"),
            source_payload.get("source_type", "official_registry"),
            source_payload.get("scope", "federal"),
            bool(source_payload.get("official", True)),
            source_payload.get("update_frequency", "daily"),
            source_payload.get("license", "open data"),
            bool(source_payload.get("enabled", True)),
            Jsonb(metadata),
        ),
    )


def ensure_dataset(conn, source_id: str, dataset_payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(dataset_payload.get("metadata") or {})
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            dataset_payload["name"],
            dataset_payload["slug"],
            dataset_payload["external_id"],
            dataset_payload.get("format", "json"),
            dataset_payload["resource_url"],
            dataset_payload.get("scope", "federal"),
            parse_iso_date(dataset_payload.get("period_start")),
            parse_iso_date(dataset_payload.get("period_end")),
            dataset_payload.get("update_frequency", "daily"),
            bool(dataset_payload.get("enabled", True)),
            Jsonb(metadata),
        ),
    )


def ensure_series(
    conn,
    source_id: str,
    dataset_id: str,
    series_payload: Mapping[str, Any],
) -> dict[str, Any]:
    metadata = dict(series_payload.get("metadata") or {})
    return _fetch_one(
        conn,
        """
        INSERT INTO economic_series (
            source_id,
            dataset_id,
            external_id,
            name,
            description,
            unit,
            frequency,
            series_code,
            start_date,
            end_date,
            active,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            dataset_id = EXCLUDED.dataset_id,
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            unit = EXCLUDED.unit,
            frequency = EXCLUDED.frequency,
            series_code = EXCLUDED.series_code,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            active = EXCLUDED.active,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING id, source_id, dataset_id, external_id, name, description, unit, frequency, series_code, start_date, end_date, active, metadata, created_at, updated_at
        """,
        (
            source_id,
            dataset_id,
            series_payload.get("external_id", BCB_SERIES_EXTERNAL_ID),
            series_payload["name"],
            series_payload.get("description"),
            series_payload.get("unit"),
            series_payload.get("frequency", "daily"),
            int(series_payload.get("series_code", BCB_SERIES_CODE)),
            parse_iso_date(series_payload.get("start_date")),
            parse_iso_date(series_payload.get("end_date")),
            bool(series_payload.get("active", True)),
            Jsonb(metadata),
        ),
    )


def ensure_ingestion_run(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    bundle: Mapping[str, Any],
    source_checksum_value: str | None,
) -> dict[str, Any]:
    existing = _fetch_optional(
        conn,
        """
        SELECT id, source_id, dataset_id, pipeline, run_type, started_at, finished_at, status,
               records_read, records_created, records_updated, records_unchanged, records_failed,
               source_checksum, error_summary, metadata, created_at
        FROM ingestion_runs
        WHERE source_id = %s
          AND dataset_id = %s
          AND pipeline = %s
          AND source_checksum = %s
        LIMIT 1
        """,
        (source_id, dataset_id, "connector-bcb-expansion", source_checksum_value),
    )
    if existing is not None:
        return existing

    started_at = parse_iso_datetime(bundle.get("ingestion_run", {}).get("started_at")) or datetime.now(timezone.utc)
    finished_at = parse_iso_datetime(bundle.get("ingestion_run", {}).get("finished_at")) or started_at
    metadata = dict(bundle.get("ingestion_run", {}).get("metadata") or {})
    return _fetch_one(
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
            error_summary,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, source_id, dataset_id, pipeline, run_type, started_at, finished_at, status,
                  records_read, records_created, records_updated, records_unchanged, records_failed,
                  source_checksum, error_summary, metadata, created_at
        """,
        (
            source_id,
            dataset_id,
            "connector-bcb-expansion",
            "full",
            started_at,
            finished_at,
            "success",
            len(bundle["series"]["observations"]),
            len(bundle["series"]["observations"]),
            0,
            0,
            0,
            source_checksum_value,
            None,
            Jsonb(metadata),
        ),
    )


def upsert_raw_record(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    ingestion_run_id: str,
    bundle: Mapping[str, Any],
    source_checksum_value: str | None,
) -> dict[str, Any]:
    raw_record_payload = bundle.get("raw_record") or {}
    external_id = raw_record_payload.get("external_id", f"{BCB_SERIES_EXTERNAL_ID}-2024-12")
    payload = {
        "series": bundle["series"],
        "observations": bundle["series"]["observations"],
    }
    metadata = dict(raw_record_payload.get("metadata") or {})
    source_updated_at = parse_iso_datetime(raw_record_payload.get("source_updated_at"))
    collected_at = parse_iso_datetime(raw_record_payload.get("collected_at")) or datetime.now(timezone.utc)
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
            Jsonb(payload),
            source_checksum_value or payload_hash(payload),
            source_updated_at,
            collected_at,
            "normalized",
            Jsonb(metadata),
        ),
    )


def upsert_evidence(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    raw_record_id: str,
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_payload = bundle.get("evidence") or {}
    metadata = dict(evidence_payload.get("metadata") or {})
    return _fetch_one(
        conn,
        """
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
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, dataset_id, external_id) DO UPDATE
        SET
            raw_record_id = EXCLUDED.raw_record_id,
            source_url = EXCLUDED.source_url,
            page = EXCLUDED.page,
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
            evidence_payload.get("external_id", f"{BCB_SERIES_EXTERNAL_ID}-evidence"),
            evidence_payload.get("source_url", bundle["dataset"]["resource_url"]),
            evidence_payload.get("page"),
            evidence_payload.get("section", "SGS Selic"),
            parse_iso_datetime(evidence_payload.get("collected_at")) or datetime.now(timezone.utc),
            evidence_payload.get("payload_hash", payload_hash(bundle)),
            Jsonb(metadata),
        ),
    )


def replace_observations(
    conn,
    *,
    economic_series_id: str,
    observations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    conn.execute(
        "DELETE FROM economic_observations WHERE economic_series_id = %s",
        (economic_series_id,),
    )
    inserted: list[dict[str, Any]] = []
    for observation in observations:
        inserted.append(
            _fetch_one(
                conn,
                """
                INSERT INTO economic_observations (
                    economic_series_id,
                    observation_date,
                    value,
                    source_updated_at,
                    collected_at,
                    raw_payload,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, economic_series_id, observation_date, value, source_updated_at, collected_at, raw_payload, metadata, created_at
                """,
                (
                    economic_series_id,
                    parse_iso_date(observation["data"]),
                    parse_bcb_decimal(observation["valor"]),
                    parse_iso_datetime(observation.get("source_updated_at")),
                    parse_iso_datetime(observation.get("collected_at")) or datetime.now(timezone.utc),
                    Jsonb(dict(observation)),
                    Jsonb(dict(observation.get("metadata") or {})),
                ),
            )
        )
    return inserted


def upsert_summary_fact(
    conn,
    *,
    source_id: str,
    evidence_id: str,
    economic_series_id: str,
    latest_observation: Mapping[str, Any],
    series_payload: Mapping[str, Any],
) -> dict[str, Any]:
    effective_date = latest_observation["observation_date"]
    existing = _fetch_optional(
        conn,
        """
        SELECT id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric,
               value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method,
               metadata, created_at
        FROM facts
        WHERE subject_type = %s
          AND subject_id = %s
          AND predicate = %s
          AND effective_date = %s
        LIMIT 1
        """,
        ("economic_series", economic_series_id, "selic_rate_end_of_2024", effective_date),
    )
    if existing is not None:
        return existing

    formatted_rate = format_percent(latest_observation["value"] or Decimal("0"))
    metadata = {
        "series_code": series_payload.get("series_code", BCB_SERIES_CODE),
        "raw_value": latest_observation["raw_payload"]["valor"],
        "observation_date": latest_observation["observation_date"].isoformat(),
    }
    return _fetch_one(
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
            value_boolean,
            value_date,
            unit,
            effective_date,
            source_id,
            evidence_id,
            calculation_method,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric,
                  value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method,
                  metadata, created_at
        """,
        (
            "economic_series",
            economic_series_id,
            "selic_rate_end_of_2024",
            "text",
            None,
            formatted_rate,
            None,
            None,
            effective_date,
            "%",
            effective_date,
            source_id,
            evidence_id,
            "latest_observation",
            Jsonb(metadata),
        ),
    )


def upsert_summary_claim(
    conn,
    *,
    economic_series_id: str,
    latest_observation: Mapping[str, Any],
    fact_id: str,
    series_payload: Mapping[str, Any],
) -> dict[str, Any]:
    effective_date = latest_observation["observation_date"]
    statement = f"A taxa Selic encerrou 2024 em {format_percent(latest_observation['value'] or Decimal('0'))}."
    existing = _fetch_optional(
        conn,
        """
        SELECT id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider,
               model_name, metadata, created_at
        FROM claims
        WHERE subject_type = %s
          AND subject_id = %s
          AND statement = %s
        LIMIT 1
        """,
        ("economic_series", economic_series_id, statement),
    )
    if existing is not None:
        return existing

    return _fetch_one(
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider, model_name, metadata, created_at
        """,
        (
            "official_fact",
            statement,
            "economic_series",
            economic_series_id,
            "latest_observation",
            "manual",
            "bcb-expansion",
            Jsonb(
                {
                    "fact_id": str(fact_id),
                    "effective_date": effective_date.isoformat() if effective_date else None,
                    "series_code": series_payload.get("series_code", BCB_SERIES_CODE),
                }
            ),
        ),
    )


def ingest_official_bundle(conn, bundle: Mapping[str, Any], *, source_checksum_value: str | None = None) -> dict[str, Any]:
    source = ensure_source(conn, bundle["source"])
    dataset = ensure_dataset(conn, source["id"], bundle["dataset"])
    series = ensure_series(conn, source["id"], dataset["id"], bundle["series"])
    ingestion_run = ensure_ingestion_run(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        bundle=bundle,
        source_checksum_value=source_checksum_value,
    )
    raw_record = upsert_raw_record(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        ingestion_run_id=ingestion_run["id"],
        bundle=bundle,
        source_checksum_value=source_checksum_value,
    )
    evidence = upsert_evidence(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        raw_record_id=raw_record["id"],
        bundle=bundle,
    )
    observations = replace_observations(
        conn,
        economic_series_id=series["id"],
        observations=bundle["series"]["observations"],
    )
    latest_observation = max(observations, key=lambda row: row["observation_date"])
    fact = upsert_summary_fact(
        conn,
        source_id=source["id"],
        evidence_id=evidence["id"],
        economic_series_id=series["id"],
        latest_observation=latest_observation,
        series_payload=bundle["series"],
    )
    claim = upsert_summary_claim(
        conn,
        economic_series_id=series["id"],
        latest_observation=latest_observation,
        fact_id=fact["id"],
        series_payload=bundle["series"],
    )
    claim_evidence = upsert_claim_evidence(conn, claim["id"], evidence["id"])
    return {
        "source": source,
        "dataset": dataset,
        "series": series,
        "ingestion_run": ingestion_run,
        "raw_record": raw_record,
        "evidence": evidence,
        "observations": observations,
        "latest_observation": latest_observation,
        "fact": fact,
        "claim": claim,
        "claim_evidence": claim_evidence,
    }


def fetch_series_summary(conn, series_external_id: str = BCB_SERIES_EXTERNAL_ID) -> dict[str, Any]:
    series = _fetch_optional(
        conn,
        """
        SELECT es.id, es.source_id, es.dataset_id, es.external_id, es.name, es.description, es.unit,
               es.frequency, es.series_code, es.start_date, es.end_date, es.active, es.metadata,
               es.created_at, es.updated_at,
               s.name AS source_name, s.slug AS source_slug, s.base_url AS source_url,
               d.name AS dataset_name, d.slug AS dataset_slug, d.resource_url AS dataset_url
        FROM economic_series AS es
        JOIN sources AS s ON s.id = es.source_id
        JOIN datasets AS d ON d.id = es.dataset_id
        WHERE es.external_id = %s
        LIMIT 1
        """,
        (series_external_id,),
    )
    if series is None:
        raise KeyError(series_external_id)

    observations = conn.execute(
        """
        SELECT id, economic_series_id, observation_date, value, source_updated_at, collected_at, raw_payload, metadata, created_at
        FROM economic_observations
        WHERE economic_series_id = %s
        ORDER BY observation_date
        """,
        (series["id"],),
    ).fetchall()
    observations = [dict(row) for row in observations]

    fact = _fetch_optional(
        conn,
        """
        SELECT id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric,
               value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method,
               metadata, created_at
        FROM facts
        WHERE subject_type = %s
          AND subject_id = %s
          AND predicate = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        ("economic_series", series["id"], "selic_rate_end_of_2024"),
    )
    claim = _fetch_optional(
        conn,
        """
        SELECT id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider,
               model_name, metadata, created_at
        FROM claims
        WHERE subject_type = %s
          AND subject_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        ("economic_series", series["id"]),
    )
    raw_record = _fetch_optional(
        conn,
        """
        SELECT id, source_id, dataset_id, ingestion_run_id, external_id, payload, payload_hash,
               source_updated_at, collected_at, processing_status, metadata, created_at
        FROM raw_records
        WHERE source_id = %s
          AND dataset_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (series["source_id"], series["dataset_id"]),
    )
    evidence = _fetch_optional(
        conn,
        """
        SELECT id, source_id, dataset_id, raw_record_id, external_id, source_url, page, section,
               collected_at, payload_hash, metadata, created_at
        FROM evidence
        WHERE source_id = %s
          AND dataset_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (series["source_id"], series["dataset_id"]),
    )
    return {
        "source": {
            "id": series["source_id"],
            "name": series["source_name"],
            "slug": series["source_slug"],
            "base_url": series["source_url"],
        },
        "dataset": {
            "id": series["dataset_id"],
            "name": series["dataset_name"],
            "slug": series["dataset_slug"],
            "resource_url": series["dataset_url"],
        },
        "series": series,
        "observations": observations,
        "fact": fact,
        "claim": claim,
        "raw_record": raw_record,
        "evidence": evidence,
        "latest_value_formatted": format_percent(observations[-1]["value"]),
    }


def query_observation_response(
    conn,
    observation_date: str,
    *,
    series_external_id: str = BCB_SERIES_EXTERNAL_ID,
) -> dict[str, Any]:
    summary = fetch_series_summary(conn, series_external_id)
    target_date = parse_iso_date(observation_date)
    if target_date is None:
        raise ValueError("observation_date is required")

    matches = [observation for observation in summary["observations"] if observation["observation_date"] == target_date]
    response = {
        "series": summary["series"],
        "source": summary["source"],
        "dataset": summary["dataset"],
        "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
        "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
        "observation_date": target_date.isoformat(),
    }
    if not matches:
        return {
            **response,
            "status": "no_evidence",
            "value": None,
            "value_formatted": None,
            "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
            "citations": [],
        }

    observation = matches[0]
    return {
        **response,
        "status": "ok",
        "value": observation["value"],
        "value_formatted": format_percent(observation["value"]),
        "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
        "citations": [
            {
                "observation_date": observation["observation_date"],
                "value": observation["value"],
                "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
                "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
            }
        ],
    }
