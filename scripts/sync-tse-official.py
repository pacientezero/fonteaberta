#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from curl_cffi import requests
from psycopg.types.json import Jsonb

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db import db_connection  # noqa: E402
from app.tse_v1 import (  # noqa: E402
    ensure_tse_catalog,
    ingest_candidate_bundle,
    payload_hash,
)

TSE_CANDIDATE_ZIP_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2026.zip"
TSE_CANDIDATE_COMPLEMENTARY_ZIP_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand_complementar/consulta_cand_complementar_2026.zip"
)
TSE_ASSET_ZIP_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/bem_candidato_2026.zip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync the official TSE 2026 candidacy data.")
    parser.add_argument("--batch-size", type=int, default=250, help="Commit after this many candidates.")
    parser.add_argument("--force", action="store_true", help="Run even if a success checksum already exists.")
    return parser.parse_args()


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def download_zip(url: str) -> bytes:
    response = requests.get(url, impersonate="chrome120", timeout=300)
    response.raise_for_status()
    return response.content


def read_brasil_csv(zip_bytes: bytes, expected_prefix: str) -> tuple[str, list[dict[str, str]]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        matches = sorted(
            name
            for name in archive.namelist()
            if name.endswith("_BRASIL.csv") and expected_prefix in name
        )
        if not matches:
            raise RuntimeError(f"CSV BRASIL not found for {expected_prefix}")
        csv_name = matches[0]
        with archive.open(csv_name) as csv_file:
            payload = csv_file.read()
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                text = payload.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise UnicodeDecodeError("csv", payload, 0, len(payload), "unable to decode official TSE CSV")
        rows = list(csv.DictReader(io.StringIO(text), delimiter=';'))
    return csv_name, rows


def build_index(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key)
        if value:
            indexed[value] = row
    return indexed


def build_asset_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    indexed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        candidate_id = row.get("SQ_CANDIDATO")
        if candidate_id:
            indexed[candidate_id].append(row)
    for asset_rows in indexed.values():
        asset_rows.sort(key=lambda row: int(row.get("NR_ORDEM_BEM_CANDIDATO") or 0))
    return dict(indexed)


def ensure_ingestion_run(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    source_checksum: str,
    records_read: int,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    existing = conn.execute(
        """
        SELECT id, status
        FROM ingestion_runs
        WHERE source_id = %s
          AND dataset_id = %s
          AND pipeline = %s
          AND source_checksum = %s
          AND status = 'success'
        LIMIT 1
        """,
        (source_id, dataset_id, "connector-tse-v1", source_checksum),
    ).fetchone()
    if existing is not None:
        return dict(existing)

    row = conn.execute(
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
            metadata
        )
        VALUES (%s, %s, %s, %s, now(), NULL, %s, %s, 0, 0, 0, 0, %s, %s)
        RETURNING id, status
        """,
        (
            source_id,
            dataset_id,
            "connector-tse-v1",
            "official_full",
            "running",
            records_read,
            source_checksum,
            Jsonb(metadata),
        ),
    ).fetchone()
    return dict(row)


def main() -> int:
    args = parse_args()

    candidate_zip = download_zip(TSE_CANDIDATE_ZIP_URL)
    complementary_zip = download_zip(TSE_CANDIDATE_COMPLEMENTARY_ZIP_URL)
    asset_zip = download_zip(TSE_ASSET_ZIP_URL)

    candidate_zip_sha256 = sha256_hex(candidate_zip)
    complementary_zip_sha256 = sha256_hex(complementary_zip)
    asset_zip_sha256 = sha256_hex(asset_zip)

    candidate_csv, candidate_rows = read_brasil_csv(candidate_zip, "consulta_cand_2026")
    complementary_csv, complementary_rows = read_brasil_csv(complementary_zip, "consulta_cand_complementar_2026")
    asset_csv, asset_rows = read_brasil_csv(asset_zip, "bem_candidato_2026")

    candidate_by_id = build_index(candidate_rows, "SQ_CANDIDATO")
    complementary_by_id = build_index(complementary_rows, "SQ_CANDIDATO")
    assets_by_id = build_asset_index(asset_rows)

    source_checksum = payload_hash(
        {
            "candidate_zip_sha256": candidate_zip_sha256,
            "candidate_csv": candidate_csv,
            "complementary_zip_sha256": complementary_zip_sha256,
            "complementary_csv": complementary_csv,
            "asset_zip_sha256": asset_zip_sha256,
            "asset_csv": asset_csv,
            "candidate_rows": len(candidate_rows),
            "complementary_rows": len(complementary_rows),
            "asset_rows": len(asset_rows),
        }
    )

    bundle = {
        "metadata": {
            "portal_url": "https://dadosabertos.tse.jus.br/",
            "candidate_dataset_url": TSE_CANDIDATE_ZIP_URL,
            "complementary_dataset_url": TSE_CANDIDATE_COMPLEMENTARY_ZIP_URL,
            "asset_dataset_url": TSE_ASSET_ZIP_URL,
        }
    }

    with db_connection() as connection:
        catalog = ensure_tse_catalog(connection, bundle)
        source = catalog["source"]
        candidate_dataset = catalog["candidate_dataset"]
        complementary_dataset = catalog["complementary_dataset"]
        asset_dataset = catalog["asset_dataset"]

        records_read = len(candidate_rows) + len(complementary_rows) + len(asset_rows)
        ingestion_run = ensure_ingestion_run(
            connection,
            source_id=source["id"],
            dataset_id=candidate_dataset["id"],
            source_checksum=source_checksum,
            records_read=records_read,
            metadata={
                "candidate_csv": candidate_csv,
                "complementary_csv": complementary_csv,
                "asset_csv": asset_csv,
                "candidate_zip_sha256": candidate_zip_sha256,
                "complementary_zip_sha256": complementary_zip_sha256,
                "asset_zip_sha256": asset_zip_sha256,
                "candidate_rows": len(candidate_rows),
                "complementary_rows": len(complementary_rows),
                "asset_rows": len(asset_rows),
                "batch_size": args.batch_size,
            },
        )
        if ingestion_run.get("status") == "success" and not args.force:
            print(
                json.dumps(
                    {
                        "status": "already_synced",
                        "source_checksum": source_checksum,
                        "records_read": records_read,
                        "candidate_rows": len(candidate_rows),
                        "complementary_rows": len(complementary_rows),
                        "asset_rows": len(asset_rows),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        candidate_ids = sorted(candidate_by_id)
        started_at = time.perf_counter()
        processed = 0
        for candidate_id in candidate_ids:
            candidate_row = candidate_by_id[candidate_id]
            complementary_row = complementary_by_id.get(candidate_id)
            asset_rows_for_candidate = assets_by_id.get(candidate_id, [])
            ingest_candidate_bundle(
                connection,
                source=source,
                candidate_dataset=candidate_dataset,
                asset_dataset=asset_dataset,
                candidate_row=candidate_row,
                asset_rows=asset_rows_for_candidate,
                ingestion_run_id=ingestion_run["id"],
                candidate_dataset_url=TSE_CANDIDATE_ZIP_URL,
                asset_dataset_url=TSE_ASSET_ZIP_URL,
                complementary_dataset=complementary_dataset,
                complementary_dataset_url=TSE_CANDIDATE_COMPLEMENTARY_ZIP_URL,
                complementary_row=complementary_row,
            )
            processed += 1
            if processed % max(1, args.batch_size) == 0:
                connection.commit()

        connection.execute(
            """
            UPDATE ingestion_runs
            SET
                finished_at = now(),
                status = 'success',
                records_read = %s,
                records_created = %s,
                records_updated = 0,
                records_unchanged = 0,
                records_failed = 0
            WHERE id = %s
            """,
            (records_read, records_read, ingestion_run["id"]),
        )
        connection.commit()

    elapsed = time.perf_counter() - started_at
    print(
        json.dumps(
            {
                "status": "success",
                "source_checksum": source_checksum,
                "records_read": records_read,
                "candidate_rows": len(candidate_rows),
                "complementary_rows": len(complementary_rows),
                "asset_rows": len(asset_rows),
                "processed_candidates": processed,
                "elapsed_seconds": round(elapsed, 2),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
