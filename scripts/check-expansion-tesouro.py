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
from app.tesouro_expansion import (  # noqa: E402
    TESOURO_ANEXO,
    TESOURO_ENTITY_CODE,
    TESOURO_EXERCISE,
    TESOURO_HEADLINE_ACCOUNT_CODE,
    TESOURO_HEADLINE_COLUMN_LABEL,
    TESOURO_PERIOD,
    fetch_rreo_summary,
    format_brl_amount,
    ingest_official_bundle,
    load_fixture_bundle,
    payload_hash,
    query_rreo_response,
    query_rreo_row_response,
    summary_statement,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Tesouro expansion slice.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "tesouro" / "rreo_sp_2024_p06_anexo01.json",
        help="Path to the official Tesouro RREO fixture bundle.",
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

    expected_paid = sum((parse_decimal(row["valor"]) for row in bundle["items"]), Decimal("0"))

    with db_connection() as connection:
        first = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        second = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        summary = fetch_rreo_summary(
            connection,
            TESOURO_ENTITY_CODE,
            TESOURO_EXERCISE,
            TESOURO_PERIOD,
            TESOURO_ANEXO,
        )
        present_response = query_rreo_response(
            connection,
            TESOURO_ENTITY_CODE,
            TESOURO_EXERCISE,
            TESOURO_PERIOD,
            TESOURO_ANEXO,
        )
        missing_response = query_rreo_response(
            connection,
            TESOURO_ENTITY_CODE,
            TESOURO_EXERCISE,
            TESOURO_PERIOD - 1,
            TESOURO_ANEXO,
        )
        detail_response = query_rreo_row_response(
            connection,
            TESOURO_ENTITY_CODE,
            TESOURO_EXERCISE,
            TESOURO_PERIOD,
            summary["headline_row"]["external_id"],
            TESOURO_ANEXO,
        )

        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM rreo_rows WHERE source_id = %s AND dataset_id = %s) AS row_count,
                (SELECT COUNT(*) FROM raw_records WHERE source_id = %s AND dataset_id = %s) AS raw_record_count,
                (SELECT COUNT(*) FROM evidence WHERE source_id = %s AND dataset_id = %s) AS evidence_count,
                (SELECT COUNT(*) FROM facts
                 WHERE subject_type = %s
                   AND subject_id = %s
                   AND predicate = %s) AS fact_count,
                (SELECT COUNT(*) FROM facts
                 WHERE subject_type = %s
                   AND subject_id = %s
                   AND predicate = %s
                   AND evidence_id = %s) AS fact_evidence_count,
                (SELECT COUNT(*) FROM claims
                 WHERE subject_type = %s
                   AND subject_id = %s) AS claim_count,
                (SELECT COUNT(*) FROM claims_evidence
                 WHERE claim_id = %s
                   AND evidence_id = %s) AS claim_evidence_count
            """,
            (
                first["source"]["id"],
                first["dataset"]["id"],
                first["source"]["id"],
                first["dataset"]["id"],
                first["source"]["id"],
                first["dataset"]["id"],
                "siconfi_rreo_report",
                str(summary["fact"]["subject_id"]),
                "rreo_bimonthly_expense_headline",
                "siconfi_rreo_report",
                str(summary["fact"]["subject_id"]),
                "rreo_bimonthly_expense_headline",
                summary["evidence"]["id"],
                "siconfi_rreo_report",
                str(summary["fact"]["subject_id"]),
                summary["claim"]["id"],
                summary["evidence"]["id"],
            ),
        ).fetchone()
        counts = dict(counts)

    expected_statement = summary_statement(
        summary["headline_row"],
        exercise=TESOURO_EXERCISE,
        period=TESOURO_PERIOD,
        annex=TESOURO_ANEXO,
    )
    expected_headline_value = parse_decimal(summary["headline_row"]["value_numeric"])

    assert first["source"]["slug"] == "tesouro"
    assert first["dataset"]["slug"] == "rreo-3550308-2024-p06-anexo01"
    assert second["ingestion_run"]["id"] == first["ingestion_run"]["id"]
    assert counts["row_count"] == len(bundle["items"])
    assert counts["raw_record_count"] == 1
    assert counts["evidence_count"] == 1
    assert counts["fact_count"] == 1
    assert counts["fact_evidence_count"] == 1
    assert counts["claim_count"] == 1
    assert counts["claim_evidence_count"] == 1
    assert summary["headline_row"]["account_code"] == TESOURO_HEADLINE_ACCOUNT_CODE
    assert summary["headline_row"]["column_label"] == TESOURO_HEADLINE_COLUMN_LABEL
    assert expected_headline_value == Decimal("105733532939.31")
    assert summary["headline_value_formatted"] == format_brl_amount(expected_headline_value)
    assert summary["fact"]["value_text"] == expected_statement
    assert summary["fact"]["evidence_id"] == summary["evidence"]["id"]
    assert summary["claim"]["statement"] == expected_statement
    assert first["claim_evidence"]["claim_id"] == summary["claim"]["id"]
    assert first["claim_evidence"]["evidence_id"] == summary["evidence"]["id"]
    assert summary["raw_record"]["payload_hash"] == source_checksum
    assert summary["evidence"]["source_url"] == first["evidence"]["source_url"]
    assert present_response["status"] == "ok"
    assert present_response["row_count"] == len(bundle["items"])
    assert present_response["headline"]["external_id"] == summary["headline_row"]["external_id"]
    assert present_response["headline"]["account_code"] == TESOURO_HEADLINE_ACCOUNT_CODE
    assert present_response["headline"]["column_label"] == TESOURO_HEADLINE_COLUMN_LABEL
    assert present_response["headline"]["value"] == expected_headline_value
    assert present_response["headline"]["value_formatted"] == format_brl_amount(expected_headline_value)
    assert present_response["source_url"] == first["evidence"]["source_url"]
    assert missing_response["status"] == "no_evidence"
    assert missing_response["row_count"] == 0
    assert missing_response["headline"] is None
    assert missing_response["citations"] == []
    assert detail_response["status"] == "ok"
    assert detail_response["row"]["external_id"] == summary["headline_row"]["external_id"]
    assert detail_response["value"] == expected_headline_value
    assert detail_response["value_formatted"] == format_brl_amount(expected_headline_value)

    print(
        json.dumps(
            {
                "source_checksum": source_checksum,
                "source": first["source"]["slug"],
                "dataset": first["dataset"]["slug"],
                "rows": len(summary["rows"]),
                "headline": summary["headline_row"]["external_id"],
                "headline_value_formatted": summary["headline_value_formatted"],
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
