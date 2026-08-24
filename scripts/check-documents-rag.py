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
from app.documents_rag import (  # noqa: E402
    build_query_response,
    index_document_bundle,
    load_fixture_bundle,
    normalize_text,
    payload_hash,
    query_documents,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the documents and RAG slice.")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "documents" / "candex_2026_official_page.json",
        help="Path to the official document fixture bundle.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = load_fixture_bundle(args.fixture)
    source_checksum = payload_hash(bundle)

    with db_connection() as connection:
        indexing = index_document_bundle(connection, bundle)

        stored_counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM documents WHERE source_id = %s AND external_id = %s) AS document_count,
                (SELECT COUNT(*) FROM document_versions WHERE document_id = %s) AS version_count,
                (SELECT COUNT(*) FROM document_chunks WHERE document_version_id = %s) AS chunk_count
            """,
            (
                indexing["source"]["id"],
                bundle["document"]["external_id"],
                indexing["document"]["id"],
                indexing["version"]["id"],
            ),
        ).fetchone()
        stored_counts = dict(stored_counts)

        assert stored_counts["document_count"] == 1
        assert stored_counts["version_count"] == 1
        assert stored_counts["chunk_count"] == len(bundle["version"]["chunks"])

        query_results: list[dict[str, object]] = []
        for check in bundle["checks"]:
            response = query_documents(connection, check["question"], limit=3)
            query_results.append(response)
            assert response["status"] == "ok"
            assert response["answer"] is not None
            expected_fragment = normalize_text(check["expected_fragment"]).casefold()
            normalized_answer = normalize_text(response["answer"]).casefold()
            assert expected_fragment in normalized_answer
            assert response["citations"], "expected at least one citation"
            assert any(
                expected_fragment in normalize_text(citation["quote"]).casefold()
                for citation in response["citations"]
            )

        for check in bundle.get("negative_checks", []):
            response = query_documents(connection, check["question"], limit=3)
            assert response["status"] == check.get("expected_status", "no_evidence")
            assert response["answer"] is None
            assert not response["citations"]
            assert not response["evidence"]

    print(
        json.dumps(
            {
                "source_checksum": source_checksum,
                "document": bundle["document"]["external_id"],
                "chunks_indexed": indexing["chunks_indexed"],
                "queries": [
                    {
                        "question": check["question"],
                        "answer": query_results[index]["answer"],
                        "citation_count": len(query_results[index]["citations"]),
                    }
                    for index, check in enumerate(bundle["checks"])
                ],
                "negative_checks": [
                    {
                        "question": check["question"],
                        "expected_status": check.get("expected_status", "no_evidence"),
                    }
                    for check in bundle.get("negative_checks", [])
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
