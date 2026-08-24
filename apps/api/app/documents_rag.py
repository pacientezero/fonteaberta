from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from psycopg.types.json import Jsonb

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "documents" / "candex_2026_official_page.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "documents" / "candex_2026_official_page.json"
DEFAULT_EMBEDDING_DIMENSIONS = 384
DEFAULT_SOURCE_SLUG = "tse"
DEFAULT_DOCUMENT_EXTERNAL_ID = "candex-2026"
DEFAULT_DOCUMENT_TYPE = "official_page"
WORD_RE = re.compile(r"[0-9A-Za-zÀ-ÿ]+", re.UNICODE)
BLANK_LINE_RE = re.compile(r"\n\s*\n+", re.UNICODE)
CONTENT_STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "for",
    "ha",
    "há",
    "i",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "para",
    "por",
    "que",
    "quem",
    "qual",
    "quais",
    "se",
    "sem",
    "ser",
    "sua",
    "suas",
    "the",
    "to",
    "um",
    "uma",
    "with",
}


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(stripped.split())


def tokenize(value: str | None) -> list[str]:
    normalized = normalize_text(value).casefold()
    return WORD_RE.findall(normalized)


def content_terms(value: str | None) -> list[str]:
    return [token for token in tokenize(value) if token not in CONTENT_STOPWORDS]


def token_count(value: str | None) -> int:
    return len(tokenize(value))


def chunk_text(value: str, *, max_chars: int = 900) -> list[dict[str, Any]]:
    paragraphs = [paragraph.strip() for paragraph in BLANK_LINE_RE.split(value.strip()) if paragraph.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        normalized = " ".join(paragraph.split())
        if current and current_length + len(normalized) + 2 > max_chars:
            chunks.append("\n\n".join(current))
            current = [normalized]
            current_length = len(normalized)
            continue
        current.append(normalized)
        current_length += len(normalized) + 2

    if current:
        chunks.append("\n\n".join(current))

    results: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        results.append(
            {
                "chunk_index": index,
                "page": 1,
                "section": None,
                "content": chunk,
                "token_count": token_count(chunk),
                "metadata": {
                    "chunking_strategy": "blank_line",
                    "max_chars": max_chars,
                },
            }
        )
    return results


def hashed_embedding(value: str, *, dimensions: int = DEFAULT_EMBEDDING_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(value):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(digest, 16) % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(component * component for component in vector)) or 1.0
    return [round(component / norm, 8) for component in vector]


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _fetch_one(conn, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
    row = conn.execute(query, params).fetchone()
    if row is None:
        raise RuntimeError("Expected row not found")
    return dict(row)


def _fetch_optional(conn, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return dict(row)


def ensure_source(conn, source_payload: Mapping[str, Any]) -> dict[str, Any]:
    existing = _fetch_optional(
        conn,
        """
        SELECT id, name, slug, institution, description, base_url, documentation_url,
               source_type, scope, official, update_frequency, license, enabled, metadata,
               created_at, updated_at
        FROM sources
        WHERE slug = %s
        LIMIT 1
        """,
        (source_payload["slug"],),
    )
    if existing is not None:
        return existing

    metadata = dict(source_payload.get("metadata") or {})
    return _fetch_one(
        conn,
        """
        INSERT INTO sources (
            name,
            slug,
            institution,
            description,
            base_url,
            documentation_url,
            source_type,
            scope,
            official,
            update_frequency,
            license,
            enabled,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, name, slug, institution, description, base_url, documentation_url,
                  source_type, scope, official, update_frequency, license, enabled, metadata,
                  created_at, updated_at
        """,
        (
            source_payload["name"],
            source_payload["slug"],
            source_payload.get("institution"),
            source_payload.get("description"),
            source_payload.get("base_url"),
            source_payload.get("documentation_url"),
            source_payload.get("source_type", "official_registry"),
            source_payload.get("scope", "federal"),
            bool(source_payload.get("official", True)),
            source_payload.get("update_frequency", "daily"),
            source_payload.get("license", "open data"),
            bool(source_payload.get("enabled", True)),
            Jsonb(metadata),
        ),
    )


def upsert_document(conn, source_id: str, document_payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(document_payload.get("metadata") or {})
    return _fetch_one(
        conn,
        """
        INSERT INTO documents (
            source_id,
            entity_type,
            entity_id,
            document_type,
            title,
            description,
            external_id,
            source_url,
            published_at,
            mime_type,
            latest_version_id,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            entity_type = EXCLUDED.entity_type,
            entity_id = EXCLUDED.entity_id,
            document_type = EXCLUDED.document_type,
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            source_url = EXCLUDED.source_url,
            published_at = EXCLUDED.published_at,
            mime_type = EXCLUDED.mime_type,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING id, source_id, entity_type, entity_id, document_type, title, description,
                  external_id, source_url, published_at, mime_type, latest_version_id, metadata,
                  created_at, updated_at
        """,
        (
            source_id,
            document_payload.get("entity_type"),
            document_payload.get("entity_id"),
            document_payload["document_type"],
            document_payload["title"],
            document_payload.get("description"),
            document_payload["external_id"],
            document_payload["source_url"],
            parse_iso_datetime(document_payload.get("published_at")),
            document_payload["mime_type"],
            Jsonb(metadata),
        ),
    )


def upsert_document_version(conn, document_id: str, version_payload: Mapping[str, Any]) -> dict[str, Any]:
    version_number = int(version_payload.get("version_number", 1))
    text_content = version_payload.get("text_content", "")
    sha256 = version_payload.get("sha256") or hashlib.sha256(text_content.encode("utf-8")).hexdigest()
    file_path = version_payload.get("file_path")
    file_url = version_payload.get("file_url")
    source_updated_at = parse_iso_datetime(version_payload.get("source_updated_at"))
    collected_at = parse_iso_datetime(version_payload.get("collected_at")) or datetime.now(timezone.utc)
    metadata = dict(version_payload.get("metadata") or {})

    existing = _fetch_optional(
        conn,
        """
        SELECT id, document_id, version_number, file_path, file_url, sha256, text_content,
               collected_at, source_updated_at, metadata, created_at, updated_at
        FROM document_versions
        WHERE document_id = %s
          AND version_number = %s
        LIMIT 1
        """,
        (document_id, version_number),
    )
    if existing is not None:
        if existing["sha256"] != sha256 or existing["text_content"] != text_content:
            raise ValueError(
                f"Document version {version_number} for {document_id} already exists with different content"
            )
        return existing

    return _fetch_one(
        conn,
        """
        INSERT INTO document_versions (
            document_id,
            version_number,
            file_path,
            file_url,
            sha256,
            text_content,
            collected_at,
            source_updated_at,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, document_id, version_number, file_path, file_url, sha256, text_content,
                  collected_at, source_updated_at, metadata, created_at, updated_at
        """,
        (
            document_id,
            version_number,
            file_path,
            file_url,
            sha256,
            text_content,
            collected_at,
            source_updated_at,
            Jsonb(metadata),
        ),
    )


def replace_document_chunks(
    conn,
    *,
    document_id: str,
    document_version_id: str,
    chunks: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    conn.execute(
        "DELETE FROM document_chunks WHERE document_version_id = %s",
        (document_version_id,),
    )

    inserted: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        content = " ".join(str(chunk.get("content", "")).split())
        page = chunk.get("page")
        section = chunk.get("section")
        metadata = dict(chunk.get("metadata") or {})
        token_count_value = int(chunk.get("token_count") or token_count(content))
        embedding = vector_literal(hashed_embedding(content))
        inserted.append(
            _fetch_one(
                conn,
                """
                INSERT INTO document_chunks (
                    document_id,
                    document_version_id,
                    chunk_index,
                    page,
                    section,
                    content,
                    embedding,
                    token_count,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, (%s)::vector, %s, %s)
                RETURNING id, document_id, document_version_id, chunk_index, page, section,
                          content, token_count, metadata, created_at
                """,
                (
                    document_id,
                    document_version_id,
                    int(chunk.get("chunk_index", index)),
                    page,
                    section,
                    content,
                    embedding,
                    token_count_value,
                    Jsonb(metadata),
                ),
            )
        )
    return inserted


def index_document_bundle(conn, bundle: Mapping[str, Any]) -> dict[str, Any]:
    source = ensure_source(conn, bundle["source"])
    document = upsert_document(conn, source["id"], bundle["document"])
    version = upsert_document_version(conn, document["id"], bundle["version"])
    version_chunks = bundle["version"].get("chunks")
    chunks = version_chunks if version_chunks else chunk_text(bundle["version"]["text_content"])
    inserted_chunks = replace_document_chunks(
        conn,
        document_id=document["id"],
        document_version_id=version["id"],
        chunks=chunks,
    )
    document = _fetch_one(
        conn,
        """
        UPDATE documents
        SET latest_version_id = %s,
            updated_at = now()
        WHERE id = %s
        RETURNING id, source_id, entity_type, entity_id, document_type, title, description,
                  external_id, source_url, published_at, mime_type, latest_version_id, metadata,
                  created_at, updated_at
        """,
        (version["id"], document["id"]),
    )
    return {
        "source": source,
        "document": document,
        "version": version,
        "chunks_indexed": len(inserted_chunks),
        "chunks": inserted_chunks,
    }


def resolve_query_scope(question: str) -> dict[str, Any]:
    normalized_question = normalize_text(question).casefold()
    tokens = tokenize(question)
    candidate_markers = {
        "candex",
        "candidatura",
        "candidaturas",
        "registro",
        "drap",
        "partido",
        "federação",
        "convencao",
        "convenção",
        "atas",
    }
    if any(marker in normalized_question for marker in candidate_markers):
        return {
            "source_slug": DEFAULT_SOURCE_SLUG,
            "document_external_id": DEFAULT_DOCUMENT_EXTERNAL_ID,
            "document_type": DEFAULT_DOCUMENT_TYPE,
            "keywords": tokens,
        }
    return {
        "source_slug": DEFAULT_SOURCE_SLUG,
        "document_external_id": DEFAULT_DOCUMENT_EXTERNAL_ID,
        "document_type": DEFAULT_DOCUMENT_TYPE,
        "keywords": tokens,
    }


def search_document_chunks(
    conn,
    question: str,
    *,
    limit: int = 5,
    scope: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    scope = dict(scope or resolve_query_scope(question))
    query_vector = vector_literal(hashed_embedding(question))

    rows = conn.execute(
        """
        SELECT
            dc.id,
            dc.document_id,
            dc.document_version_id,
            dc.chunk_index,
            dc.page,
            dc.section,
            dc.content,
            dc.token_count,
            dc.metadata,
            d.title AS document_title,
            d.description AS document_description,
            d.external_id AS document_external_id,
            d.document_type,
            d.source_url,
            s.name AS source_name,
            s.slug AS source_slug,
            dv.version_number,
            dv.sha256,
            dc.embedding <=> (%s)::vector AS distance
        FROM document_chunks AS dc
        JOIN document_versions AS dv ON dv.id = dc.document_version_id
        JOIN documents AS d ON d.id = dc.document_id
        JOIN sources AS s ON s.id = d.source_id
        WHERE s.slug = %s
          AND d.external_id = %s
        ORDER BY dc.embedding <=> (%s)::vector
        LIMIT %s
        """,
        (query_vector, scope["source_slug"], scope["document_external_id"], query_vector, limit),
    ).fetchall()

    query_tokens = set(tokenize(question))
    query_content_tokens = set(content_terms(question))
    results: list[dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row)
        content_tokens = set(tokenize(row_dict["content"]))
        content_terms_tokens = set(content_terms(row_dict["content"]))
        row_dict["lexical_overlap"] = len(query_tokens & content_tokens)
        row_dict["content_overlap"] = len(query_content_tokens & content_terms_tokens)
        results.append(row_dict)

    results.sort(
        key=lambda row: (
            -row["content_overlap"],
            -row["lexical_overlap"],
            row["distance"],
            row["chunk_index"],
        )
    )
    return results


def build_query_response(
    question: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    if not candidates:
        return {
            "question": question,
            "answer": None,
            "citations": [],
            "evidence": [],
            "resolved_scope": dict(scope),
            "retrieval_mode": "hybrid-vector-lexical",
            "status": "no_evidence",
        }

    if max(int(candidate.get("content_overlap") or 0) for candidate in candidates) == 0:
        return {
            "question": question,
            "answer": None,
            "citations": [],
            "evidence": [],
            "resolved_scope": dict(scope),
            "retrieval_mode": "hybrid-vector-lexical",
            "status": "no_evidence",
        }

    answer = candidates[0]["content"].strip()
    citations: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for row in candidates[:3]:
        citation = {
            "document_id": row["document_id"],
            "document_title": row["document_title"],
            "document_type": row["document_type"],
            "source_name": row["source_name"],
            "source_slug": row["source_slug"],
            "source_url": row["source_url"],
            "page": row["page"],
            "section": row["section"],
            "chunk_index": row["chunk_index"],
            "quote": row["content"].strip(),
        }
        citations.append(citation)
        evidence.append(
            {
                "chunk_id": row["id"],
                "distance": row["distance"],
                "lexical_overlap": row["lexical_overlap"],
                "content_overlap": row["content_overlap"],
                "quote": row["content"].strip(),
            }
        )

    return {
        "question": question,
        "answer": answer,
        "citations": citations,
        "evidence": evidence,
        "resolved_scope": dict(scope),
        "retrieval_mode": "hybrid-vector-lexical",
        "status": "ok",
    }


def query_documents(conn, question: str, *, limit: int = 5) -> dict[str, Any]:
    scope = resolve_query_scope(question)
    candidates = search_document_chunks(conn, question, limit=limit, scope=scope)
    return build_query_response(question, candidates, scope=scope)
