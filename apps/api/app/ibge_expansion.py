from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from psycopg.types.json import Jsonb

from app.bcb_expansion import (
    _fetch_one,
    _fetch_optional,
    ensure_dataset,
    ensure_source,
    parse_bcb_decimal,
    parse_iso_date,
    parse_iso_datetime,
    payload_hash,
    replace_observations,
    upsert_evidence,
    upsert_raw_record,
    upsert_claim_evidence,
)

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "ibge" / "ipca_2024.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "ibge" / "ipca_2024.json"
IBGE_SOURCE_SLUG = "ibge"
IBGE_DATASET_SLUG = "ipca-1737-2024"
IBGE_SERIES_EXTERNAL_ID = "ibge-ipca-1737-63-brasil"
IBGE_SERIES_CODE = 1737
IBGE_VARIABLE_CODE = 63


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def format_percent_value(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    return f"{quantized:.2f}".replace(".", ",") + "%"


def parse_month_period(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)


def ensure_series(conn, source_id: str, dataset_id: str, series_payload: Mapping[str, Any]) -> dict[str, Any]:
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
            series_payload.get("external_id", IBGE_SERIES_EXTERNAL_ID),
            series_payload["name"],
            series_payload.get("description"),
            series_payload.get("unit", "%"),
            series_payload.get("frequency", "monthly"),
            int(series_payload.get("series_code", IBGE_SERIES_CODE)),
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
        (source_id, dataset_id, "connector-ibge-expansion", source_checksum_value),
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
            "connector-ibge-expansion",
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
        ("economic_series", economic_series_id, "ipca_monthly_variation_december_2024", effective_date),
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

    formatted_rate = format_percent_value(latest_observation["value"] or Decimal("0"))
    metadata = {
        "series_code": series_payload.get("series_code", IBGE_SERIES_CODE),
        "variable_code": series_payload.get("variable_code", IBGE_VARIABLE_CODE),
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
            "ipca_monthly_variation_december_2024",
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
    statement = f"A variação mensal do IPCA em dezembro de 2024 foi de {format_percent_value(latest_observation['value'] or Decimal('0'))}."
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
            "ibge-expansion",
            Jsonb(
                {
                    "fact_id": str(fact_id),
                    "effective_date": effective_date.isoformat() if effective_date else None,
                    "series_code": series_payload.get("series_code", IBGE_SERIES_CODE),
                    "variable_code": series_payload.get("variable_code", IBGE_VARIABLE_CODE),
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


def fetch_series_summary(conn, series_external_id: str = IBGE_SERIES_EXTERNAL_ID) -> dict[str, Any]:
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
        ("economic_series", series["id"], "ipca_monthly_variation_december_2024"),
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
        "latest_value_formatted": format_percent_value(observations[-1]["value"]),
    }


def query_observation_response(
    conn,
    period: str,
    *,
    series_external_id: str = IBGE_SERIES_EXTERNAL_ID,
) -> dict[str, Any]:
    summary = fetch_series_summary(conn, series_external_id)
    target_date = parse_month_period(period)
    if target_date is None:
        raise ValueError("period is required")

    matches = [observation for observation in summary["observations"] if observation["observation_date"] == target_date]
    response = {
        "series": summary["series"],
        "source": summary["source"],
        "dataset": summary["dataset"],
        "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
        "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
        "observation_period": target_date.strftime("%Y-%m"),
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
        "value_formatted": format_percent_value(observation["value"]),
        "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
        "citations": [
            {
                "observation_date": observation["observation_date"].isoformat(),
                "value": observation["value"],
                "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
                "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
            }
        ],
    }
