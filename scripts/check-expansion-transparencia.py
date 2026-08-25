#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db import db_connection  # noqa: E402
from app.transparencia_expansion import (  # noqa: E402
    expense_summary_subject_id,
    fetch_expense_summary,
    format_brl_amount,
    ingest_official_bundle,
    load_fixture_bundle,
    payload_hash,
    query_expense_response,
    query_expense_row_response,
    summary_statement,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Portal da Transparência expansion slice.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "transparencia" / "despesas_execucao_202608.json",
        help="Path to the official Portal da Transparência fixture bundle.",
    )
    return parser.parse_args()


def parse_decimal(value: str | Decimal | int | float | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def main() -> int:
    args = parse_args()
    bundle = load_fixture_bundle(args.fixture)
    source_checksum = payload_hash(bundle)

    expected_committed = sum((parse_decimal(row["committed_amount"]) for row in bundle["expenses"]), Decimal("0"))
    expected_liquidated = sum((parse_decimal(row["liquidated_amount"]) for row in bundle["expenses"]), Decimal("0"))
    expected_paid = sum((parse_decimal(row["paid_amount"]) for row in bundle["expenses"]), Decimal("0"))

    with db_connection() as connection:
        first = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        second = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        summary = fetch_expense_summary(connection, bundle["expense_month"])
        present_response = query_expense_response(connection, bundle["expense_month"])
        missing_response = query_expense_response(connection, "2026-07")
        detail_response = query_expense_row_response(
            connection,
            bundle["expense_month"],
            first["expenses"][0]["external_id"],
        )

        summary_subject = expense_summary_subject_id(
            first["source"]["slug"],
            first["dataset"]["slug"],
            summary["expense_month"],
        )

        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM government_expenses WHERE source_id = %s AND dataset_id = %s) AS expense_count,
                (SELECT COUNT(*) FROM raw_records WHERE source_id = %s AND dataset_id = %s) AS raw_record_count,
                (SELECT COUNT(*) FROM evidence WHERE source_id = %s AND dataset_id = %s) AS evidence_count,
                (SELECT COUNT(*) FROM facts WHERE subject_type = %s AND subject_id = %s AND predicate = %s) AS fact_count,
                (SELECT COUNT(*) FROM facts WHERE subject_type = %s AND subject_id = %s AND predicate = %s AND evidence_id = %s) AS fact_evidence_count,
                (SELECT COUNT(*) FROM claims WHERE subject_type = %s AND subject_id = %s) AS claim_count,
                (SELECT COUNT(*) FROM claims_evidence WHERE claim_id = %s AND evidence_id = %s) AS claim_evidence_count
            """,
            (
                first["source"]["id"],
                first["dataset"]["id"],
                first["source"]["id"],
                first["dataset"]["id"],
                first["source"]["id"],
                first["dataset"]["id"],
                "government_expense_period",
                str(summary_subject),
                "monthly_expense_summary",
                "government_expense_period",
                str(summary_subject),
                "monthly_expense_summary",
                summary["evidence"]["id"],
                "government_expense_period",
                str(summary_subject),
                summary["claim"]["id"],
                summary["evidence"]["id"],
            ),
        ).fetchone()
        counts = dict(counts)

    expected_statement = summary_statement(summary["expense_month"], summary["summary"]["totals"])

    assert first["source"]["slug"] == "transparencia"
    assert first["dataset"]["slug"] == "despesas-execucao-2026-08"
    assert second["summary_fact"]["id"] == first["summary_fact"]["id"]
    assert second["summary_claim"]["id"] == first["summary_claim"]["id"]
    assert counts["expense_count"] == len(bundle["expenses"])
    assert counts["raw_record_count"] == 1
    assert counts["evidence_count"] == 1
    assert counts["fact_count"] == 1
    assert counts["fact_evidence_count"] == 1
    assert counts["claim_count"] == 1
    assert counts["claim_evidence_count"] == 1
    assert summary["summary"]["row_count"] == len(bundle["expenses"])
    assert summary["summary"]["totals"]["committed_amount"] == expected_committed
    assert summary["summary"]["totals"]["liquidated_amount"] == expected_liquidated
    assert summary["summary"]["totals"]["paid_amount"] == expected_paid
    assert summary["summary"]["totals"]["paid_amount"] == Decimal("200089.66")
    assert summary["fact"]["value_text"] == expected_statement
    assert summary["fact"]["evidence_id"] == summary["evidence"]["id"]
    assert summary["claim"]["statement"] == expected_statement
    assert first["summary_claim_evidence"]["claim_id"] == summary["claim"]["id"]
    assert first["summary_claim_evidence"]["evidence_id"] == summary["evidence"]["id"]
    assert summary["raw_record"]["payload_hash"] == source_checksum
    assert summary["evidence"]["source_url"] == bundle["evidence"]["source_url"]
    assert present_response["status"] == "ok"
    assert present_response["paid_amount"] == Decimal("200089.66")
    assert present_response["paid_amount_formatted"] == format_brl_amount(Decimal("200089.66"))
    assert missing_response["status"] == "no_evidence"
    assert missing_response["paid_amount"] is None
    assert missing_response["citations"] == []
    assert detail_response["status"] == "ok"
    assert detail_response["expense"]["external_id"] == first["expenses"][0]["external_id"]
    assert detail_response["value"] == first["expenses"][0]["paid_amount"]
    assert detail_response["value_formatted"] == format_brl_amount(first["expenses"][0]["paid_amount"])

    print(
        json.dumps(
            {
                "source_checksum": source_checksum,
                "source": first["source"]["slug"],
                "dataset": first["dataset"]["slug"],
                "expense_month": summary["expense_month"].isoformat(),
                "expenses": len(summary["expenses"]),
                "paid_amount_formatted": present_response["paid_amount_formatted"],
                "statement": expected_statement,
                "present_response": present_response["status"],
                "missing_response": missing_response["status"],
                "detail_response": detail_response["status"],
                "counts": counts,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
