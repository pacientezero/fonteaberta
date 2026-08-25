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

from app.camara_legislative import (  # noqa: E402
    fetch_vote_summary,
    ingest_official_bundle,
    ingest_recent_official_votes,
    load_fixture_bundle,
    payload_hash_value,
    query_proposition_response,
    query_recent_votes_response,
    query_vote_response,
)
from app.db import db_connection  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Câmara legislative voting slice.")
    parser.add_argument(
        "--recent",
        action="store_true",
        help="Fetch and ingest recent nominal votes from the official Câmara API.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="How many recent nominal votes to ingest in --recent mode.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=4,
        help="How many official pages to scan in --recent mode.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "camara" / "legislative_plp230_2025_vote_2580259_24.json",
        help="Path to the official Câmara legislative fixture bundle.",
    )
    return parser.parse_args()


def run_recent_mode(connection, limit: int, pages: int) -> None:
    ingested = ingest_recent_official_votes(connection, limit=limit, pages=pages)
    catalog = query_recent_votes_response(connection, limit=limit)
    nominal_count = sum(1 for item in catalog["votes"] if item["member_count"] > 0)
    symbolic_count = sum(1 for item in catalog["votes"] if item["member_count"] == 0)

    assert len(ingested) >= limit
    assert catalog["status"] == "ok"
    assert catalog["count"] == len(catalog["votes"])
    assert catalog["count"] >= limit
    assert nominal_count + symbolic_count == catalog["count"]
    assert len({item["proposition"]["external_id"] for item in catalog["votes"]}) >= 2
    assert nominal_count >= 1
    assert symbolic_count >= 1

    print(
        json.dumps(
            {
                "mode": "recent",
                "ingested_votes": len(ingested),
                "catalog_count": catalog["count"],
                "votes": [
                    {
                        "vote": item["vote"]["external_id"],
                        "proposition": item["proposition"]["external_id"],
                        "members": item["member_count"],
                    }
                    for item in catalog["votes"]
                ],
                "nominal_count": nominal_count,
                "symbolic_count": symbolic_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def run_fixture_mode(connection, fixture_path: Path) -> None:
    bundle = load_fixture_bundle(fixture_path)
    source_checksum = payload_hash_value(bundle)

    result = ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
    summary = fetch_vote_summary(connection, bundle["vote"]["id"])
    vote_response = query_vote_response(connection, bundle["vote"]["id"])
    proposition_response = query_proposition_response(connection, str(bundle["proposition"]["id"]))

    expected_yes = 333
    expected_no = 91
    expected_other = 1
    expected_counted = 424
    expected_members = 425

    assert result["source"]["slug"] == "camara"
    assert result["proposition"]["external_id"] == "2580259"
    assert result["counts"]["yes_votes"] == expected_yes
    assert result["counts"]["no_votes"] == expected_no
    assert result["counts"]["other_votes"] == expected_other
    assert result["counts"]["total_votes"] == expected_counted
    assert result["counts"]["member_count"] == expected_members
    assert summary["vote"]["approved"] is True
    assert summary["vote"]["yes_votes"] == expected_yes
    assert summary["vote"]["no_votes"] == expected_no
    assert summary["vote"]["other_votes"] == expected_other
    assert summary["vote"]["total_votes"] == expected_counted
    assert len(summary["members"]) == expected_members
    assert summary["claim"]["statement"] == bundle["vote"]["descricao"]
    assert vote_response["status"] == "ok"
    assert len(vote_response["vote"]["members"]) == expected_members
    assert proposition_response["status"] == "ok"
    assert proposition_response["proposition"]["external_id"] == "2580259"
    assert len(proposition_response["votes"]) == 1

    print(
        json.dumps(
            {
                "mode": "fixture",
                "source_checksum": source_checksum,
                "proposition": summary["proposition"]["external_id"],
                "vote": summary["vote"]["external_id"],
                "yes_votes": summary["vote"]["yes_votes"],
                "no_votes": summary["vote"]["no_votes"],
                "other_votes": summary["vote"]["other_votes"],
                "members": len(summary["members"]),
                "claim": summary["claim"]["statement"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    args = parse_args()

    with db_connection() as connection:
        if args.recent:
            run_recent_mode(connection, limit=args.limit, pages=args.pages)
        else:
            run_fixture_mode(connection, args.fixture)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
