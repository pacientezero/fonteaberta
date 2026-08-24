from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from psycopg.types.json import Jsonb

from app.bcb_expansion import (
    _fetch_one,
    _fetch_optional,
    ensure_dataset,
    ensure_source,
    parse_iso_date,
    parse_iso_datetime,
    payload_hash,
)
from app.tse_v1 import normalize_name

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "camara" / "deputados_legislatura_57.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "camara" / "deputados_legislatura_57.json"

CAMARA_SOURCE_SLUG = "camara"
CAMARA_DATASET_SLUG = "deputados-legislatura-57"
CAMARA_DATASET_EXTERNAL_ID = "camara-deputados-legislatura-57"
CAMARA_LEGISLATURE_EXTERNAL_ID = "camara-legislatura-57"
CAMARA_CHAMBER = "camara"


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_hash_value(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def ensure_ingestion_run(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    bundle: Mapping[str, Any],
    source_checksum_value: str | None,
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
        (source_id, dataset_id, "connector-camara-expansion", source_checksum_value),
    )
    if existing is not None:
        return existing

    started_at = parse_iso_datetime(bundle.get("ingestion_run", {}).get("started_at")) or datetime.now(timezone.utc)
    finished_at = parse_iso_datetime(bundle.get("ingestion_run", {}).get("finished_at")) or started_at
    metadata = dict(bundle.get("ingestion_run", {}).get("metadata") or {})
    metadata.setdefault("selected_deputies", len(bundle.get("selected_deputies") or []))
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
            "connector-camara-expansion",
            "full",
            started_at,
            finished_at,
            "success",
            len(bundle.get("selected_deputies") or []),
            len(bundle.get("selected_deputies") or []),
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
    raw_record_payload = bundle.get("raw_record") or {}
    external_id = raw_record_payload.get("external_id", f"{CAMARA_DATASET_EXTERNAL_ID}-snapshot")
    payload = bundle["snapshot"]
    metadata = dict(raw_record_payload.get("metadata") or {})
    source_updated_at = parse_iso_datetime(raw_record_payload.get("source_updated_at"))
    collected_at = parse_iso_datetime(raw_record_payload.get("collected_at")) or datetime.now(timezone.utc)
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
            external_id,
            Jsonb(payload),
            source_checksum_value or payload_hash(payload),
            source_updated_at,
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
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_payload = bundle.get("evidence") or {}
    metadata = dict(evidence_payload.get("metadata") or {})
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
            evidence_payload.get("external_id", f"{CAMARA_DATASET_EXTERNAL_ID}-evidence"),
            evidence_payload.get("source_url", bundle["dataset"]["resource_url"]),
            evidence_payload.get("page"),
            evidence_payload.get("section", "deputados"),
            parse_iso_datetime(evidence_payload.get("collected_at")) or datetime.now(timezone.utc),
            evidence_payload.get("payload_hash", payload_hash(bundle["snapshot"])),
            Jsonb(metadata),
        ),
    )


def _resolve_party_id(conn, party_acronym: str | None) -> str | None:
    if not party_acronym:
        return None
    row = _fetch_optional(
        conn,
        """
        SELECT id
        FROM parties
        WHERE acronym = %s
        LIMIT 1
        """,
        (party_acronym,),
    )
    if row is None:
        return None
    return str(row["id"])


def ensure_person(conn, source_id: str, deputy_bundle: Mapping[str, Any]) -> dict[str, Any]:
    detail = deputy_bundle["detail"]
    status = detail["ultimoStatus"]
    external_id = str(status["id"])
    alias = _fetch_optional(
        conn,
        """
        SELECT p.id
        FROM entity_aliases AS ea
        JOIN people AS p ON p.id = ea.entity_id
        WHERE ea.source_id = %s
          AND ea.entity_type = 'person'
          AND ea.external_id = %s
        LIMIT 1
        """,
        (source_id, external_id),
    )

    canonical_name = detail.get("nomeCivil") or status.get("nome") or status.get("nomeEleitoral")
    birth_place_parts = [part for part in [detail.get("municipioNascimento"), detail.get("ufNascimento")] if part]
    birth_place = ", ".join(birth_place_parts) if birth_place_parts else None
    metadata = {
        "display_name": status.get("nome"),
        "electoral_name": status.get("nomeEleitoral"),
        "party_acronym": status.get("siglaPartido"),
        "state": status.get("siglaUf"),
        "legislature": status.get("idLegislatura"),
        "photo_url": status.get("urlFoto"),
        "email": (status.get("gabinete") or {}).get("email") or status.get("email"),
        "profile_url": detail.get("uri"),
        "detail_url": detail.get("uri"),
        "social_links": detail.get("redeSocial") or [],
        "education": detail.get("escolaridade"),
        "birth_date": detail.get("dataNascimento"),
        "birth_place": birth_place,
    }
    if alias is None:
        person = _fetch_one(
            conn,
            """
            INSERT INTO people (
                canonical_name,
                normalized_name,
                birth_date,
                birth_place,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, canonical_name, normalized_name, birth_date, birth_place, metadata, created_at, updated_at
            """,
            (
                canonical_name,
                normalize_name(canonical_name),
                parse_iso_date(detail.get("dataNascimento")),
                birth_place,
                Jsonb(metadata),
            ),
        )
        conn.execute(
            """
            INSERT INTO entity_aliases (
                entity_type,
                entity_id,
                source_id,
                external_id,
                external_name,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, entity_type, external_id) DO UPDATE
            SET
                entity_id = EXCLUDED.entity_id,
                external_name = EXCLUDED.external_name,
                metadata = EXCLUDED.metadata
            """,
            (
                "person",
                person["id"],
                source_id,
                external_id,
                status.get("nomeEleitoral") or status.get("nome"),
                Jsonb(
                    {
                        "external_id": external_id,
                        "list_name": deputy_bundle.get("list_row", {}).get("nome"),
                        "party_acronym": status.get("siglaPartido"),
                        "state": status.get("siglaUf"),
                        "legislature_external_id": f"{CAMARA_LEGISLATURE_EXTERNAL_ID}",
                    }
                ),
            ),
        )
        return person

    person_id = alias["id"]
    person = _fetch_one(
        conn,
        """
        UPDATE people
        SET
            canonical_name = %s,
            normalized_name = %s,
            birth_date = %s,
            birth_place = %s,
            metadata = %s
        WHERE id = %s
        RETURNING id, canonical_name, normalized_name, birth_date, birth_place, metadata, created_at, updated_at
        """,
        (
            canonical_name,
            normalize_name(canonical_name),
            parse_iso_date(detail.get("dataNascimento")),
            birth_place,
            Jsonb(metadata),
            person_id,
        ),
    )
    conn.execute(
        """
        UPDATE entity_aliases
        SET
            external_name = %s,
            metadata = %s
        WHERE source_id = %s
          AND entity_type = 'person'
          AND external_id = %s
        """,
        (
            status.get("nomeEleitoral") or status.get("nome"),
            Jsonb(
                {
                    "external_id": external_id,
                    "list_name": deputy_bundle.get("list_row", {}).get("nome"),
                    "party_acronym": status.get("siglaPartido"),
                    "state": status.get("siglaUf"),
                    "legislature_external_id": f"{CAMARA_LEGISLATURE_EXTERNAL_ID}",
                }
            ),
            source_id,
            external_id,
        ),
    )
    return person


def ensure_mandate(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    person_id: str,
    deputy_bundle: Mapping[str, Any],
) -> dict[str, Any]:
    detail = deputy_bundle["detail"]
    status = detail["ultimoStatus"]
    deputy_id = str(status["id"])
    legislature_id = str(status["idLegislatura"])
    external_id = f"camara-deputado-{deputy_id}-{legislature_id}"
    party_acronym = status.get("siglaPartido")
    party_id = _resolve_party_id(conn, party_acronym)
    started_at = parse_iso_date(status.get("data"))
    metadata = {
        "detail_url": detail.get("uri"),
        "list_url": deputy_bundle.get("list_row", {}).get("uri"),
        "gabinete": status.get("gabinete"),
        "social_links": detail.get("redeSocial") or [],
        "condicao_eleitoral": status.get("condicaoEleitoral"),
        "descricao_status": status.get("descricaoStatus"),
    }
    existing = _fetch_optional(
        conn,
        """
        SELECT id, source_id, dataset_id, person_id, party_id, external_id, legislature_external_id, chamber,
               electoral_name, state, party_acronym, status, email, profile_url, photo_url, started_at,
               ended_at, source_updated_at, collected_at, raw_payload, metadata, created_at, updated_at
        FROM mandates
        WHERE source_id = %s
          AND external_id = %s
        LIMIT 1
        """,
        (source_id, external_id),
    )
    if existing is not None:
        return existing

    return _fetch_one(
        conn,
        """
        INSERT INTO mandates (
            source_id,
            dataset_id,
            person_id,
            party_id,
            external_id,
            legislature_external_id,
            chamber,
            electoral_name,
            state,
            party_acronym,
            status,
            email,
            profile_url,
            photo_url,
            started_at,
            ended_at,
            source_updated_at,
            collected_at,
            raw_payload,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            dataset_id = EXCLUDED.dataset_id,
            person_id = EXCLUDED.person_id,
            party_id = EXCLUDED.party_id,
            legislature_external_id = EXCLUDED.legislature_external_id,
            chamber = EXCLUDED.chamber,
            electoral_name = EXCLUDED.electoral_name,
            state = EXCLUDED.state,
            party_acronym = EXCLUDED.party_acronym,
            status = EXCLUDED.status,
            email = EXCLUDED.email,
            profile_url = EXCLUDED.profile_url,
            photo_url = EXCLUDED.photo_url,
            started_at = EXCLUDED.started_at,
            ended_at = EXCLUDED.ended_at,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            raw_payload = EXCLUDED.raw_payload,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING id, source_id, dataset_id, person_id, party_id, external_id, legislature_external_id, chamber,
                  electoral_name, state, party_acronym, status, email, profile_url, photo_url, started_at,
                  ended_at, source_updated_at, collected_at, raw_payload, metadata, created_at, updated_at
        """,
        (
            source_id,
            dataset_id,
            person_id,
            party_id,
            external_id,
            f"{CAMARA_LEGISLATURE_EXTERNAL_ID}-{legislature_id}",
            CAMARA_CHAMBER,
            status.get("nomeEleitoral") or status.get("nome"),
            status.get("siglaUf"),
            party_acronym,
            status.get("situacao") or "Exercício",
            (status.get("gabinete") or {}).get("email") or status.get("email"),
            status.get("uri") or detail.get("uri"),
            status.get("urlFoto"),
            started_at,
            None,
            started_at,
            started_at,
            Jsonb(detail),
            Jsonb(metadata),
        ),
    )


def upsert_current_mandate_fact(
    conn,
    *,
    source_id: str,
    evidence_id: str,
    person_id: str,
    mandate: Mapping[str, Any],
) -> dict[str, Any]:
    effective_date = mandate["started_at"] or mandate["source_updated_at"]
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
          AND object_id = %s
        LIMIT 1
        """,
        ("person", person_id, "current_mandate", mandate["id"]),
    )
    if existing is not None:
        return existing

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
            "person",
            person_id,
            "current_mandate",
            "mandate",
            mandate["id"],
            mandate["electoral_name"],
            None,
            None,
            effective_date,
            None,
            effective_date,
            source_id,
            evidence_id,
            "camara.deputados.ultimoStatus",
            Jsonb(
                {
                    "chamber": mandate["chamber"],
                    "legislature_external_id": mandate["legislature_external_id"],
                    "party_acronym": mandate["party_acronym"],
                    "status": mandate["status"],
                }
            ),
        ),
    )


def upsert_current_mandate_claim(
    conn,
    *,
    person: Mapping[str, Any],
    mandate: Mapping[str, Any],
    fact_id: str,
) -> dict[str, Any]:
    legislature_number = mandate["legislature_external_id"].split("-")[-1]
    statement = (
        f"{person['canonical_name']} exerce mandato de deputado federal pela Câmara dos Deputados na "
        f"{legislature_number}ª legislatura."
    )
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
        ("person", person["id"], statement),
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
        RETURNING id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider,
                  model_name, metadata, created_at
        """,
        (
            "official_fact",
            statement,
            "person",
            person["id"],
            "camara.deputados.ultimoStatus",
            "manual",
            "camara-expansion",
            Jsonb(
                {
                    "fact_id": str(fact_id),
                    "mandate_id": str(mandate["id"]),
                }
            ),
        ),
    )


def ingest_official_bundle(conn, bundle: Mapping[str, Any], *, source_checksum_value: str | None = None) -> dict[str, Any]:
    source = ensure_source(conn, bundle["source"])
    dataset = ensure_dataset(conn, source["id"], bundle["dataset"])
    ingestion_run = ensure_ingestion_run(
        conn,
        source_id=source["id"],
        dataset_id=dataset["id"],
        bundle=bundle,
        source_checksum_value=source_checksum_value,
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
        bundle=bundle,
    )

    people: list[dict[str, Any]] = []
    mandates: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    for deputy_bundle in bundle["selected_deputies"]:
        person = ensure_person(conn, source["id"], deputy_bundle)
        mandate = ensure_mandate(
            conn,
            source_id=source["id"],
            dataset_id=dataset["id"],
            person_id=person["id"],
            deputy_bundle=deputy_bundle,
        )
        fact = upsert_current_mandate_fact(
            conn,
            source_id=source["id"],
            evidence_id=evidence["id"],
            person_id=person["id"],
            mandate=mandate,
        )
        claim = upsert_current_mandate_claim(
            conn,
            person=person,
            mandate=mandate,
            fact_id=fact["id"],
        )
        people.append(person)
        mandates.append(mandate)
        facts.append(fact)
        claims.append(claim)

    return {
        "source": source,
        "dataset": dataset,
        "ingestion_run": ingestion_run,
        "raw_record": raw_record,
        "evidence": evidence,
        "people": people,
        "mandates": mandates,
        "facts": facts,
        "claims": claims,
    }


def fetch_mandate_summary(conn, mandate_external_id: str) -> dict[str, Any]:
    row = _fetch_optional(
        conn,
        """
        SELECT
            m.id AS mandate_id,
            m.external_id AS mandate_external_id,
            m.legislature_external_id,
            m.chamber,
            m.electoral_name,
            m.state,
            m.party_acronym,
            m.status,
            m.email,
            m.profile_url,
            m.photo_url,
            m.started_at,
            m.ended_at,
            m.source_updated_at,
            m.collected_at,
            m.raw_payload,
            m.metadata,
            p.id AS person_id,
            p.canonical_name,
            p.normalized_name,
            p.birth_date,
            p.birth_place,
            p.metadata AS person_metadata,
            party.id AS party_id,
            party.name AS party_name,
            party.acronym AS party_acronym_resolved,
            party.number AS party_number,
            s.id AS source_id,
            s.slug AS source_slug,
            s.name AS source_name,
            d.id AS dataset_id,
            d.slug AS dataset_slug,
            rr.id AS raw_record_id,
            rr.external_id AS raw_record_external_id,
            rr.payload_hash AS raw_record_payload_hash,
            e.id AS evidence_id,
            e.external_id AS evidence_external_id,
            e.source_url AS evidence_source_url,
            f.id AS fact_id,
            f.predicate AS fact_predicate,
            f.value_text AS fact_value_text,
            f.effective_date AS fact_effective_date,
            c.id AS claim_id,
            c.statement AS claim_statement,
            c.claim_type AS claim_type,
            c.calculation_method AS claim_calculation_method
        FROM mandates AS m
        JOIN people AS p ON p.id = m.person_id
        LEFT JOIN parties AS party ON party.id = m.party_id
        JOIN sources AS s ON s.id = m.source_id
        JOIN datasets AS d ON d.id = m.dataset_id
        LEFT JOIN raw_records AS rr
               ON rr.source_id = m.source_id
              AND rr.dataset_id = m.dataset_id
        LEFT JOIN evidence AS e
               ON e.raw_record_id = rr.id
              AND e.source_id = m.source_id
              AND e.dataset_id = m.dataset_id
        LEFT JOIN facts AS f
               ON f.subject_type = 'person'
              AND f.subject_id = p.id
              AND f.predicate = 'current_mandate'
              AND f.object_type = 'mandate'
              AND f.object_id = m.id
        LEFT JOIN claims AS c
               ON c.subject_type = 'person'
              AND c.subject_id = p.id
              AND c.metadata ->> 'fact_id' = f.id::text
        WHERE m.external_id = %s
        ORDER BY rr.created_at DESC, e.created_at DESC, f.created_at DESC, c.created_at DESC
        LIMIT 1
        """,
        (mandate_external_id,),
    )
    if row is None:
        raise KeyError(mandate_external_id)
    return row


def query_mandate_response(conn, deputy_id: str, legislature_id: str | int = 57) -> dict[str, Any]:
    mandate_external_id = f"camara-deputado-{deputy_id}-{legislature_id}"
    try:
        summary = fetch_mandate_summary(conn, mandate_external_id)
    except KeyError:
        return {
            "status": "no_evidence",
            "mandate": None,
            "citations": [],
        }
    return {
        "status": "ok",
        "mandate": summary,
        "citations": [
            {
                "evidence_id": summary["evidence_id"],
                "source_url": summary["evidence_source_url"],
                "raw_record_id": summary["raw_record_id"],
            }
        ],
    }
