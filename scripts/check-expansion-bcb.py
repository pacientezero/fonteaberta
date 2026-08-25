#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from decimal import Decimal

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.bcb_expansion import (  # noqa: E402
    fetch_series_summary,
    ingest_official_bundle,
    load_fixture_bundle,
    payload_hash,
    query_observation_response,
)
from app.db import db_connection  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the BCB expansion slice.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "bcb" / "selic_2024.json",
        help="Path to the official BCB fixture bundle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = load_fixture_bundle(args.fixture)
    source_checksum = payload_hash(bundle)

    with db_connection() as connection:
        first = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        second = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        summary = fetch_series_summary(connection, bundle["series"]["external_id"])
        present_response = query_observation_response(connection, "2024-12-31")
        missing_response = query_observation_response(connection, "2024-11-30")

        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM economic_series WHERE source_id = %s AND external_id = %s) AS series_count,
                (SELECT COUNT(*) FROM economic_observations WHERE economic_series_id = %s) AS observation_count,
                (SELECT COUNT(*) FROM raw_records WHERE source_id = %s AND external_id = %s) AS raw_record_count,
                (SELECT COUNT(*) FROM evidence WHERE source_id = %s AND external_id = %s) AS evidence_count,
                (SELECT COUNT(*) FROM facts WHERE subject_type = 'economic_series' AND subject_id = %s AND predicate = %s) AS fact_count,
                (SELECT COUNT(*) FROM facts WHERE subject_type = 'economic_series' AND subject_id = %s AND predicate = %s AND evidence_id = %s) AS fact_evidence_count,
                (SELECT COUNT(*) FROM claims WHERE subject_type = 'economic_series' AND subject_id = %s) AS claim_count,
                (SELECT COUNT(*) FROM claims_evidence WHERE claim_id = %s AND evidence_id = %s) AS claim_evidence_count
            """,
            (
                first["source"]["id"],
                bundle["series"]["external_id"],
                first["series"]["id"],
                first["source"]["id"],
                bundle["raw_record"]["external_id"],
                first["source"]["id"],
                bundle["evidence"]["external_id"],
                first["series"]["id"],
                "selic_rate_end_of_2024",
                first["series"]["id"],
                "selic_rate_end_of_2024",
                summary["evidence"]["id"],
                first["series"]["id"],
                summary["claim"]["id"],
                summary["evidence"]["id"],
            ),
        ).fetchone()
        counts = dict(counts)

    expected_first = bundle["series"]["observations"][0]["valor"]
    expected_last = bundle["series"]["observations"][-1]["valor"]
    expected_statement = "A taxa Selic encerrou 2024 em 4,5513%."

    assert first["source"]["slug"] == "bcb"
    assert first["dataset"]["slug"] == "selic-sgs-11-2024"
    assert first["series"]["external_id"] == "bcb-sgs-11"
    assert second["series"]["id"] == first["series"]["id"]
    assert counts["series_count"] == 1
    assert counts["observation_count"] == len(bundle["series"]["observations"])
    assert counts["raw_record_count"] == 1
    assert counts["evidence_count"] == 1
    assert counts["fact_count"] == 1
    assert counts["fact_evidence_count"] == 1
    assert counts["claim_count"] == 1
    assert counts["claim_evidence_count"] == 1
    assert summary["latest_value_formatted"] == "4,5513%"
    assert summary["fact"]["value_text"] == "4,5513%"
    assert summary["fact"]["evidence_id"] == summary["evidence"]["id"]
    assert summary["claim"]["statement"] == expected_statement
    assert first["claim_evidence"]["claim_id"] == summary["claim"]["id"]
    assert first["claim_evidence"]["evidence_id"] == summary["evidence"]["id"]
    assert summary["raw_record"]["payload_hash"] == source_checksum
    assert summary["raw_record"]["collected_at"] is not None
    assert summary["evidence"]["source_url"] == bundle["evidence"]["source_url"]
    assert str(summary["observations"][0]["observation_date"]) == "2024-12-02"
    assert str(summary["observations"][-1]["observation_date"]) == "2024-12-31"
    assert summary["observations"][0]["value"] == Decimal("0.041957")
    assert summary["observations"][-1]["value"] == Decimal("0.045513")
    assert summary["observations"][0]["value"] == first["observations"][0]["value"]
    assert summary["observations"][-1]["value"] == first["observations"][-1]["value"]
    assert bundle["series"]["observations"][0]["valor"] == expected_first
    assert bundle["series"]["observations"][-1]["valor"] == expected_last
    assert present_response["status"] == "ok"
    assert present_response["value_formatted"] == "4,5513%"
    assert present_response["payload_hash"] == source_checksum
    assert present_response["source_url"] == bundle["evidence"]["source_url"]
    assert missing_response["status"] == "no_evidence"
    assert missing_response["value"] is None
    assert missing_response["citations"] == []

    print(
        json.dumps(
            {
                "source_checksum": source_checksum,
                "source": first["source"]["slug"],
                "dataset": first["dataset"]["slug"],
                "series": first["series"]["external_id"],
                "observations": len(summary["observations"]),
                "latest_value_formatted": summary["latest_value_formatted"],
                "claim": summary["claim"]["statement"],
                "present_response": present_response["status"],
                "missing_response": missing_response["status"],
                "counts": counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
