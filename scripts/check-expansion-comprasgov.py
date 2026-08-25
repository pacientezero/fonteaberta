#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.comprasgov_expansion import (  # noqa: E402
    COMPRASGOV_ACTIVE,
    COMPRASGOV_DATASET_SLUG,
    COMPRASGOV_PAGE,
    COMPRASGOV_PAGE_SIZE,
    fetch_supplier_summary,
    ingest_official_bundle,
    load_fixture_bundle,
    payload_hash,
    query_supplier_response,
    query_supplier_row_response,
    report_subject_id,
)
from app.db import db_connection  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Compras.gov expansion slice.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "comprasgov" / "fornecedores_ativos_p01_t10.json",
        help="Path to the official Compras.gov fixture bundle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = load_fixture_bundle(args.fixture)
    source_checksum = payload_hash(bundle)

    with db_connection() as connection:
        first = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        second = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        summary = fetch_supplier_summary(connection, COMPRASGOV_PAGE, COMPRASGOV_PAGE_SIZE, COMPRASGOV_ACTIVE)
        present_response = query_supplier_response(connection, COMPRASGOV_PAGE, COMPRASGOV_PAGE_SIZE, COMPRASGOV_ACTIVE)
        missing_response = query_supplier_response(connection, COMPRASGOV_PAGE + 1, COMPRASGOV_PAGE_SIZE, COMPRASGOV_ACTIVE)
        detail_response = query_supplier_row_response(
            connection,
            summary["headline_row"]["external_id"],
            COMPRASGOV_PAGE,
            COMPRASGOV_PAGE_SIZE,
            COMPRASGOV_ACTIVE,
        )
        wrong_page_detail_response = query_supplier_row_response(
            connection,
            summary["headline_row"]["external_id"],
            COMPRASGOV_PAGE + 1,
            COMPRASGOV_PAGE_SIZE,
            COMPRASGOV_ACTIVE,
        )
        missing_detail_response = query_supplier_row_response(
            connection,
            "cnpj:99999999999999",
            COMPRASGOV_PAGE,
            COMPRASGOV_PAGE_SIZE,
            COMPRASGOV_ACTIVE,
        )

        summary_subject = report_subject_id(COMPRASGOV_PAGE, COMPRASGOV_PAGE_SIZE, COMPRASGOV_ACTIVE)
        expected_statement = summary["headline_statement"]

        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM comprasgov_supplier_records WHERE source_id = %s AND dataset_id = %s) AS supplier_count,
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
                   AND subject_id = %s
                   AND statement = %s) AS claim_count,
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
                "comprasgov_supplier_snapshot",
                str(summary_subject),
                "supplier_page_headline",
                "comprasgov_supplier_snapshot",
                str(summary_subject),
                "supplier_page_headline",
                summary["evidence"]["id"],
                "comprasgov_supplier_snapshot",
                str(summary_subject),
                expected_statement,
                summary["claim"]["id"],
                summary["evidence"]["id"],
            ),
        ).fetchone()
        counts = dict(counts)

    assert first["source"]["slug"] == "comprasgov"
    assert first["dataset"]["slug"] == COMPRASGOV_DATASET_SLUG
    assert second["ingestion_run"]["id"] == first["ingestion_run"]["id"]
    assert counts["supplier_count"] == len(bundle["resultado"])
    assert counts["raw_record_count"] == 1
    assert counts["evidence_count"] == 1
    assert counts["fact_count"] == 1
    assert counts["fact_evidence_count"] == 1
    assert counts["claim_count"] == 1
    assert counts["claim_evidence_count"] == 1
    assert summary["row_count"] == len(bundle["resultado"])
    assert summary["headline_row"]["supplier_name"] == "BANCO DO BRASIL SA"
    assert summary["headline_row"]["identity_confidence"] == "strong"
    assert summary["fact"]["value_text"] == expected_statement
    assert summary["fact"]["evidence_id"] == summary["evidence"]["id"]
    assert summary["claim"]["statement"] == expected_statement
    assert first["claim_evidence"]["claim_id"] == summary["claim"]["id"]
    assert first["claim_evidence"]["evidence_id"] == summary["evidence"]["id"]
    assert summary["raw_record"]["payload_hash"] == source_checksum
    assert summary["evidence"]["source_url"] == bundle["source_url"]
    assert present_response["status"] == "ok"
    assert present_response["row_count"] == len(bundle["resultado"])
    assert present_response["headline"]["external_id"] == summary["headline_row"]["external_id"]
    assert present_response["headline"]["identity_confidence"] == "strong"
    assert present_response["source_url"] == bundle["source_url"]
    assert missing_response["status"] == "no_evidence"
    assert missing_response["row_count"] == 0
    assert missing_response["headline"] is None
    assert missing_response["citations"] == []
    assert detail_response["status"] == "ok"
    assert detail_response["row"]["external_id"] == summary["headline_row"]["external_id"]
    assert detail_response["row"]["identity_confidence"] == "strong"
    assert wrong_page_detail_response["status"] == "no_evidence"
    assert wrong_page_detail_response["row"] is None
    assert wrong_page_detail_response["citations"] == []
    assert missing_detail_response["status"] == "no_evidence"
    assert missing_detail_response["row"] is None
    assert missing_detail_response["citations"] == []

    print(
        json.dumps(
            {
                "source_checksum": source_checksum,
                "source": first["source"]["slug"],
                "dataset": first["dataset"]["slug"],
                "rows": len(summary["rows"]),
                "headline": summary["headline_row"]["external_id"],
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
