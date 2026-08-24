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

from app.camara_expansion import (  # noqa: E402
    fetch_mandate_summary,
    ingest_official_bundle,
    load_fixture_bundle,
    payload_hash_value,
    query_mandate_response,
)
from app.db import db_connection  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Câmara expansion slice.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "camara" / "deputados_legislatura_57.json",
        help="Path to the official Câmara fixture bundle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = load_fixture_bundle(args.fixture)
    source_checksum = payload_hash_value(bundle["snapshot"])

    with db_connection() as connection:
        first = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        second = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        sample_external_id = first["mandates"][0]["external_id"]
        summary = fetch_mandate_summary(connection, sample_external_id)
        present_response = query_mandate_response(
            connection,
            str(bundle["selected_deputies"][0]["detail"]["ultimoStatus"]["id"]),
            bundle["selected_deputies"][0]["detail"]["ultimoStatus"]["idLegislatura"],
        )
        missing_response = query_mandate_response(connection, "999999", 57)
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM mandates WHERE source_id = %s AND dataset_id = %s) AS mandate_count,
                (SELECT COUNT(*) FROM people AS p
                 JOIN entity_aliases AS ea ON ea.entity_id = p.id
                 WHERE ea.source_id = %s
                   AND ea.entity_type = 'person'
                   AND ea.external_id IN (%s, %s)) AS person_count,
                (SELECT COUNT(*) FROM raw_records WHERE source_id = %s AND dataset_id = %s AND external_id = %s) AS raw_record_count,
                (SELECT COUNT(*) FROM evidence WHERE source_id = %s AND dataset_id = %s AND external_id = %s) AS evidence_count,
                (SELECT COUNT(*) FROM facts
                 WHERE subject_type = 'person'
                   AND subject_id IN (%s, %s)
                   AND predicate = 'current_mandate') AS fact_count,
                (SELECT COUNT(*) FROM claims
                 WHERE subject_type = 'person'
                   AND subject_id IN (%s, %s)
                   AND claim_type = 'official_fact') AS claim_count,
                (SELECT COUNT(*) FROM mandates WHERE source_id = %s AND dataset_id = %s AND party_id IS NOT NULL) AS resolved_party_count
            """,
            (
                first["source"]["id"],
                first["dataset"]["id"],
                first["source"]["id"],
                str(bundle["selected_deputies"][0]["detail"]["ultimoStatus"]["id"]),
                str(bundle["selected_deputies"][1]["detail"]["ultimoStatus"]["id"]),
                first["source"]["id"],
                first["dataset"]["id"],
                bundle["raw_record"]["external_id"],
                first["source"]["id"],
                first["dataset"]["id"],
                bundle["evidence"]["external_id"],
                first["people"][0]["id"],
                first["people"][1]["id"],
                first["people"][0]["id"],
                first["people"][1]["id"],
                first["source"]["id"],
                first["dataset"]["id"],
            ),
        ).fetchone()
        counts = dict(counts)

    expected_statement = "ARLINDO CHIGNALIA JUNIOR exerce mandato de deputado federal pela Câmara dos Deputados na 57ª legislatura."

    assert first["source"]["slug"] == "camara"
    assert first["dataset"]["slug"] == "deputados-legislatura-57"
    assert second["ingestion_run"]["id"] == first["ingestion_run"]["id"]
    assert counts["mandate_count"] == len(bundle["selected_deputies"])
    assert counts["person_count"] == len(bundle["selected_deputies"])
    assert counts["raw_record_count"] == 1
    assert counts["evidence_count"] == 1
    assert counts["fact_count"] == len(bundle["selected_deputies"])
    assert counts["claim_count"] == len(bundle["selected_deputies"])
    assert summary["mandate_external_id"] == sample_external_id
    assert summary["claim_statement"] == expected_statement
    assert summary["fact_value_text"] == "Arlindo Chinaglia"
    assert summary["raw_record_payload_hash"] == source_checksum
    assert summary["evidence_source_url"] == bundle["evidence"]["source_url"]
    assert present_response["status"] == "ok"
    assert present_response["citations"]
    assert missing_response["status"] == "no_evidence"
    assert missing_response["citations"] == []

    print(
        json.dumps(
            {
                "source_checksum": source_checksum,
                "source": first["source"]["slug"],
                "dataset": first["dataset"]["slug"],
                "selected_deputies": len(bundle["selected_deputies"]),
                "mandate_count": counts["mandate_count"],
                "person_count": counts["person_count"],
                "resolved_party_count": counts["resolved_party_count"],
                "claim": summary["claim_statement"],
                "present_response": present_response["status"],
                "missing_response": missing_response["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
