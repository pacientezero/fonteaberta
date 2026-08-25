from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

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
        if (parent / "tests" / "fixtures" / "transparencia" / "despesas_execucao_202608.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "transparencia" / "despesas_execucao_202608.json"

TRANSPARENCIA_SOURCE_SLUG = "transparencia"
TRANSPARENCIA_DATASET_SLUG = "despesas-execucao-2026-08"
TRANSPARENCIA_DATASET_EXTERNAL_ID = "despesas-execucao-202608"
TRANSPARENCIA_EXPENSE_MONTH = date(2026, 8, 1)
EXPENSE_SUBJECT_TYPE = "government_expense_period"
EXPENSE_SUMMARY_PREDICATE = "monthly_expense_summary"

TEXT_COLUMNS = [
    "superior_org_code",
    "superior_org_name",
    "subordinate_org_code",
    "subordinate_org_name",
    "managing_unit_code",
    "managing_unit_name",
    "management_code",
    "management_name",
    "budget_unit_code",
    "budget_unit_name",
    "function_code",
    "function_name",
    "subfunction_code",
    "subfunction_name",
    "budget_program_code",
    "budget_program_name",
    "action_code",
    "action_name",
    "planning_code",
    "planning_name",
    "government_program_code",
    "government_program_name",
    "uf",
    "municipality",
    "subtitle_code",
    "subtitle_name",
    "locator_code",
    "locator_name",
    "locator_sigla",
    "locator_description",
    "amendment_author_code",
    "amendment_author_name",
    "economic_category_code",
    "economic_category_name",
    "expense_group_code",
    "expense_group_name",
    "expense_element_code",
    "expense_element_name",
    "expense_modality_code",
    "expense_modality_name",
]

DECIMAL_COLUMNS = [
    "committed_amount",
    "liquidated_amount",
    "paid_amount",
    "restos_apagar_inscritos_amount",
    "restos_apagar_cancelados_amount",
    "restos_apagar_pagos_amount",
]

STORAGE_COLUMNS = [
    "expense_month",
    *TEXT_COLUMNS,
    *DECIMAL_COLUMNS,
    "source_updated_at",
    "collected_at",
    "raw_payload",
    "metadata",
]

RETURN_COLUMNS = [
    "id",
    "source_id",
    "dataset_id",
    "external_id",
    *STORAGE_COLUMNS,
    "created_at",
    "updated_at",
]

EXTERNAL_ID_KEY_FIELDS = [
    "expense_month",
    "superior_org_code",
    "subordinate_org_code",
    "managing_unit_code",
    "management_code",
    "budget_unit_code",
    "function_code",
    "subfunction_code",
    "budget_program_code",
    "action_code",
    "planning_code",
    "government_program_code",
    "uf",
    "municipality",
    "subtitle_code",
    "locator_code",
    "amendment_author_code",
    "economic_category_code",
    "expense_group_code",
    "expense_element_code",
    "expense_modality_code",
]

MONTH_NAMES_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
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


def parse_expense_period(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None
    if len(text) == 7 and text[4] == "-":
        return date.fromisoformat(f"{text}-01")
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return date.fromisoformat(text)
    if len(text) == 7 and text[4] == "/":
        return datetime.strptime(text, "%Y/%m").date().replace(day=1)
    if len(text) == 6 and text.isdigit():
        return datetime.strptime(text, "%Y%m").date().replace(day=1)
    raise ValueError(f"Unsupported expense period format: {value}")


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def format_brl_amount(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    sign = "-" if quantized < 0 else ""
    absolute = abs(quantized)
    integer_part, decimal_part = f"{absolute:.2f}".split(".")
    grouped = f"{int(integer_part):,}".replace(",", ".")
    return f"{sign}R$ {grouped},{decimal_part}"


def format_month_label(expense_month: date) -> str:
    return f"{MONTH_NAMES_PT[expense_month.month]} de {expense_month.year}"


def _fetch_rows(conn, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def expense_row_signature(row: Mapping[str, Any]) -> dict[str, str]:
    signature: dict[str, str] = {}
    for field in EXTERNAL_ID_KEY_FIELDS:
        value = row.get(field)
        if isinstance(value, date):
            signature[field] = value.isoformat()
        elif value is None:
            signature[field] = ""
        else:
            signature[field] = str(value)
    return signature


def expense_row_external_id(row: Mapping[str, Any]) -> str:
    signature = expense_row_signature(row)
    digest = hashlib.sha256(canonical_json_bytes(signature)).hexdigest()
    return f"pt-expense-{digest[:24]}"


def normalize_expense_row(
    row: Mapping[str, Any],
    *,
    default_expense_month: date | None = None,
    default_source_updated_at: datetime | None = None,
    default_collected_at: datetime | None = None,
) -> dict[str, Any]:
    payload = dict(row)
    expense_month = parse_expense_period(payload.get("expense_month") or default_expense_month)
    if expense_month is None:
        raise ValueError("expense_month is required")

    normalized: dict[str, Any] = {"expense_month": expense_month}
    for field in TEXT_COLUMNS:
        normalized[field] = normalize_text(payload.get(field))
    for field in DECIMAL_COLUMNS:
        normalized[field] = parse_brazilian_decimal(payload.get(field))

    normalized["source_updated_at"] = parse_iso_datetime(payload.get("source_updated_at")) or default_source_updated_at
    normalized["collected_at"] = parse_iso_datetime(payload.get("collected_at")) or default_collected_at or datetime.now(timezone.utc)
    normalized["raw_payload"] = payload
    normalized["metadata"] = dict(payload.get("metadata") or {})
    normalized["external_id"] = normalize_text(payload.get("external_id")) or expense_row_external_id(normalized)
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
        (source_id, dataset_id, "connector-transparencia-expansion", source_checksum_value),
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
            "connector-transparencia-expansion",
            "full",
            started_at,
            finished_at,
            "success",
            len(bundle["expenses"]),
            len(bundle["expenses"]),
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
    expense_month = parse_expense_period(bundle.get("expense_month") or bundle["dataset"].get("period_start") or TRANSPARENCIA_EXPENSE_MONTH)
    payload = {
        "expense_month": expense_month.isoformat() if expense_month else None,
        "expenses": bundle["expenses"],
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
            raw_record_payload.get("external_id", TRANSPARENCIA_DATASET_EXTERNAL_ID),
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
            evidence_payload.get("external_id", f"{TRANSPARENCIA_DATASET_EXTERNAL_ID}-evidence"),
            evidence_payload.get("source_url", bundle["dataset"]["resource_url"]),
            evidence_payload.get("page"),
            evidence_payload.get("section", "Despesas Execucao"),
            parse_iso_datetime(evidence_payload.get("collected_at")) or datetime.now(timezone.utc),
            evidence_payload.get("payload_hash", payload_hash(bundle)),
            Jsonb(metadata),
        ),
    )


def upsert_expense_rows(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    bundle: Mapping[str, Any],
    default_expense_month: date,
) -> list[dict[str, Any]]:
    inserted: list[dict[str, Any]] = []
    insert_columns = ["source_id", "dataset_id", "external_id", *STORAGE_COLUMNS]
    update_columns = [column for column in STORAGE_COLUMNS]
    returning_sql = ", ".join(RETURN_COLUMNS)
    insert_sql = f"""
        INSERT INTO government_expenses ({", ".join(insert_columns)})
        VALUES ({", ".join(["%s"] * len(insert_columns))})
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            {", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)}
        RETURNING {returning_sql}
        """

    for raw_row in bundle["expenses"]:
        normalized = normalize_expense_row(
            raw_row,
            default_expense_month=default_expense_month,
            default_source_updated_at=parse_iso_datetime(bundle.get("raw_record", {}).get("source_updated_at")),
            default_collected_at=parse_iso_datetime(bundle.get("raw_record", {}).get("collected_at")),
        )
        params: list[Any] = [
            source_id,
            dataset_id,
            normalized["external_id"],
            normalized["expense_month"],
        ]
        params.extend(normalized[column] for column in TEXT_COLUMNS)
        params.extend(normalized[column] for column in DECIMAL_COLUMNS)
        params.extend(
            [
                normalized["source_updated_at"],
                normalized["collected_at"],
                Jsonb(normalized["raw_payload"]),
                Jsonb(normalized["metadata"]),
            ]
        )
        inserted.append(_fetch_one(conn, insert_sql, tuple(params)))
    return inserted


def summarize_expenses(expenses: Sequence[Mapping[str, Any]], expense_month: date) -> dict[str, Any]:
    totals = {
        "committed_amount": sum((row["committed_amount"] or Decimal("0") for row in expenses), Decimal("0")),
        "liquidated_amount": sum((row["liquidated_amount"] or Decimal("0") for row in expenses), Decimal("0")),
        "paid_amount": sum((row["paid_amount"] or Decimal("0") for row in expenses), Decimal("0")),
        "restos_apagar_inscritos_amount": sum((row["restos_apagar_inscritos_amount"] or Decimal("0") for row in expenses), Decimal("0")),
        "restos_apagar_cancelados_amount": sum((row["restos_apagar_cancelados_amount"] or Decimal("0") for row in expenses), Decimal("0")),
        "restos_apagar_pagos_amount": sum((row["restos_apagar_pagos_amount"] or Decimal("0") for row in expenses), Decimal("0")),
    }
    return {
        "expense_month": expense_month,
        "row_count": len(expenses),
        "totals": totals,
    }


def summary_statement(expense_month: date, totals: Mapping[str, Decimal]) -> str:
    return (
        f"No recorte validado de {format_month_label(expense_month)} do Portal da Transparência, "
        f"foram {format_brl_amount(totals['committed_amount'])} empenhados, "
        f"{format_brl_amount(totals['liquidated_amount'])} liquidados e "
        f"{format_brl_amount(totals['paid_amount'])} pagos."
    )


def expense_summary_subject_id(source_slug: str, dataset_slug: str, expense_month: date) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"fonteaberta:government_expense_period:{source_slug}:{dataset_slug}:{expense_month.isoformat()}",
    )


def upsert_summary_fact(
    conn,
    *,
    source_id: str,
    source_slug: str,
    dataset_slug: str,
    evidence_id: str,
    expense_month: date,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    subject_id = expense_summary_subject_id(source_slug, dataset_slug, expense_month)
    statement = summary_statement(expense_month, summary["totals"])
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
        (EXPENSE_SUBJECT_TYPE, str(subject_id), EXPENSE_SUMMARY_PREDICATE),
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

    metadata = {
        "expense_month": expense_month.isoformat(),
        "row_count": summary["row_count"],
        "totals": {key: str(value) for key, value in summary["totals"].items()},
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
            EXPENSE_SUBJECT_TYPE,
            str(subject_id),
            EXPENSE_SUMMARY_PREDICATE,
            "text",
            None,
            statement,
            summary["totals"]["paid_amount"],
            None,
            expense_month,
            "BRL",
            expense_month,
            source_id,
            evidence_id,
            "sum(government_expenses.*)",
            Jsonb(metadata),
        ),
    )


def upsert_summary_claim(
    conn,
    *,
    source_slug: str,
    dataset_slug: str,
    expense_month: date,
    fact_id: str,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    subject_id = expense_summary_subject_id(source_slug, dataset_slug, expense_month)
    statement = summary_statement(expense_month, summary["totals"])
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
        (EXPENSE_SUBJECT_TYPE, str(subject_id), statement),
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
            EXPENSE_SUBJECT_TYPE,
            str(subject_id),
            "sum(government_expenses.*)",
            "manual",
            "transparencia-expansion",
            Jsonb(
                {
                    "fact_id": str(fact_id),
                    "expense_month": expense_month.isoformat(),
                    "row_count": summary["row_count"],
                    "paid_amount": str(summary["totals"]["paid_amount"]),
                }
            ),
        ),
    )


def ingest_official_bundle(conn, bundle: Mapping[str, Any], *, source_checksum_value: str | None = None) -> dict[str, Any]:
    source = ensure_source(conn, bundle["source"])
    dataset = ensure_dataset(conn, source["id"], bundle["dataset"])
    default_expense_month = parse_expense_period(
        bundle.get("expense_month") or bundle["dataset"].get("period_start") or TRANSPARENCIA_EXPENSE_MONTH
    )
    if default_expense_month is None:
        raise ValueError("expense_month is required")

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
    expenses = upsert_expense_rows(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        bundle=bundle,
        default_expense_month=default_expense_month,
    )
    summary = summarize_expenses(expenses, default_expense_month)
    fact = upsert_summary_fact(
        conn,
        source_id=source["id"],
        source_slug=source["slug"],
        dataset_slug=dataset["slug"],
        evidence_id=evidence["id"],
        expense_month=default_expense_month,
        summary=summary,
    )
    claim = upsert_summary_claim(
        conn,
        source_slug=source["slug"],
        dataset_slug=dataset["slug"],
        expense_month=default_expense_month,
        fact_id=fact["id"],
        summary=summary,
    )
    claim_evidence = upsert_claim_evidence(conn, claim["id"], evidence["id"])
    return {
        "source": source,
        "dataset": dataset,
        "ingestion_run": ingestion_run,
        "raw_record": raw_record,
        "evidence": evidence,
        "expenses": expenses,
        "summary": summary,
        "summary_fact": fact,
        "summary_claim": claim,
        "summary_claim_evidence": claim_evidence,
    }


def fetch_expense_summary(conn, expense_period: str | None = None) -> dict[str, Any]:
    target_month = parse_expense_period(expense_period)
    if target_month is None:
        latest = _fetch_optional(
            conn,
            """
            SELECT expense_month
            FROM government_expenses
            ORDER BY expense_month DESC, created_at DESC
            LIMIT 1
            """,
            (),
        )
        if latest is None:
            raise KeyError("government_expense_period")
        target_month = latest["expense_month"]

    lead_row = _fetch_optional(
        conn,
        """
        SELECT ge.id, ge.source_id, ge.dataset_id, ge.external_id, ge.expense_month, ge.superior_org_code,
               ge.superior_org_name, ge.subordinate_org_code, ge.subordinate_org_name, ge.managing_unit_code,
               ge.managing_unit_name, ge.management_code, ge.management_name, ge.budget_unit_code,
               ge.budget_unit_name, ge.function_code, ge.function_name, ge.subfunction_code, ge.subfunction_name,
               ge.budget_program_code, ge.budget_program_name, ge.action_code, ge.action_name, ge.planning_code,
               ge.planning_name, ge.government_program_code, ge.government_program_name, ge.uf, ge.municipality,
               ge.subtitle_code, ge.subtitle_name, ge.locator_code, ge.locator_name, ge.locator_sigla,
               ge.locator_description, ge.amendment_author_code, ge.amendment_author_name, ge.economic_category_code,
               ge.economic_category_name, ge.expense_group_code, ge.expense_group_name, ge.expense_element_code,
               ge.expense_element_name, ge.expense_modality_code, ge.expense_modality_name, ge.committed_amount,
               ge.liquidated_amount, ge.paid_amount, ge.restos_apagar_inscritos_amount,
               ge.restos_apagar_cancelados_amount, ge.restos_apagar_pagos_amount, ge.source_updated_at,
               ge.collected_at, ge.raw_payload, ge.metadata, ge.created_at, ge.updated_at,
               s.name AS source_name, s.slug AS source_slug, s.base_url AS source_url,
               d.name AS dataset_name, d.slug AS dataset_slug, d.resource_url AS dataset_url
        FROM government_expenses AS ge
        JOIN sources AS s ON s.id = ge.source_id
        JOIN datasets AS d ON d.id = ge.dataset_id
        WHERE ge.expense_month = %s
        ORDER BY ge.paid_amount DESC, ge.external_id ASC
        LIMIT 1
        """,
        (target_month,),
    )
    if lead_row is None:
        raise KeyError(target_month.isoformat())

    expenses = _fetch_rows(
        conn,
        """
        SELECT id, source_id, dataset_id, external_id, expense_month, superior_org_code, superior_org_name,
               subordinate_org_code, subordinate_org_name, managing_unit_code, managing_unit_name, management_code,
               management_name, budget_unit_code, budget_unit_name, function_code, function_name, subfunction_code,
               subfunction_name, budget_program_code, budget_program_name, action_code, action_name, planning_code,
               planning_name, government_program_code, government_program_name, uf, municipality, subtitle_code,
               subtitle_name, locator_code, locator_name, locator_sigla, locator_description, amendment_author_code,
               amendment_author_name, economic_category_code, economic_category_name, expense_group_code,
               expense_group_name, expense_element_code, expense_element_name, expense_modality_code,
               expense_modality_name, committed_amount, liquidated_amount, paid_amount,
               restos_apagar_inscritos_amount, restos_apagar_cancelados_amount, restos_apagar_pagos_amount,
               source_updated_at, collected_at, raw_payload, metadata, created_at, updated_at
        FROM government_expenses
        WHERE expense_month = %s
        ORDER BY paid_amount DESC, external_id ASC
        """,
        (target_month,),
    )

    summary = summarize_expenses(expenses, target_month)
    source_slug = lead_row["source_slug"]
    dataset_slug = lead_row["dataset_slug"]
    summary_subject_id = expense_summary_subject_id(source_slug, dataset_slug, target_month)

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
        (EXPENSE_SUBJECT_TYPE, str(summary_subject_id), EXPENSE_SUMMARY_PREDICATE),
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
        (EXPENSE_SUBJECT_TYPE, str(summary_subject_id)),
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
        (lead_row["source_id"], lead_row["dataset_id"]),
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
        (lead_row["source_id"], lead_row["dataset_id"]),
    )

    return {
        "source": {
            "id": lead_row["source_id"],
            "name": lead_row["source_name"],
            "slug": source_slug,
            "base_url": lead_row["source_url"],
        },
        "dataset": {
            "id": lead_row["dataset_id"],
            "name": lead_row["dataset_name"],
            "slug": dataset_slug,
            "resource_url": lead_row["dataset_url"],
        },
        "expense_month": target_month,
        "expenses": expenses,
        "summary": summary,
        "fact": fact,
        "claim": claim,
        "raw_record": raw_record,
        "evidence": evidence,
        "latest_paid_amount_formatted": format_brl_amount(summary["totals"]["paid_amount"]),
    }


def query_expense_response(conn, expense_period: str | None = None) -> dict[str, Any]:
    target_month = parse_expense_period(expense_period)
    try:
        summary = fetch_expense_summary(conn, expense_period)
    except KeyError:
        expense_month = target_month.isoformat() if target_month else None
        return {
            "source": None,
            "dataset": None,
            "expense_month": expense_month,
            "collection_timestamp": None,
            "payload_hash": None,
            "paid_amount": None,
            "paid_amount_formatted": None,
            "summary": None,
            "status": "no_evidence",
            "source_url": None,
            "citations": [],
        }

    response = {
        "source": summary["source"],
        "dataset": summary["dataset"],
        "expense_month": summary["expense_month"].isoformat(),
        "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
        "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
        "paid_amount": summary["summary"]["totals"]["paid_amount"],
        "paid_amount_formatted": format_brl_amount(summary["summary"]["totals"]["paid_amount"]),
        "summary": {
            "row_count": summary["summary"]["row_count"],
            "totals": summary["summary"]["totals"],
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
                "expense_month": summary["expense_month"].isoformat(),
                "row_count": summary["summary"]["row_count"],
                "source_url": summary["evidence"]["source_url"],
                "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
            }
        ],
    }


def query_expense_row_response(
    conn,
    expense_period: str,
    external_id: str,
) -> dict[str, Any]:
    target_month = parse_expense_period(expense_period)
    if target_month is None:
        raise ValueError("expense_period is required")

    row = _fetch_optional(
        conn,
        """
        SELECT id, source_id, dataset_id, external_id, expense_month, superior_org_code, superior_org_name,
               subordinate_org_code, subordinate_org_name, managing_unit_code, managing_unit_name, management_code,
               management_name, budget_unit_code, budget_unit_name, function_code, function_name, subfunction_code,
               subfunction_name, budget_program_code, budget_program_name, action_code, action_name, planning_code,
               planning_name, government_program_code, government_program_name, uf, municipality, subtitle_code,
               subtitle_name, locator_code, locator_name, locator_sigla, locator_description, amendment_author_code,
               amendment_author_name, economic_category_code, economic_category_name, expense_group_code,
               expense_group_name, expense_element_code, expense_element_name, expense_modality_code,
               expense_modality_name, committed_amount, liquidated_amount, paid_amount,
               restos_apagar_inscritos_amount, restos_apagar_cancelados_amount, restos_apagar_pagos_amount,
               source_updated_at, collected_at, raw_payload, metadata, created_at, updated_at
        FROM government_expenses
        WHERE expense_month = %s
          AND external_id = %s
        LIMIT 1
        """,
        (target_month, external_id),
    )
    if row is None:
        try:
            summary = fetch_expense_summary(conn, target_month.isoformat())
        except KeyError:
            return {
                "source": None,
                "dataset": None,
                "expense_month": target_month.isoformat(),
                "collection_timestamp": None,
                "payload_hash": None,
                "status": "no_evidence",
                "expense": None,
                "value": None,
                "value_formatted": None,
                "source_url": None,
                "citations": [],
            }
        return {
            "source": summary["source"],
            "dataset": summary["dataset"],
            "expense_month": target_month.isoformat(),
            "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
            "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
            "status": "no_evidence",
            "expense": None,
            "value": None,
            "value_formatted": None,
            "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
            "citations": [],
        }

    summary = fetch_expense_summary(conn, target_month.isoformat())
    row = dict(row)
    return {
        "source": summary["source"],
        "dataset": summary["dataset"],
        "expense_month": target_month.isoformat(),
        "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
        "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
        "status": "ok",
        "expense": row,
        "value": row["paid_amount"],
        "value_formatted": format_brl_amount(row["paid_amount"]),
        "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
        "citations": [
            {
                "expense_month": target_month.isoformat(),
                "external_id": external_id,
                "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
                "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
            }
        ],
    }
