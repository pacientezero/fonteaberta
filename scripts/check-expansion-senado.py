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

from app.db import db_connection  # noqa: E402
from app.senado_expansion import (  # noqa: E402
    fetch_mandate_summary,
    ingest_official_bundle,
    load_fixture_bundle,
    payload_hash,
    parse_br_datetime,
    query_mandate_response,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Senate expansion slice.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "senado" / "senadores_em_exercicio_57.json",
        help="Path to the official Senate fixture bundle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = load_fixture_bundle(args.fixture)
    source_checksum = payload_hash(bundle["snapshot"])

    with db_connection() as connection:
        first = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        second = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        sample_mandate_external_id = first["mandates"][0]["external_id"]
        snapshot_date = parse_br_datetime(bundle["snapshot"]["ListaParlamentarEmExercicio"]["Metadados"]["Versao"]).date()
        summary = fetch_mandate_summary(connection, sample_mandate_external_id)
        present_response = query_mandate_response(connection, sample_mandate_external_id)
        missing_response = query_mandate_response(connection, "senado-mandato-999999-exercicio-999999")
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
                (SELECT COUNT(*) FROM facts
                 WHERE subject_type = 'person'
                   AND subject_id IN (%s, %s)
                   AND predicate = 'current_mandate'
                   AND evidence_id = %s) AS fact_evidence_count,
                (SELECT COUNT(*) FROM claims
                 WHERE subject_type = 'person'
                   AND subject_id IN (%s, %s)
                   AND claim_type = 'official_fact') AS claim_count,
                (SELECT COUNT(*) FROM claims_evidence
                 WHERE evidence_id = %s) AS claim_evidence_count,
                (SELECT COUNT(*) FROM mandates WHERE source_id = %s AND dataset_id = %s AND party_id IS NOT NULL) AS resolved_party_count
            """,
            (
                first["source"]["id"],
                first["dataset"]["id"],
                first["source"]["id"],
                str(bundle["selected_parliamentarians"][0]["list_row"]["IdentificacaoParlamentar"]["CodigoParlamentar"]),
                str(bundle["selected_parliamentarians"][1]["list_row"]["IdentificacaoParlamentar"]["CodigoParlamentar"]),
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
                first["evidence"]["id"],
                first["people"][0]["id"],
                first["people"][1]["id"],
                first["evidence"]["id"],
                first["source"]["id"],
                first["dataset"]["id"],
            ),
        ).fetchone()
        counts = dict(counts)

    expected_statement = (
        f"Em {snapshot_date:%d/%m/%Y}, "
        f"{bundle['selected_parliamentarians'][0]['list_row']['IdentificacaoParlamentar']['NomeCompletoParlamentar']} "
        f"constava como senador em exercício pela 57ª legislatura."
    )

    assert first["source"]["slug"] == "senado"
    assert first["dataset"]["slug"] == "senadores-em-exercicio-57"
    assert second["ingestion_run"]["id"] == first["ingestion_run"]["id"]
    assert counts["mandate_count"] == len(bundle["selected_parliamentarians"])
    assert counts["person_count"] == len(bundle["selected_parliamentarians"])
    assert counts["raw_record_count"] == 1
    assert counts["evidence_count"] == 1
    assert counts["fact_count"] == len(bundle["selected_parliamentarians"])
    assert counts["fact_evidence_count"] == len(bundle["selected_parliamentarians"])
    assert counts["claim_count"] == len(bundle["selected_parliamentarians"])
    assert counts["claim_evidence_count"] == len(bundle["selected_parliamentarians"])
    assert counts["resolved_party_count"] == 0
    assert summary["mandate_external_id"] == sample_mandate_external_id
    assert summary["claim_statement"] == expected_statement
    assert summary["fact_value_text"] == "Alan Rick"
    assert summary["raw_record_payload_hash"] == source_checksum
    assert summary["evidence_source_url"] == bundle["evidence"]["source_url"]
    assert len(first["facts"]) == len(bundle["selected_parliamentarians"])
    assert len(first["claims"]) == len(bundle["selected_parliamentarians"])
    assert len(first["claim_evidences"]) == len(bundle["selected_parliamentarians"])
    assert all(fact["evidence_id"] == first["evidence"]["id"] for fact in first["facts"])
    assert {item["claim_id"] for item in first["claim_evidences"]} == {claim["id"] for claim in first["claims"]}
    assert {item["evidence_id"] for item in first["claim_evidences"]} == {first["evidence"]["id"]}
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
                "selected_parliamentarians": len(bundle["selected_parliamentarians"]),
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
