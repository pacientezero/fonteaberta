from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote

from psycopg.types.json import Jsonb

from app.bcb_expansion import (
    _fetch_one,
    _fetch_optional,
    ensure_dataset,
    ensure_source,
    parse_iso_datetime,
    payload_hash,
    upsert_claim_evidence,
)

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "comprasgov" / "fornecedores_ativos_p01_t10.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "comprasgov" / "fornecedores_ativos_p01_t10.json"

COMPRASGOV_SOURCE_SLUG = "comprasgov"
COMPRASGOV_INSTITUTION = "Ministerio da Gestao e da Inovacao em Servicos Publicos"
COMPRASGOV_PORTAL_URL = "https://www.gov.br/compras/"
COMPRASGOV_API_DOCS_URL = "https://www.gov.br/compras/pt-br/cidadao/portal-de-dados-abertos"
COMPRASGOV_API_BASE_URL = "https://dadosabertos.compras.gov.br/"

COMPRASGOV_PAGE = 1
COMPRASGOV_PAGE_SIZE = 10
COMPRASGOV_ACTIVE = True
COMPRASGOV_DATASET_SLUG = "fornecedores-ativos-page-1"
COMPRASGOV_DATASET_EXTERNAL_ID = "comprasgov-fornecedores-page-1"
COMPRASGOV_ROW_SUBJECT_TYPE = "comprasgov_supplier_snapshot"
COMPRASGOV_ROW_SUMMARY_PREDICATE = "supplier_page_headline"


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y", "sim"}


def digits_only(value: Any) -> str:
    text = normalize_text(value) or ""
    return re.sub(r"\D+", "", text)


def build_source_payload() -> dict[str, Any]:
    return {
        "name": "Compras.gov.br / Dados Abertos",
        "slug": COMPRASGOV_SOURCE_SLUG,
        "institution": COMPRASGOV_INSTITUTION,
        "description": "Portal oficial de dados abertos do Compras.gov.br",
        "base_url": COMPRASGOV_API_BASE_URL,
        "documentation_url": COMPRASGOV_API_DOCS_URL,
        "source_type": "official_registry",
        "scope": "federal",
        "official": True,
        "update_frequency": "daily",
        "license": "open data",
        "enabled": True,
        "metadata": {
            "portal_url": COMPRASGOV_PORTAL_URL,
            "api_docs_url": COMPRASGOV_API_DOCS_URL,
            "api_base_url": COMPRASGOV_API_BASE_URL,
            "module": "fornecedor",
            "endpoint": "/modulo-fornecedor/1_consultarFornecedor",
        },
    }


def build_endpoint_url(page: int, page_size: int, active: bool) -> str:
    return (
        "https://dadosabertos.compras.gov.br/modulo-fornecedor/1_consultarFornecedor"
        f"?pagina={page}"
        f"&tamanhoPagina={page_size}"
        f"&ativo={'true' if active else 'false'}"
    )


def build_dataset_payload(bundle: Mapping[str, Any], page: int, page_size: int, active: bool) -> dict[str, Any]:
    first_row = bundle["resultado"][0]
    captured_at = parse_iso_datetime(bundle.get("captured_at")) or datetime.now(timezone.utc)
    snapshot_date = captured_at.date()
    supplier_name = normalize_text(first_row.get("nomeRazaoSocialFornecedor")) or "Fornecedor"
    return {
        "name": f"Fornecedores ativos - pagina {page}",
        "slug": COMPRASGOV_DATASET_SLUG,
        "external_id": COMPRASGOV_DATASET_EXTERNAL_ID,
        "format": "json",
        "resource_url": build_endpoint_url(page, page_size, active),
        "scope": "federal",
        "period_start": snapshot_date.isoformat(),
        "period_end": snapshot_date.isoformat(),
        "update_frequency": "daily",
        "enabled": True,
        "metadata": {
            "module": "fornecedor",
            "page": page,
            "page_size": page_size,
            "active": active,
            "source_items": len(bundle["resultado"]),
            "total_pages": bundle.get("totalPaginas"),
            "remaining_pages": bundle.get("paginasRestantes"),
            "supplier_name": supplier_name,
        },
    }


def row_signature(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "ativo": "1" if row.get("ativo") else "0",
        "cnpj": normalize_text(row.get("cnpj")) or "",
        "cpf": normalize_text(row.get("cpf")) or "",
        "habilitadoLicitar": "1" if row.get("habilitadoLicitar") else "0",
        "codigoCnae": str(row.get("codigoCnae") or ""),
        "nomeMunicipio": normalize_text(row.get("nomeMunicipio")) or "",
        "naturezaJuridicaId": str(row.get("naturezaJuridicaId") or ""),
        "naturezaJuridicaNome": normalize_text(row.get("naturezaJuridicaNome")) or "",
        "porteEmpresaId": str(row.get("porteEmpresaId") or ""),
        "porteEmpresaNome": normalize_text(row.get("porteEmpresaNome")) or "",
        "nomeRazaoSocialFornecedor": normalize_text(row.get("nomeRazaoSocialFornecedor")) or "",
        "ufSigla": normalize_text(row.get("ufSigla")) or "",
    }


def row_external_id(row: Mapping[str, Any]) -> str:
    cnpj = digits_only(row.get("cnpj"))
    if cnpj:
        return f"cnpj:{cnpj}"
    cpf = digits_only(row.get("cpf"))
    if cpf:
        return f"cpf:{cpf}"
    digest = hashlib.sha256(canonical_json_bytes(row_signature(row))).hexdigest()
    return f"comprasgov:fornecedor:{digest[:24]}"


def normalize_supplier_row(
    row: Mapping[str, Any],
    *,
    default_collected_at: datetime | None = None,
    default_source_updated_at: datetime | None = None,
) -> dict[str, Any]:
    payload = dict(row)
    cnpj = normalize_text(payload.get("cnpj"))
    cpf = normalize_text(payload.get("cpf"))
    normalized: dict[str, Any] = {
        "active": parse_bool(payload.get("ativo")),
        "cnpj": cnpj,
        "cpf": cpf,
        "identity_confidence": "strong" if cnpj else "weak",
        "licensed_to_bid": parse_bool(payload.get("habilitadoLicitar")),
        "cnae_code": int(payload["codigoCnae"]) if payload.get("codigoCnae") is not None else None,
        "cnae_name": normalize_text(payload.get("nomeCnae")),
        "municipality": normalize_text(payload.get("nomeMunicipio")),
        "nature_id": int(payload["naturezaJuridicaId"]) if payload.get("naturezaJuridicaId") is not None else None,
        "nature_name": normalize_text(payload.get("naturezaJuridicaNome")),
        "company_size_id": int(payload["porteEmpresaId"]) if payload.get("porteEmpresaId") is not None else None,
        "company_size_name": normalize_text(payload.get("porteEmpresaNome")),
        "supplier_name": normalize_text(payload.get("nomeRazaoSocialFornecedor")) or "",
        "uf": normalize_text(payload.get("ufSigla")),
        "raw_payload": payload,
        "metadata": dict(payload.get("metadata") or {}),
        "source_updated_at": parse_iso_datetime(payload.get("source_updated_at")) or default_source_updated_at,
        "collected_at": parse_iso_datetime(payload.get("collected_at")) or default_collected_at or datetime.now(timezone.utc),
    }
    normalized["external_id"] = normalize_text(payload.get("external_id")) or row_external_id(normalized)
    return normalized


def summary_statement(headline_row: Mapping[str, Any], *, page: int, page_size: int, active: bool) -> str:
    status = "ativos" if active else "inativos"
    return (
        f"Na pagina {page} do modulo Fornecedor do Compras.gov, o primeiro fornecedor {status} "
        f"retornado e {headline_row['supplier_name']}."
    )


def report_subject_id(page: int, page_size: int, active: bool) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"fonteaberta:comprasgov-fornecedor:{page}:{page_size}:{int(active)}",
    )


def ensure_ingestion_run(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    bundle: Mapping[str, Any],
    source_checksum_value: str | None,
    page: int,
    page_size: int,
    active: bool,
) -> dict[str, Any]:
    existing = _fetch_optional(
        conn,
        """
        SELECT id, source_id, dataset_id, pipeline, run_type, started_at, finished_at, status,
               records_read, records_created, records_updated, records_unchanged, records_failed,
               source_checksum, error_summary, metadata, created_at
        FROM ingestion_runs
        WHERE source_id = %s
          AND dataset_id = %s
          AND pipeline = %s
          AND source_checksum = %s
        LIMIT 1
        """,
        (source_id, dataset_id, "connector-comprasgov-expansion", source_checksum_value),
    )
    if existing is not None:
        return existing

    started_at = parse_iso_datetime(bundle.get("captured_at")) or datetime.now(timezone.utc)
    metadata = {
        "module": "fornecedor",
        "page": page,
        "page_size": page_size,
        "active": active,
        "total_pages": bundle.get("totalPaginas"),
        "remaining_pages": bundle.get("paginasRestantes"),
    }
    return _fetch_one(
        conn,
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
            error_summary,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, source_id, dataset_id, pipeline, run_type, started_at, finished_at, status,
                  records_read, records_created, records_updated, records_unchanged, records_failed,
                  source_checksum, error_summary, metadata, created_at
        """,
        (
            source_id,
            dataset_id,
            "connector-comprasgov-expansion",
            "full",
            started_at,
            started_at,
            "success",
            len(bundle["resultado"]),
            len(bundle["resultado"]),
            0,
            0,
            0,
            source_checksum_value,
            None,
            Jsonb(metadata),
        ),
    )


def upsert_raw_record(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    ingestion_run_id: str,
    bundle: Mapping[str, Any],
    source_checksum_value: str | None,
) -> dict[str, Any]:
    raw_payload = {
        "request": dict(bundle.get("request") or {}),
        "captured_at": bundle.get("captured_at"),
        "source_url": bundle.get("source_url"),
        "totalRegistros": bundle.get("totalRegistros"),
        "totalPaginas": bundle.get("totalPaginas"),
        "paginasRestantes": bundle.get("paginasRestantes"),
    }
    collected_at = parse_iso_datetime(bundle.get("captured_at")) or datetime.now(timezone.utc)
    metadata = dict(bundle.get("request") or {})
    return _fetch_one(
        conn,
        """
        INSERT INTO raw_records (
            source_id,
            dataset_id,
            ingestion_run_id,
            external_id,
            payload,
            payload_hash,
            source_updated_at,
            collected_at,
            processing_status,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, dataset_id, external_id) DO UPDATE
        SET
            ingestion_run_id = EXCLUDED.ingestion_run_id,
            payload = EXCLUDED.payload,
            payload_hash = EXCLUDED.payload_hash,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            processing_status = EXCLUDED.processing_status,
            metadata = EXCLUDED.metadata
        RETURNING id, source_id, dataset_id, ingestion_run_id, external_id, payload, payload_hash, source_updated_at, collected_at, processing_status, metadata, created_at
        """,
        (
            source_id,
            dataset_id,
            ingestion_run_id,
            COMPRASGOV_DATASET_EXTERNAL_ID,
            Jsonb(raw_payload),
            source_checksum_value or payload_hash(bundle),
            collected_at,
            collected_at,
            "normalized",
            Jsonb(metadata),
        ),
    )


def upsert_evidence(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    raw_record_id: str,
    page: int,
    page_size: int,
    active: bool,
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    source_url = build_endpoint_url(page, page_size, active)
    metadata = {
        "module": "fornecedor",
        "page": page,
        "page_size": page_size,
        "active": active,
    }
    return _fetch_one(
        conn,
        """
        INSERT INTO evidence (
            source_id,
            dataset_id,
            raw_record_id,
            external_id,
            source_url,
            page,
            section,
            collected_at,
            payload_hash,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, dataset_id, external_id) DO UPDATE
        SET
            raw_record_id = EXCLUDED.raw_record_id,
            source_url = EXCLUDED.source_url,
            page = EXCLUDED.page,
            section = EXCLUDED.section,
            collected_at = EXCLUDED.collected_at,
            payload_hash = EXCLUDED.payload_hash,
            metadata = EXCLUDED.metadata
        RETURNING id, source_id, dataset_id, raw_record_id, external_id, source_url, page, section, collected_at, payload_hash, metadata, created_at
        """,
        (
            source_id,
            dataset_id,
            raw_record_id,
            f"{COMPRASGOV_DATASET_EXTERNAL_ID}-evidence",
            source_url,
            page,
            "Fornecedor",
            parse_iso_datetime(bundle.get("captured_at")) or datetime.now(timezone.utc),
            payload_hash(bundle),
            Jsonb(metadata),
        ),
    )


def upsert_rows(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    bundle: Mapping[str, Any],
    default_collected_at: datetime | None = None,
    default_source_updated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    inserted: list[dict[str, Any]] = []
    insert_sql = """
        INSERT INTO comprasgov_supplier_records (
            source_id,
            dataset_id,
            external_id,
            active,
            cnpj,
            cpf,
            identity_confidence,
            licensed_to_bid,
            cnae_code,
            cnae_name,
            municipality,
            nature_id,
            nature_name,
            company_size_id,
            company_size_name,
            supplier_name,
            uf,
            source_updated_at,
            collected_at,
            raw_payload,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            dataset_id = EXCLUDED.dataset_id,
            active = EXCLUDED.active,
            cnpj = EXCLUDED.cnpj,
            cpf = EXCLUDED.cpf,
            identity_confidence = EXCLUDED.identity_confidence,
            licensed_to_bid = EXCLUDED.licensed_to_bid,
            cnae_code = EXCLUDED.cnae_code,
            cnae_name = EXCLUDED.cnae_name,
            municipality = EXCLUDED.municipality,
            nature_id = EXCLUDED.nature_id,
            nature_name = EXCLUDED.nature_name,
            company_size_id = EXCLUDED.company_size_id,
            company_size_name = EXCLUDED.company_size_name,
            supplier_name = EXCLUDED.supplier_name,
            uf = EXCLUDED.uf,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            raw_payload = EXCLUDED.raw_payload,
            metadata = EXCLUDED.metadata
        RETURNING id, source_id, dataset_id, external_id, active, cnpj, cpf, licensed_to_bid, cnae_code,
                  identity_confidence, cnae_name, municipality, nature_id, nature_name, company_size_id, company_size_name,
                  supplier_name, uf, source_updated_at, collected_at, raw_payload, metadata, created_at, updated_at
    """
    for index, raw_row in enumerate(bundle["resultado"], start=1):
        normalized = normalize_supplier_row(
            raw_row,
            default_collected_at=default_collected_at,
            default_source_updated_at=default_source_updated_at,
        )
        params = (
            source_id,
            dataset_id,
            normalized["external_id"],
            normalized["active"],
            normalized["cnpj"],
            normalized["cpf"],
            normalized["identity_confidence"],
            normalized["licensed_to_bid"],
            normalized["cnae_code"],
            normalized["cnae_name"],
            normalized["municipality"],
            normalized["nature_id"],
            normalized["nature_name"],
            normalized["company_size_id"],
            normalized["company_size_name"],
            normalized["supplier_name"],
            normalized["uf"],
            normalized["source_updated_at"],
            normalized["collected_at"],
            Jsonb(normalized["raw_payload"]),
            Jsonb({**normalized["metadata"], "line_index": index}),
        )
        inserted.append(_fetch_one(conn, insert_sql, params))
    return inserted


def headline_statement(headline_row: Mapping[str, Any], *, page: int) -> str:
    status = "ativo" if headline_row["active"] else "inativo"
    licitar = "habilitado a licitar" if headline_row["licensed_to_bid"] else "sem habilitacao para licitar"
    return (
        f"Na pagina {page} do modulo Fornecedor do Compras.gov, o fornecedor "
        f"{headline_row['supplier_name']} esta {status} e {licitar}."
    )


def report_subject_id(page: int, page_size: int, active: bool) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"fonteaberta:comprasgov-fornecedor:{page}:{page_size}:{int(active)}",
    )


def upsert_summary_fact(
    conn,
    *,
    source_id: str,
    evidence_id: str,
    page: int,
    page_size: int,
    active: bool,
    headline_row: Mapping[str, Any],
) -> dict[str, Any]:
    subject_id = report_subject_id(page, page_size, active)
    statement = headline_statement(headline_row, page=page)
    existing = _fetch_optional(
        conn,
        """
        SELECT id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric,
               value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method,
               metadata, created_at
        FROM facts
        WHERE subject_type = %s
          AND subject_id = %s
          AND predicate = %s
        LIMIT 1
        """,
        (COMPRASGOV_ROW_SUBJECT_TYPE, str(subject_id), COMPRASGOV_ROW_SUMMARY_PREDICATE),
    )
    if existing is not None:
        if existing["evidence_id"] != evidence_id:
            existing = _fetch_one(
                conn,
                """
                UPDATE facts
                SET evidence_id = %s
                WHERE id = %s
                RETURNING id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric,
                          value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method,
                          metadata, created_at
                """,
                (evidence_id, existing["id"]),
            )
        return existing

    metadata = {
        "page": page,
        "page_size": page_size,
        "active": active,
        "headline_external_id": headline_row["external_id"],
        "headline_cnpj": headline_row["cnpj"],
        "headline_supplier_name": headline_row["supplier_name"],
    }
    return _fetch_one(
        conn,
        """
        INSERT INTO facts (
            subject_type,
            subject_id,
            predicate,
            object_type,
            object_id,
            value_text,
            value_numeric,
            value_boolean,
            value_date,
            unit,
            effective_date,
            source_id,
            evidence_id,
            calculation_method,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric,
                  value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method,
                  metadata, created_at
        """,
        (
            COMPRASGOV_ROW_SUBJECT_TYPE,
            str(subject_id),
            COMPRASGOV_ROW_SUMMARY_PREDICATE,
            "text",
            None,
            statement,
            None,
            None,
            headline_row["collected_at"].date(),
            None,
            headline_row["collected_at"].date(),
            source_id,
            evidence_id,
            "headline_row",
            Jsonb(metadata),
        ),
    )


def upsert_summary_claim(
    conn,
    *,
    page: int,
    page_size: int,
    active: bool,
    fact_id: str,
    headline_row: Mapping[str, Any],
) -> dict[str, Any]:
    subject_id = report_subject_id(page, page_size, active)
    statement = headline_statement(headline_row, page=page)
    existing = _fetch_optional(
        conn,
        """
        SELECT id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider,
               model_name, metadata, created_at
        FROM claims
        WHERE subject_type = %s
          AND subject_id = %s
          AND statement = %s
        LIMIT 1
        """,
        (COMPRASGOV_ROW_SUBJECT_TYPE, str(subject_id), statement),
    )
    if existing is not None:
        return existing

    return _fetch_one(
        conn,
        """
        INSERT INTO claims (
            claim_type,
            statement,
            subject_type,
            subject_id,
            calculation_method,
            model_provider,
            model_name,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider, model_name, metadata, created_at
        """,
        (
            "official_fact",
            statement,
            COMPRASGOV_ROW_SUBJECT_TYPE,
            str(subject_id),
            "headline_row",
            "manual",
            "comprasgov-expansion",
            Jsonb(
                {
                    "fact_id": str(fact_id),
                    "page": page,
                    "page_size": page_size,
                    "active": active,
                    "headline_external_id": headline_row["external_id"],
                }
            ),
        ),
    )


def ingest_official_bundle(
    conn,
    bundle: Mapping[str, Any],
    *,
    page: int = COMPRASGOV_PAGE,
    page_size: int = COMPRASGOV_PAGE_SIZE,
    active: bool = COMPRASGOV_ACTIVE,
    source_checksum_value: str | None = None,
) -> dict[str, Any]:
    source = ensure_source(conn, build_source_payload())
    dataset_payload = build_dataset_payload(bundle, page, page_size, active)
    dataset = ensure_dataset(conn, source["id"], dataset_payload)
    ingestion_run = ensure_ingestion_run(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        bundle=bundle,
        source_checksum_value=source_checksum_value,
        page=page,
        page_size=page_size,
        active=active,
    )
    raw_record = upsert_raw_record(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        ingestion_run_id=ingestion_run["id"],
        bundle=bundle,
        source_checksum_value=source_checksum_value,
    )
    evidence = upsert_evidence(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        raw_record_id=raw_record["id"],
        page=page,
        page_size=page_size,
        active=active,
        bundle=bundle,
    )
    rows = upsert_rows(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        bundle=bundle,
        default_collected_at=parse_iso_datetime(bundle.get("captured_at")),
        default_source_updated_at=parse_iso_datetime(bundle.get("captured_at")),
    )
    headline_row = rows[0]
    fact = upsert_summary_fact(
        conn,
        source_id=source["id"],
        evidence_id=evidence["id"],
        page=page,
        page_size=page_size,
        active=active,
        headline_row=headline_row,
    )
    claim = upsert_summary_claim(
        conn,
        page=page,
        page_size=page_size,
        active=active,
        fact_id=fact["id"],
        headline_row=headline_row,
    )
    claim_evidence = upsert_claim_evidence(conn, claim["id"], evidence["id"])
    return {
        "source": source,
        "dataset": dataset,
        "ingestion_run": ingestion_run,
        "raw_record": raw_record,
        "evidence": evidence,
        "rows": rows,
        "row_count": len(rows),
        "headline_row": headline_row,
        "headline_statement": headline_statement(headline_row, page=page),
        "fact": fact,
        "claim": claim,
        "claim_evidence": claim_evidence,
    }


def fetch_supplier_summary(
    conn,
    page: int = COMPRASGOV_PAGE,
    page_size: int = COMPRASGOV_PAGE_SIZE,
    active: bool = COMPRASGOV_ACTIVE,
) -> dict[str, Any]:
    if (page, page_size, active) != (COMPRASGOV_PAGE, COMPRASGOV_PAGE_SIZE, COMPRASGOV_ACTIVE):
        raise KeyError(f"{page}:{page_size}:{int(active)}")

    rows = _fetch_rows(
        conn,
        """
        SELECT sr.id, sr.source_id, sr.dataset_id, sr.external_id, sr.active, sr.cnpj, sr.cpf,
               sr.identity_confidence, sr.licensed_to_bid, sr.cnae_code, sr.cnae_name, sr.municipality,
               sr.nature_id, sr.nature_name, sr.company_size_id, sr.company_size_name, sr.supplier_name,
               sr.uf, sr.source_updated_at, sr.collected_at, sr.raw_payload, sr.metadata, sr.created_at,
               sr.updated_at,
               s.name AS source_name, s.slug AS source_slug, s.base_url AS source_url,
               d.name AS dataset_name, d.slug AS dataset_slug, d.resource_url AS dataset_url
        FROM comprasgov_supplier_records AS sr
        JOIN sources AS s ON s.id = sr.source_id
        JOIN datasets AS d ON d.id = sr.dataset_id
        WHERE d.slug = %s
        ORDER BY COALESCE((sr.metadata->>'line_index')::int, 2147483647) ASC,
                 sr.created_at ASC,
                 sr.external_id ASC
        """,
        (COMPRASGOV_DATASET_SLUG,),
    )
    if not rows:
        raise KeyError(f"{page}:{page_size}:{int(active)}")

    rows = [
        row
        for row in rows
        if row["dataset_slug"] == COMPRASGOV_DATASET_SLUG
    ]
    if not rows:
        raise KeyError(f"{page}:{page_size}:{int(active)}")

    headline_row = rows[0]
    subject_id = report_subject_id(page, page_size, active)
    fact = _fetch_optional(
        conn,
        """
        SELECT id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric,
               value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method,
               metadata, created_at
        FROM facts
        WHERE subject_type = %s
          AND subject_id = %s
          AND predicate = %s
        LIMIT 1
        """,
        (COMPRASGOV_ROW_SUBJECT_TYPE, str(subject_id), COMPRASGOV_ROW_SUMMARY_PREDICATE),
    )
    claim = _fetch_optional(
        conn,
        """
        SELECT id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider,
               model_name, metadata, created_at
        FROM claims
        WHERE subject_type = %s
          AND subject_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (COMPRASGOV_ROW_SUBJECT_TYPE, str(subject_id)),
    )
    raw_record = _fetch_optional(
        conn,
        """
        SELECT id, source_id, dataset_id, ingestion_run_id, external_id, payload, payload_hash,
               source_updated_at, collected_at, processing_status, metadata, created_at
        FROM raw_records
        WHERE source_id = %s
          AND dataset_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (headline_row["source_id"], headline_row["dataset_id"]),
    )
    evidence = _fetch_optional(
        conn,
        """
        SELECT id, source_id, dataset_id, raw_record_id, external_id, source_url, page, section,
               collected_at, payload_hash, metadata, created_at
        FROM evidence
        WHERE source_id = %s
          AND dataset_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (headline_row["source_id"], headline_row["dataset_id"]),
    )
    return {
        "source": {
            "id": headline_row["source_id"],
            "name": headline_row["source_name"],
            "slug": headline_row["source_slug"],
            "base_url": headline_row["source_url"],
        },
        "dataset": {
            "id": headline_row["dataset_id"],
            "name": headline_row["dataset_name"],
            "slug": headline_row["dataset_slug"],
            "resource_url": headline_row["dataset_url"],
        },
        "report": {
            "page": page,
            "page_size": page_size,
            "active": active,
            "page_label": f"pagina {page} do cadastro de fornecedores ativos",
        },
        "rows": rows,
        "row_count": len(rows),
        "headline_row": headline_row,
        "headline_statement": headline_statement(headline_row, page=page),
        "fact": fact,
        "claim": claim,
        "raw_record": raw_record,
        "evidence": evidence,
    }


def _fetch_rows(conn, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def query_supplier_response(
    conn,
    page: int = COMPRASGOV_PAGE,
    page_size: int = COMPRASGOV_PAGE_SIZE,
    active: bool = COMPRASGOV_ACTIVE,
) -> dict[str, Any]:
    try:
        summary = fetch_supplier_summary(conn, page, page_size, active)
    except KeyError:
        return {
            "source": None,
            "dataset": None,
            "report": {
                "page": page,
                "page_size": page_size,
                "active": active,
                "page_label": f"pagina {page} do cadastro de fornecedores ativos",
            },
            "collection_timestamp": None,
            "payload_hash": None,
            "status": "no_evidence",
            "row_count": 0,
            "headline": None,
            "source_url": None,
            "citations": [],
        }

    response = {
        "source": summary["source"],
        "dataset": summary["dataset"],
        "report": summary["report"],
        "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
        "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
        "row_count": summary["row_count"],
            "headline": {
            "external_id": summary["headline_row"]["external_id"],
            "cnpj": summary["headline_row"]["cnpj"],
            "cpf": summary["headline_row"]["cpf"],
            "identity_confidence": summary["headline_row"]["identity_confidence"],
            "supplier_name": summary["headline_row"]["supplier_name"],
            "municipality": summary["headline_row"]["municipality"],
            "uf": summary["headline_row"]["uf"],
            "active": summary["headline_row"]["active"],
            "licensed_to_bid": summary["headline_row"]["licensed_to_bid"],
            "nature_name": summary["headline_row"]["nature_name"],
            "company_size_name": summary["headline_row"]["company_size_name"],
        },
    }
    if summary["evidence"] is None:
        return {
            **response,
            "status": "no_evidence",
            "source_url": None,
            "citations": [],
        }

    return {
        **response,
        "status": "ok",
        "source_url": summary["evidence"]["source_url"],
        "citations": [
            {
                "page": page,
                "page_size": page_size,
                "active": active,
                "source_url": summary["evidence"]["source_url"],
                "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
            }
        ],
    }


def query_supplier_row_response(
    conn,
    external_id: str,
    page: int = COMPRASGOV_PAGE,
    page_size: int = COMPRASGOV_PAGE_SIZE,
    active: bool = COMPRASGOV_ACTIVE,
) -> dict[str, Any]:
    row = _fetch_optional(
        conn,
        """
        SELECT sr.id, sr.source_id, sr.dataset_id, sr.external_id, sr.active, sr.cnpj, sr.cpf,
               sr.identity_confidence, sr.licensed_to_bid, sr.cnae_code, sr.cnae_name, sr.municipality,
               sr.nature_id, sr.nature_name, sr.company_size_id, sr.company_size_name, sr.supplier_name,
               sr.uf, sr.source_updated_at, sr.collected_at, sr.raw_payload, sr.metadata, sr.created_at,
               sr.updated_at
        FROM comprasgov_supplier_records AS sr
        WHERE sr.external_id = %s
        LIMIT 1
        """,
        (external_id,),
    )
    try:
        summary = fetch_supplier_summary(conn, page, page_size, active)
    except KeyError:
        summary = None

    if row is None or summary is None:
        return {
            "source": summary["source"] if summary else None,
            "dataset": summary["dataset"] if summary else None,
            "report": summary["report"] if summary else {
                "page": page,
                "page_size": page_size,
                "active": active,
                "page_label": f"pagina {page} do cadastro de fornecedores ativos",
            },
            "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary and summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
            "payload_hash": summary["raw_record"]["payload_hash"] if summary and summary["raw_record"] else None,
            "status": "no_evidence",
            "row": None,
            "source_url": summary["evidence"]["source_url"] if summary and summary["evidence"] else None,
            "citations": [],
        }

    row = dict(row)
    summary_row_ids = {item["external_id"] for item in summary["rows"]}
    if row["external_id"] not in summary_row_ids:
        return {
            "source": summary["source"],
            "dataset": summary["dataset"],
            "report": summary["report"],
            "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
            "payload_hash": summary["raw_record"]["payload_hash"] if summary["raw_record"] else None,
            "status": "no_evidence",
            "row": None,
            "source_url": summary["evidence"]["source_url"] if summary["evidence"] else None,
            "citations": [],
        }

    return {
        "source": summary["source"] if summary else None,
        "dataset": summary["dataset"] if summary else None,
        "report": summary["report"] if summary else {
            "page": page,
            "page_size": page_size,
            "active": active,
            "page_label": f"pagina {page} do cadastro de fornecedores ativos",
        },
        "collection_timestamp": summary["raw_record"]["collected_at"].isoformat() if summary and summary["raw_record"] and summary["raw_record"]["collected_at"] else None,
        "payload_hash": summary["raw_record"]["payload_hash"] if summary and summary["raw_record"] else None,
        "status": "ok",
        "row": row,
        "source_url": summary["evidence"]["source_url"] if summary and summary["evidence"] else None,
        "citations": [
            {
                "external_id": external_id,
                "page": page,
                "page_size": page_size,
                "active": active,
                "source_url": summary["evidence"]["source_url"] if summary and summary["evidence"] else None,
                "payload_hash": summary["raw_record"]["payload_hash"] if summary and summary["raw_record"] else None,
            }
        ],
    }
