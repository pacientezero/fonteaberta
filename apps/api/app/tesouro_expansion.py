from __future__ import annotations

import hashlib
import json
import re
import uuid
from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote

from psycopg.types.json import Jsonb

from app.bcb_expansion import (
    _fetch_one,
    _fetch_optional,
    ensure_dataset,
    ensure_source,
    parse_iso_datetime,
    payload_hash,
    upsert_claim_evidence,
)

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "tesouro" / "rreo_sp_2024_p06_anexo01.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "tesouro" / "rreo_sp_2024_p06_anexo01.json"

TESOURO_SOURCE_SLUG = "tesouro"
TESOURO_INSTITUTION = "Tesouro Nacional"
TESOURO_PORTAL_URL = "https://siconfi.tesouro.gov.br/"
TESOURO_API_DOCS_URL = "https://apidatalake.tesouro.gov.br/docs/siconfi/"
TESOURO_API_BASE_URL = "https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/"

TESOURO_ENTITY_CODE = 3550308
TESOURO_EXERCISE = 2024
TESOURO_PERIOD = 6
TESOURO_ANEXO = "RREO-Anexo 01"
TESOURO_DEMONSTRATIVE = "RREO"
TESOURO_PERIODICITY = "B"
TESOURO_DATASET_SLUG = "rreo-3550308-2024-p06-anexo01"
TESOURO_DATASET_EXTERNAL_ID = "siconfi-rreo-sp-3550308-2024-p06-anexo01"
TESOURO_REPORT_SUBJECT_TYPE = "siconfi_rreo_report"
TESOURO_REPORT_SUMMARY_PREDICATE = "rreo_bimonthly_expense_headline"
TESOURO_HEADLINE_ACCOUNT_CODE = "DespesasExcetoIntraOrcamentarias"
TESOURO_HEADLINE_COLUMN_LABEL = "DESPESAS PAGAS ATÉ O BIMESTRE (j)"

ROW_TEXT_FIELDS = [
    "periodicity",
    "demonstrative",
    "institution",
    "uf",
    "annex",
    "sphere",
    "label",
    "column_label",
    "account_code",
    "account_name",
]

ROW_SIGNATURE_FIELDS = [
    "exercise",
    "period",
    "periodicity",
    "demonstrative",
    "institution",
    "entity_code",
    "uf",
    "annex",
    "sphere",
    "label",
    "column_label",
    "account_code",
    "account_name",
]

MONTH_NAMES_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "marco",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def slugify_text(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_brazilian_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        return Decimal("0")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    return Decimal(text)


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def format_brl_amount(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    sign = "-" if quantized < 0 else ""
    absolute = abs(quantized)
    integer_part, decimal_part = f"{absolute:.2f}".split(".")
    grouped = f"{int(integer_part):,}".replace(",", ".")
    return f"{sign}R$ {grouped},{decimal_part}"


def report_period_bounds(exercise: int, period: int) -> tuple[date, date]:
    start_month = period * 2 - 1
    end_month = period * 2
    start_date = date(exercise, start_month, 1)
    end_date = date(exercise, end_month, monthrange(exercise, end_month)[1])
    return start_date, end_date


def format_period_label(exercise: int, period: int) -> str:
    return f"{period}º bimestre de {exercise}"


def build_source_payload() -> dict[str, Any]:
    return {
        "name": "Tesouro Nacional / SICONFI",
        "slug": TESOURO_SOURCE_SLUG,
        "institution": TESOURO_INSTITUTION,
        "description": "Portal oficial de dados abertos do Tesouro Nacional / SICONFI",
        "base_url": TESOURO_PORTAL_URL,
        "documentation_url": TESOURO_API_DOCS_URL,
        "source_type": "official_registry",
        "scope": "federal",
        "official": True,
        "update_frequency": "bimonthly",
        "license": "open data",
        "enabled": True,
        "metadata": {
            "portal_url": TESOURO_PORTAL_URL,
            "api_docs_url": TESOURO_API_DOCS_URL,
            "api_base_url": TESOURO_API_BASE_URL,
        },
    }


def build_report_url(entity_code: int, exercise: int, period: int, annex: str) -> str:
    return (
        "https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/rreo"
        f"?an_exercicio={exercise}"
        f"&nr_periodo={period}"
        "&co_tipo_demonstrativo=RREO"
        f"&id_ente={entity_code}"
        f"&no_anexo={quote(annex)}"
    )


def build_dataset_payload(bundle: Mapping[str, Any], entity_code: int, exercise: int, period: int, annex: str) -> dict[str, Any]:
    first_row = bundle["items"][0]
    start_date, end_date = report_period_bounds(exercise, period)
    entity_name = normalize_text(first_row.get("instituicao")) or "Tesouro"
    return {
        "name": f"RREO {annex} - {entity_name} {exercise} {format_period_label(exercise, period)}",
        "slug": TESOURO_DATASET_SLUG,
        "external_id": TESOURO_DATASET_EXTERNAL_ID,
        "format": "json",
        "resource_url": build_report_url(entity_code, exercise, period, annex),
        "scope": "municipal",
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "update_frequency": "bimonthly",
        "enabled": True,
        "metadata": {
            "api_path": "/rreo",
            "exercise": exercise,
            "period": period,
            "entity_code": entity_code,
            "entity_name": entity_name,
            "report_type": TESOURO_DEMONSTRATIVE,
            "annex": annex,
            "period_label": format_period_label(exercise, period),
            "entity_slug": "sao-paulo",
        },
    }


def row_signature(row: Mapping[str, Any]) -> dict[str, str]:
    signature: dict[str, str] = {}
    for field in ROW_SIGNATURE_FIELDS:
        value = row.get(field)
        if isinstance(value, date):
            signature[field] = value.isoformat()
        elif value is None:
            signature[field] = ""
        else:
            signature[field] = str(value)
    return signature


def row_external_id(row: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(row_signature(row))).hexdigest()
    return f"tesouro-rreo-{digest[:24]}"


def normalize_rreo_row(
    row: Mapping[str, Any],
    *,
    default_source_updated_at: datetime | None = None,
    default_collected_at: datetime | None = None,
) -> dict[str, Any]:
    payload = dict(row)
    normalized: dict[str, Any] = {
        "exercise": int(payload["exercicio"]),
        "period": int(payload["periodo"]),
        "periodicity": normalize_text(payload.get("periodicidade")) or TESOURO_PERIODICITY,
        "demonstrative": normalize_text(payload.get("demonstrativo")) or TESOURO_DEMONSTRATIVE,
        "institution": normalize_text(payload.get("instituicao")) or TESOURO_INSTITUTION,
        "entity_code": int(payload["cod_ibge"]),
        "uf": normalize_text(payload.get("uf")),
        "population": int(payload["populacao"]) if payload.get("populacao") is not None else None,
        "annex": normalize_text(payload.get("anexo")) or TESOURO_ANEXO,
        "sphere": normalize_text(payload.get("esfera")) or "M",
        "label": normalize_text(payload.get("rotulo")) or "Padrão",
        "column_label": normalize_text(payload.get("coluna")) or "",
        "account_code": normalize_text(payload.get("cod_conta")) or "",
        "account_name": normalize_text(payload.get("conta")) or "",
        "value_numeric": parse_brazilian_decimal(payload.get("valor")),
        "raw_payload": payload,
        "metadata": dict(payload.get("metadata") or {}),
        "source_updated_at": parse_iso_datetime(payload.get("source_updated_at")) or default_source_updated_at,
        "collected_at": parse_iso_datetime(payload.get("collected_at")) or default_collected_at or datetime.now(timezone.utc),
    }
    normalized["external_id"] = normalize_text(payload.get("external_id")) or row_external_id(normalized)
    return normalized


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
        (source_id, dataset_id, "connector-tesouro-expansion", source_checksum_value),
    )
    if existing is not None:
        return existing

    started_at = parse_iso_datetime(bundle.get("raw_record", {}).get("collected_at")) or datetime.now(timezone.utc)
    finished_at = started_at
    metadata = {
        "source": "apidatalake.tesouro.gov.br",
        "retrieval_intent": "official_tesouro_rreo_demo",
    }
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
            "connector-tesouro-expansion",
            "full",
            started_at,
            finished_at,
            "success",
            len(bundle["items"]),
            len(bundle["items"]),
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
    metadata = dict(raw_record_payload.get("metadata") or {})
    collected_at = parse_iso_datetime(raw_record_payload.get("collected_at")) or datetime.now(timezone.utc)
    source_updated_at = parse_iso_datetime(raw_record_payload.get("source_updated_at"))
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
            raw_record_payload.get("external_id", TESOURO_DATASET_EXTERNAL_ID),
            Jsonb(bundle),
            source_checksum_value or payload_hash(bundle),
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
    entity_code: int,
    exercise: int,
    period: int,
    annex: str,
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    source_url = build_report_url(entity_code, exercise, period, annex)
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
            evidence_payload.get("external_id", f"{TESOURO_DATASET_EXTERNAL_ID}-evidence"),
            evidence_payload.get("source_url", source_url),
            evidence_payload.get("page"),
            evidence_payload.get("section", TESOURO_ANEXO),
            parse_iso_datetime(evidence_payload.get("collected_at")) or datetime.now(timezone.utc),
            evidence_payload.get("payload_hash", payload_hash(bundle)),
            Jsonb(metadata),
        ),
    )


def upsert_rows(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    bundle: Mapping[str, Any],
    default_collected_at: datetime | None = None,
    default_source_updated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    inserted: list[dict[str, Any]] = []
    insert_sql = """
        INSERT INTO rreo_rows (
            source_id,
            dataset_id,
            external_id,
            exercise,
            period,
            periodicity,
            demonstrative,
            institution,
            entity_code,
            uf,
            population,
            annex,
            sphere,
            label,
            column_label,
            account_code,
            account_name,
            value_numeric,
            source_updated_at,
            collected_at,
            raw_payload,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            dataset_id = EXCLUDED.dataset_id,
            exercise = EXCLUDED.exercise,
            period = EXCLUDED.period,
            periodicity = EXCLUDED.periodicity,
            demonstrative = EXCLUDED.demonstrative,
            institution = EXCLUDED.institution,
            entity_code = EXCLUDED.entity_code,
            uf = EXCLUDED.uf,
            population = EXCLUDED.population,
            annex = EXCLUDED.annex,
            sphere = EXCLUDED.sphere,
            label = EXCLUDED.label,
            column_label = EXCLUDED.column_label,
            account_code = EXCLUDED.account_code,
            account_name = EXCLUDED.account_name,
            value_numeric = EXCLUDED.value_numeric,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            raw_payload = EXCLUDED.raw_payload,
            metadata = EXCLUDED.metadata
        RETURNING id, source_id, dataset_id, external_id, exercise, period, periodicity, demonstrative,
                  institution, entity_code, uf, population, annex, sphere, label, column_label, account_code,
                  account_name, value_numeric, source_updated_at, collected_at, raw_payload, metadata,
                  created_at, updated_at
    """
    for index, raw_row in enumerate(bundle["items"], start=1):
        normalized = normalize_rreo_row(
            raw_row,
            default_source_updated_at=default_source_updated_at,
            default_collected_at=default_collected_at,
        )
        params = (
            source_id,
            dataset_id,
            normalized["external_id"],
            normalized["exercise"],
            normalized["period"],
            normalized["periodicity"],
            normalized["demonstrative"],
            normalized["institution"],
            normalized["entity_code"],
            normalized["uf"],
            normalized["population"],
            normalized["annex"],
            normalized["sphere"],
            normalized["label"],
            normalized["column_label"],
            normalized["account_code"],
            normalized["account_name"],
            normalized["value_numeric"],
            normalized["source_updated_at"],
            normalized["collected_at"],
            Jsonb(normalized["raw_payload"]),
            Jsonb({**normalized["metadata"], "line_index": index}),
        )
        inserted.append(_fetch_one(conn, insert_sql, params))
    return inserted


def select_headline_row(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    for row in rows:
        if row["account_code"] == TESOURO_HEADLINE_ACCOUNT_CODE and row["column_label"] == TESOURO_HEADLINE_COLUMN_LABEL:
            return row
    for row in rows:
        if row["account_code"] == TESOURO_HEADLINE_ACCOUNT_CODE:
            return row
    return rows[0]


def summary_statement(headline_row: Mapping[str, Any], *, exercise: int, period: int, annex: str) -> str:
    return (
        f"No {annex} de São Paulo no {format_period_label(exercise, period)}, "
        f"as despesas pagas até o bimestre totalizaram {format_brl_amount(headline_row['value_numeric'])}."
    )


def report_subject_id(entity_code: int, exercise: int, period: int, annex: str) -> uuid.UUID:
    annex_slug = slugify_text(annex)
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"fonteaberta:siconfi-rreo:{entity_code}:{exercise}:{period}:{annex_slug}",
    )


def upsert_summary_fact(
    conn,
    *,
    source_id: str,
    evidence_id: str,
    entity_code: int,
    exercise: int,
    period: int,
    annex: str,
    headline_row: Mapping[str, Any],
) -> dict[str, Any]:
    subject_id = report_subject_id(entity_code, exercise, period, annex)
    statement = summary_statement(headline_row, exercise=exercise, period=period, annex=annex)
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
        LIMIT 1
        """,
        (TESOURO_REPORT_SUBJECT_TYPE, str(subject_id), TESOURO_REPORT_SUMMARY_PREDICATE),
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

    period_end = report_period_bounds(exercise, period)[1]
    metadata = {
        "entity_code": entity_code,
        "exercise": exercise,
        "period": period,
        "annex": annex,
        "headline_external_id": headline_row["external_id"],
        "headline_account_code": headline_row["account_code"],
        "headline_column_label": headline_row["column_label"],
        "headline_value_numeric": str(headline_row["value_numeric"]),
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
            TESOURO_REPORT_SUBJECT_TYPE,
            str(subject_id),
            TESOURO_REPORT_SUMMARY_PREDICATE,
            "text",
            None,
            statement,
            headline_row["value_numeric"],
            None,
            period_end,
            "BRL",
            period_end,
            source_id,
            evidence_id,
            "headline_row",
            Jsonb(metadata),
        ),
    )


def upsert_summary_claim(
    conn,
    *,
    entity_code: int,
    exercise: int,
    period: int,
    annex: str,
    fact_id: str,
    headline_row: Mapping[str, Any],
) -> dict[str, Any]:
    subject_id = report_subject_id(entity_code, exercise, period, annex)
    statement = summary_statement(headline_row, exercise=exercise, period=period, annex=annex)
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
        (TESOURO_REPORT_SUBJECT_TYPE, str(subject_id), statement),
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
            TESOURO_REPORT_SUBJECT_TYPE,
            str(subject_id),
            "headline_row",
            "manual",
            "tesouro-expansion",
            Jsonb(
                {
                    "fact_id": str(fact_id),
                    "entity_code": entity_code,
                    "exercise": exercise,
                    "period": period,
                    "annex": annex,
                    "headline_external_id": headline_row["external_id"],
                }
            ),
        ),
    )


def ingest_official_bundle(
    conn,
    bundle: Mapping[str, Any],
    *,
    entity_code: int = TESOURO_ENTITY_CODE,
    exercise: int = TESOURO_EXERCISE,
    period: int = TESOURO_PERIOD,
    annex: str = TESOURO_ANEXO,
    source_checksum_value: str | None = None,
) -> dict[str, Any]:
    source = ensure_source(conn, build_source_payload())
    dataset_payload = build_dataset_payload(bundle, entity_code, exercise, period, annex)
    dataset = ensure_dataset(conn, source["id"], dataset_payload)
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
        entity_code=entity_code,
        exercise=exercise,
        period=period,
        annex=annex,
        bundle=bundle,
    )
    rows = upsert_rows(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        bundle=bundle,
        default_collected_at=parse_iso_datetime(bundle.get("raw_record", {}).get("collected_at")),
        default_source_updated_at=parse_iso_datetime(bundle.get("raw_record", {}).get("source_updated_at")),
    )
    headline_row = select_headline_row(rows)
    fact = upsert_summary_fact(
        conn,
        source_id=source["id"],
        evidence_id=evidence["id"],
        entity_code=entity_code,
        exercise=exercise,
        period=period,
        annex=annex,
        headline_row=headline_row,
    )
    claim = upsert_summary_claim(
        conn,
        entity_code=entity_code,
        exercise=exercise,
        period=period,
        annex=annex,
        fact_id=fact["id"],
        headline_row=headline_row,
    )
    claim_evidence = upsert_claim_evidence(conn, claim["id"], evidence["id"])
    return {
        "source": source,
        "dataset": dataset,
        "ingestion_run": ingestion_run,
        "raw_record": raw_record,
        "evidence": evidence,
        "rows": rows,
        "headline_row": headline_row,
        "fact": fact,
        "claim": claim,
        "claim_evidence": claim_evidence,
    }


def fetch_rreo_summary(
    conn,
    entity_code: int = TESOURO_ENTITY_CODE,
    exercise: int = TESOURO_EXERCISE,
    period: int = TESOURO_PERIOD,
    annex: str = TESOURO_ANEXO,
) -> dict[str, Any]:
    rows = _fetch_rows(
        conn,
        """
        SELECT rr.id, rr.source_id, rr.dataset_id, rr.external_id, rr.exercise, rr.period, rr.periodicity,
               rr.demonstrative, rr.institution, rr.entity_code, rr.uf, rr.population, rr.annex, rr.sphere,
               rr.label, rr.column_label, rr.account_code, rr.account_name, rr.value_numeric,
               rr.source_updated_at, rr.collected_at, rr.raw_payload, rr.metadata, rr.created_at, rr.updated_at,
               s.name AS source_name, s.slug AS source_slug, s.base_url AS source_url,
               d.name AS dataset_name, d.slug AS dataset_slug, d.resource_url AS dataset_url
        FROM rreo_rows AS rr
        JOIN sources AS s ON s.id = rr.source_id
        JOIN datasets AS d ON d.id = rr.dataset_id
        WHERE rr.entity_code = %s
          AND rr.exercise = %s
          AND rr.period = %s
          AND rr.annex = %s
        ORDER BY rr.created_at ASC
        """,
        (entity_code, exercise, period, annex),
    )
    if not rows:
        raise KeyError(f"{entity_code}:{exercise}:{period}:{annex}")

    headline_row = select_headline_row(rows)
    source_slug = rows[0]["source_slug"]
    dataset_slug = rows[0]["dataset_slug"]
    subject_id = report_subject_id(entity_code, exercise, period, annex)
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
        LIMIT 1
        """,
        (TESOURO_REPORT_SUBJECT_TYPE, str(subject_id), TESOURO_REPORT_SUMMARY_PREDICATE),
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
        (TESOURO_REPORT_SUBJECT_TYPE, str(subject_id)),
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
        (rows[0]["source_id"], rows[0]["dataset_id"]),
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
        (rows[0]["source_id"], rows[0]["dataset_id"]),
    )
    return {
        "source": {
            "id": rows[0]["source_id"],
            "name": rows[0]["source_name"],
            "slug": source_slug,
            "base_url": rows[0]["source_url"],
        },
        "dataset": {
            "id": rows[0]["dataset_id"],
            "name": rows[0]["dataset_name"],
            "slug": dataset_slug,
            "resource_url": rows[0]["dataset_url"],
        },
        "report": {
            "entity_code": entity_code,
            "exercise": exercise,
            "period": period,
            "annex": annex,
            "period_label": format_period_label(exercise, period),
        },
        "rows": rows,
        "row_count": len(rows),
        "headline_row": headline_row,
        "headline_value_formatted": format_brl_amount(headline_row["value_numeric"]),
        "fact": fact,
        "claim": claim,
        "raw_record": raw_record,
        "evidence": evidence,
    }


def _fetch_rows(conn, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def query_rreo_response(
    conn,
    entity_code: int = TESOURO_ENTITY_CODE,
    exercise: int = TESOURO_EXERCISE,
    period: int = TESOURO_PERIOD,
    annex: str = TESOURO_ANEXO,
) -> dict[str, Any]:
    try:
        summary = fetch_rreo_summary(conn, entity_code, exercise, period, annex)
    except KeyError:
        return {
            "source": None,
            "dataset": None,
            "report": {
                "entity_code": entity_code,
                "exercise": exercise,
                "period": period,
                "annex": annex,
                "period_label": format_period_label(exercise, period),
            },
            "collection_timestamp": None,
            "payload_hash": None,
            "status": "no_evidence",
            "row_count": 0,
            "headline": None,
            "source_url": None,
            "citations": [],
        }

    response = {
        "source": summary["source"],
        "dataset": summary["dataset"],
        "report": summary["report"],
        "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
        "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
        "row_count": summary["row_count"],
        "headline": {
            "external_id": summary["headline_row"]["external_id"],
            "account_code": summary["headline_row"]["account_code"],
            "account_name": summary["headline_row"]["account_name"],
            "column_label": summary["headline_row"]["column_label"],
            "value": summary["headline_row"]["value_numeric"],
            "value_formatted": summary["headline_value_formatted"],
        },
    }
    if summary["evidence"] is None:
        return {
            **response,
            "status": "no_evidence",
            "source_url": None,
            "citations": [],
        }

    return {
        **response,
        "status": "ok",
        "source_url": summary["evidence"]["source_url"],
        "citations": [
            {
                "entity_code": entity_code,
                "exercise": exercise,
                "period": period,
                "annex": annex,
                "source_url": summary["evidence"]["source_url"],
                "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
            }
        ],
    }


def query_rreo_row_response(
    conn,
    entity_code: int,
    exercise: int,
    period: int,
    external_id: str,
    annex: str = TESOURO_ANEXO,
) -> dict[str, Any]:
    row = _fetch_optional(
        conn,
        """
        SELECT rr.id, rr.source_id, rr.dataset_id, rr.external_id, rr.exercise, rr.period, rr.periodicity,
               rr.demonstrative, rr.institution, rr.entity_code, rr.uf, rr.population, rr.annex, rr.sphere,
               rr.label, rr.column_label, rr.account_code, rr.account_name, rr.value_numeric,
               rr.source_updated_at, rr.collected_at, rr.raw_payload, rr.metadata, rr.created_at, rr.updated_at
        FROM rreo_rows AS rr
        WHERE rr.entity_code = %s
          AND rr.exercise = %s
          AND rr.period = %s
          AND rr.annex = %s
          AND rr.external_id = %s
        LIMIT 1
        """,
        (entity_code, exercise, period, annex, external_id),
    )
    try:
        summary = fetch_rreo_summary(conn, entity_code, exercise, period, annex)
    except KeyError:
        summary = None

    if row is None:
        return {
            "source": summary["source"] if summary else None,
            "dataset": summary["dataset"] if summary else None,
            "report": summary["report"] if summary else {
                "entity_code": entity_code,
                "exercise": exercise,
                "period": period,
                "annex": annex,
                "period_label": format_period_label(exercise, period),
            },
            "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary and summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
            "payload_hash": summary["raw_record"]["payload_hash"] if summary and summary["raw_record"] else None,
            "status": "no_evidence",
            "row": None,
            "value": None,
            "value_formatted": None,
            "source_url": summary["evidence"]["source_url"] if summary and summary["evidence"] else None,
            "citations": [],
        }

    row = dict(row)
    return {
        "source": summary["source"] if summary else None,
        "dataset": summary["dataset"] if summary else None,
        "report": summary["report"] if summary else {
            "entity_code": entity_code,
            "exercise": exercise,
            "period": period,
            "annex": annex,
            "period_label": format_period_label(exercise, period),
        },
        "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary and summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
        "payload_hash": summary["raw_record"]["payload_hash"] if summary and summary["raw_record"] else None,
        "status": "ok",
        "row": row,
        "value": row["value_numeric"],
        "value_formatted": format_brl_amount(row["value_numeric"]),
        "source_url": summary["evidence"]["source_url"] if summary and summary["evidence"] else None,
        "citations": [
            {
                "entity_code": entity_code,
                "exercise": exercise,
                "period": period,
                "annex": annex,
                "external_id": external_id,
                "source_url": summary["evidence"]["source_url"] if summary and summary["evidence"] else None,
                "payload_hash": summary["raw_record"]["payload_hash"] if summary and summary["raw_record"] else None,
            }
        ],
    }
