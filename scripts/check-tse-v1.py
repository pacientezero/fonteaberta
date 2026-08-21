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
from app.tse_v1 import fetch_candidate_summary, ingest_official_bundle, load_fixture_bundle, payload_hash  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the TSE V1 vertical slice.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "tse" / "official_2026_presidential_bundle.json",
        help="Path to the official TSE fixture bundle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = load_fixture_bundle(args.fixture)
    source_checksum = payload_hash(bundle)

    with db_connection() as connection:
        ingest_official_bundle(connection, bundle, source_checksum_value=source_checksum)
        summary = fetch_candidate_summary(connection, bundle["candidate"]["SQ_CANDIDATO"])

    expected_total = "795089.00"
    expected_total_brl = "R$ 795.089,00"

    assert summary["source"]["name"] == "Tribunal Superior Eleitoral"
    assert summary["source"]["slug"] == "tse"
    assert {dataset["slug"] for dataset in summary["datasets"]} == {"candidatos-2026", "bens-candidato-2026"}
    assert summary["candidate"]["external_id"] == "280002540694"
    assert summary["candidate"]["declared_assets_total"] == expected_total
    assert summary["declared_assets_total"]["value"] == expected_total
    assert summary["declared_assets_total"]["formatted"] == expected_total_brl
    assert summary["declared_assets_total"]["asset_count"] == 4
    assert summary["claim"]["statement"] == f"Patrimônio declarado: {expected_total_brl}"
    assert len(summary["assets"]) == 4
    assert len(summary["provenance"]["claim_evidence"]) == 5

    print(
        json.dumps(
            {
                "candidate": summary["candidate"]["external_id"],
                "declared_assets_total": summary["declared_assets_total"],
                "claim": summary["claim"]["statement"],
                "source": summary["source"]["name"],
                "datasets": [dataset["slug"] for dataset in summary["datasets"]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
