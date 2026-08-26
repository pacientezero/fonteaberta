from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.request import Request, urlopen

from psycopg.types.json import Jsonb

from app.bcb_expansion import (
    _fetch_one,
    _fetch_optional,
    ensure_dataset,
    ensure_source,
    parse_iso_date,
    parse_iso_datetime,
    payload_hash,
    upsert_claim_evidence,
)
from app.tse_v1 import normalize_name

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "camara" / "legislative_plp230_2025_vote_2580259_24.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "camara" / "legislative_plp230_2025_vote_2580259_24.json"
CAMARA_API_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"

CAMARA_SOURCE_SLUG = "camara"
CAMARA_SOURCE_NAME = "Camara dos Deputados"
CAMARA_SOURCE_DESCRIPTION = "API oficial de dados abertos da Camara dos Deputados"
CAMARA_SOURCE_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
CAMARA_SOURCE_DOCUMENTATION_URL = "https://dadosabertos.camara.leg.br/swagger/api.html"
CAMARA_HOUSE = "camara"
SUBSTANTIVE_VOTE_PATTERN = re.compile(
    r"^Aprovad[oa].*(Projeto de Lei|Projeto de Lei Complementar|Substitutivo|Subemenda Substitutiva)",
    re.IGNORECASE,
)


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_official_json(path: str) -> dict[str, Any]:
    request = Request(
        f"{CAMARA_API_BASE_URL}{path}",
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def _extract_vote_proposition_id(vote_payload: Mapping[str, Any]) -> str:
    affected = vote_payload.get("proposicoesAfetadas") or []
    for item in affected:
        proposition_id = item.get("id")
        if proposition_id is not None:
            return str(proposition_id)

    cited = vote_payload.get("ultimaApresentacaoProposicao", {}).get("uriProposicaoCitada")
    if cited:
        return str(cited).rstrip("/").rsplit("/", 1)[-1]

    possible = vote_payload.get("objetosPossiveis") or []
    for item in possible:
        proposition_id = item.get("id")
        if proposition_id is not None:
            return str(proposition_id)

    raise KeyError(f"Unable to resolve proposition for vote {vote_payload.get('id')}")


def fetch_official_bundle(vote_external_id: str) -> dict[str, Any]:
    vote_payload = _fetch_official_json(f"/votacoes/{vote_external_id}")["dados"]
    proposition_external_id = _extract_vote_proposition_id(vote_payload)
    proposition_payload = _fetch_official_json(f"/proposicoes/{proposition_external_id}")["dados"]
    authors_payload = _fetch_official_json(f"/proposicoes/{proposition_external_id}/autores")["dados"]
    votes_payload = _fetch_official_json(f"/votacoes/{vote_external_id}/votos")["dados"]
    orientations_payload = _fetch_official_json(f"/votacoes/{vote_external_id}/orientacoes")["dados"]
    proposition_year = int(proposition_payload["ano"])
    vote_year = int(str(vote_payload["data"])[:4]) if vote_payload.get("data") else int(
        str(vote_payload.get("dataHoraRegistro", ""))[:4]
    )

    return {
        "metadata": {
            "source_slug": CAMARA_SOURCE_SLUG,
            "source_name": CAMARA_SOURCE_NAME,
            "source_license": "open data",
            "proposition_dataset_slug": f"proposicoes-{proposition_year}",
            "vote_dataset_slug": f"votacoes-{vote_year}",
            "vote_members_dataset_slug": f"votacoes-votos-{vote_year}",
            "proposition_dataset_url": f"{CAMARA_API_BASE_URL}/proposicoes",
            "vote_dataset_url": f"{CAMARA_API_BASE_URL}/votacoes",
            "vote_members_dataset_url": f"{CAMARA_API_BASE_URL}/votacoes/{vote_external_id}/votos",
            "vote_orientations_dataset_url": f"{CAMARA_API_BASE_URL}/votacoes/{vote_external_id}/orientacoes",
        },
        "proposition": proposition_payload,
        "vote": vote_payload,
        "authors": authors_payload,
        "votes": votes_payload,
        "orientations": orientations_payload,
    }


def fetch_recent_substantive_vote_ids(limit: int = 100, *, pages: int = 40) -> list[str]:
    limit = max(1, min(limit, 100))
    pages = max(1, min(pages, 40))
    vote_ids: list[str] = []
    seen: set[str] = set()

    for page in range(1, pages + 1):
        result = _fetch_official_json(
            f"/votacoes?ordem=DESC&ordenarPor=dataHoraRegistro&itens=100&pagina={page}"
        )
        for item in result.get("dados", []):
            if not item.get("aprovacao"):
                continue
            description = str(item.get("descricao") or "")
            if not SUBSTANTIVE_VOTE_PATTERN.search(description):
                continue
            vote_id = str(item["id"])
            if vote_id in seen:
                continue
            seen.add(vote_id)
            vote_ids.append(vote_id)
            if len(vote_ids) >= limit:
                return vote_ids

    return vote_ids


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_hash_value(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _build_dataset_payload(
    *,
    name: str,
    slug: str,
    external_id: str,
    resource_url: str,
    period_start: str,
    period_end: str,
    archive_year: int,
    resource_kind: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "slug": slug,
        "external_id": external_id,
        "format": "json",
        "resource_url": resource_url,
        "scope": "federal",
        "period_start": period_start,
        "period_end": period_end,
        "update_frequency": "daily",
        "enabled": True,
        "metadata": {
            "archive_year": archive_year,
            "resource_kind": resource_kind,
        },
    }


def _build_source_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    metadata = bundle.get("metadata") or {}
    source_payload = dict(bundle.get("source") or {})
    source_payload.setdefault("slug", metadata.get("source_slug", CAMARA_SOURCE_SLUG))
    source_payload.setdefault("name", metadata.get("source_name", CAMARA_SOURCE_NAME))
    source_payload.setdefault("institution", CAMARA_SOURCE_NAME)
    source_payload.setdefault("description", CAMARA_SOURCE_DESCRIPTION)
    source_payload.setdefault("base_url", CAMARA_SOURCE_BASE_URL)
    source_payload.setdefault("documentation_url", CAMARA_SOURCE_DOCUMENTATION_URL)
    source_payload.setdefault("source_type", "official_registry")
    source_payload.setdefault("scope", "federal")
    source_payload.setdefault("official", True)
    source_payload.setdefault("update_frequency", "daily")
    source_payload.setdefault("license", metadata.get("source_license", "open data"))
    source_payload.setdefault("enabled", True)
    source_payload.setdefault("metadata", dict(metadata))
    return source_payload


def ensure_catalog(conn, bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    source = ensure_source(conn, _build_source_payload(bundle))
    metadata = bundle["metadata"]
    proposition_year = int(str(metadata["proposition_dataset_slug"]).rsplit("-", 1)[-1])
    vote_year = int(str(metadata["vote_dataset_slug"]).rsplit("-", 1)[-1])
    proposition_dataset = ensure_dataset(
        conn,
        source["id"],
        _build_dataset_payload(
            name=f"Proposições {proposition_year}",
            slug=metadata["proposition_dataset_slug"],
            external_id=f"camara-{metadata['proposition_dataset_slug']}",
            resource_url=metadata["proposition_dataset_url"],
            period_start=f"{proposition_year}-01-01",
            period_end=f"{proposition_year}-12-31",
            archive_year=proposition_year,
            resource_kind="proposicoes",
        ),
    )
    vote_dataset = ensure_dataset(
        conn,
        source["id"],
        _build_dataset_payload(
            name=f"Votações {vote_year}",
            slug=metadata["vote_dataset_slug"],
            external_id=f"camara-{metadata['vote_dataset_slug']}",
            resource_url=metadata["vote_dataset_url"],
            period_start=f"{vote_year}-01-01",
            period_end=f"{vote_year}-12-31",
            archive_year=vote_year,
            resource_kind="votacoes",
        ),
    )
    vote_members_dataset = ensure_dataset(
        conn,
        source["id"],
        _build_dataset_payload(
            name=f"Votos nominais {vote_year}",
            slug=metadata["vote_members_dataset_slug"],
            external_id=f"camara-{metadata['vote_members_dataset_slug']}",
            resource_url=metadata["vote_members_dataset_url"],
            period_start=f"{vote_year}-01-01",
            period_end=f"{vote_year}-12-31",
            archive_year=vote_year,
            resource_kind="votacoesVotos",
        ),
    )
    return {
        "source": source,
        "proposition_dataset": proposition_dataset,
        "vote_dataset": vote_dataset,
        "vote_members_dataset": vote_members_dataset,
    }


def ingest_recent_official_votes(
    conn,
    *,
    limit: int = 100,
    pages: int = 40,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    pages = max(1, min(pages, 40))
    ingested: list[dict[str, Any]] = []
    seen: set[str] = set()

    scan_limit = max(limit * 10, 100)
    for vote_external_id in fetch_recent_substantive_vote_ids(limit=scan_limit, pages=pages):
        if vote_external_id in seen:
            continue
        seen.add(vote_external_id)
        bundle = fetch_official_bundle(vote_external_id)
        ingested.append(
            ingest_official_bundle(
                conn,
                bundle,
                source_checksum_value=payload_hash_value(bundle),
            )
        )
        if len(ingested) >= limit:
            break

    return ingested


def ensure_ingestion_run(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    pipeline: str,
    run_type: str,
    payload: Mapping[str, Any] | list[Mapping[str, Any]],
    started_at: datetime | None,
    finished_at: datetime | None,
    metadata: Mapping[str, Any],
    records_read: int,
) -> dict[str, Any]:
    source_checksum_value = payload_hash(payload)
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
        (source_id, dataset_id, pipeline, source_checksum_value),
    )
    if existing is not None:
        return existing

    started_at = started_at or datetime.now(timezone.utc)
    finished_at = finished_at or started_at
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
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, source_id, dataset_id, pipeline, run_type, started_at, finished_at, status,
                  records_read, records_created, records_updated, records_unchanged, records_failed,
                  source_checksum, error_summary, metadata, created_at
        """,
        (
            source_id,
            dataset_id,
            pipeline,
            run_type,
            started_at,
            finished_at,
            "success",
            records_read,
            records_read,
            0,
            0,
            0,
            source_checksum_value,
            Jsonb(dict(metadata)),
        ),
    )


def upsert_raw_record(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    ingestion_run_id: str,
    external_id: str,
    payload: Mapping[str, Any] | list[Mapping[str, Any]],
    source_updated_at: datetime | None,
    collected_at: datetime,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
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
            payload_hash(payload),
            source_updated_at,
            collected_at,
            "normalized",
            Jsonb(dict(metadata)),
        ),
    )


def upsert_evidence(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    raw_record_id: str,
    external_id: str,
    source_url: str,
    section: str,
    collected_at: datetime,
    payload: Mapping[str, Any] | list[Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return _fetch_one(
        conn,
        """
        INSERT INTO evidence (
            source_id,
            dataset_id,
            raw_record_id,
            external_id,
            source_url,
            section,
            collected_at,
            payload_hash,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, dataset_id, external_id) DO UPDATE
        SET
            raw_record_id = EXCLUDED.raw_record_id,
            source_url = EXCLUDED.source_url,
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
            external_id,
            source_url,
            section,
            collected_at,
            payload_hash(payload),
            Jsonb(dict(metadata)),
        ),
    )


def ensure_party(conn, source_id: str, party_payload: Mapping[str, Any]) -> dict[str, Any]:
    acronym = party_payload.get("siglaPartido") or ""
    if not acronym:
        return _fetch_one(
            conn,
            """
            INSERT INTO parties (
                external_id,
                name,
                acronym,
                number,
                official_url,
                logo_url,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, external_id, name, acronym, number, official_url, logo_url, metadata, created_at, updated_at
            """,
            (
                f"{CAMARA_SOURCE_SLUG}:unknown",
                "Desconhecido",
                "DESCONHECIDO",
                None,
                None,
                None,
                Jsonb({"source": CAMARA_SOURCE_SLUG}),
            ),
        )

    existing = _fetch_optional(
        conn,
        """
        SELECT id, external_id, name, acronym, number, official_url, logo_url, metadata, created_at, updated_at
        FROM parties
        WHERE acronym = %s
        LIMIT 1
        """,
        (acronym,),
    )
    if existing is not None:
        return existing

    return _fetch_one(
        conn,
        """
        INSERT INTO parties (
            external_id,
            name,
            acronym,
            number,
            official_url,
            logo_url,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, external_id, name, acronym, number, official_url, logo_url, metadata, created_at, updated_at
        """,
        (
            f"{CAMARA_SOURCE_SLUG}:{acronym}",
            party_payload.get("siglaPartido") or acronym,
            acronym,
            None,
            party_payload.get("uriPartido"),
            None,
            Jsonb(
                {
                    "source_house": CAMARA_HOUSE,
                    "source_acronym": acronym,
                    "source_uri": party_payload.get("uriPartido"),
                }
            ),
        ),
    )


def ensure_person(conn, source_id: str, vote_member: Mapping[str, Any]) -> dict[str, Any]:
    deputy = vote_member["deputado_"]
    external_id = str(deputy["id"])
    name = deputy["nome"]
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

    metadata = {
        "display_name": name,
        "party_acronym": deputy.get("siglaPartido"),
        "state": deputy.get("siglaUf"),
        "photo_url": deputy.get("urlFoto"),
        "profile_url": deputy.get("uri"),
        "email": deputy.get("email"),
        "legislature": deputy.get("idLegislatura"),
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
                name,
                normalize_name(name),
                None,
                deputy.get("siglaUf"),
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
                name,
                Jsonb(metadata),
            ),
        )
        return person

    person = _fetch_one(
        conn,
        """
        UPDATE people
        SET
            canonical_name = %s,
            normalized_name = %s,
            birth_place = %s,
            metadata = %s
        WHERE id = %s
        RETURNING id, canonical_name, normalized_name, birth_date, birth_place, metadata, created_at, updated_at
        """,
        (
            name,
            normalize_name(name),
            deputy.get("siglaUf"),
            Jsonb(metadata),
            alias["id"],
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
            name,
            Jsonb(metadata),
            source_id,
            external_id,
        ),
    )
    return person


def upsert_proposition(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    proposition_row: Mapping[str, Any],
    raw_record_id: str,
    evidence_id: str,
    source_updated_at: datetime | None,
    collected_at: datetime,
) -> dict[str, Any]:
    return _fetch_one(
        conn,
        """
        INSERT INTO legislative_propositions (
            source_id,
            dataset_id,
            external_id,
            house,
            sigla_tipo,
            number,
            year,
            title,
            summary,
            presented_at,
            status,
            source_url,
            raw_record_id,
            evidence_id,
            source_updated_at,
            collected_at,
            raw_payload,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            dataset_id = EXCLUDED.dataset_id,
            house = EXCLUDED.house,
            sigla_tipo = EXCLUDED.sigla_tipo,
            number = EXCLUDED.number,
            year = EXCLUDED.year,
            title = EXCLUDED.title,
            summary = EXCLUDED.summary,
            presented_at = EXCLUDED.presented_at,
            status = EXCLUDED.status,
            source_url = EXCLUDED.source_url,
            raw_record_id = EXCLUDED.raw_record_id,
            evidence_id = EXCLUDED.evidence_id,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            raw_payload = EXCLUDED.raw_payload,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING id, source_id, dataset_id, external_id, house, sigla_tipo, number, year, title, summary, presented_at, status, source_url, raw_record_id, evidence_id, source_updated_at, collected_at, raw_payload, metadata, created_at, updated_at
        """,
        (
            source_id,
            dataset_id,
            str(proposition_row["id"]),
            CAMARA_HOUSE,
            proposition_row["siglaTipo"],
            int(proposition_row["numero"]),
            int(proposition_row["ano"]),
            f"{proposition_row['siglaTipo']} {proposition_row['numero']}/{proposition_row['ano']}",
            proposition_row.get("ementa"),
            parse_iso_datetime(proposition_row.get("dataApresentacao")),
            proposition_row.get("statusProposicao", {}).get("descricaoSituacao")
            or proposition_row.get("statusProposicao", {}).get("descricaoTramitacao"),
            proposition_row.get("urlInteiroTeor") or proposition_row.get("uri"),
            raw_record_id,
            evidence_id,
            source_updated_at,
            collected_at,
            Jsonb(dict(proposition_row)),
            Jsonb(
                {
                    "description_type": proposition_row.get("descricaoTipo"),
                    "status_payload": proposition_row.get("statusProposicao"),
                    "authors_url": proposition_row.get("uriAutores"),
                    "keywords": proposition_row.get("keywords"),
                }
            ),
        ),
    )


def upsert_vote(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    proposition_id: str,
    vote_row: Mapping[str, Any],
    raw_record_id: str,
    evidence_id: str,
    source_updated_at: datetime | None,
    collected_at: datetime,
    yes_votes: int,
    no_votes: int,
    other_votes: int,
    total_votes: int,
) -> dict[str, Any]:
    approved = bool(vote_row.get("aprovacao"))
    return _fetch_one(
        conn,
        """
        INSERT INTO legislative_votes (
            source_id,
            dataset_id,
            proposition_id,
            external_id,
            house,
            vote_date,
            vote_timestamp,
            description,
            result,
            vote_type,
            approved,
            total_votes,
            yes_votes,
            no_votes,
            other_votes,
            source_url,
            raw_record_id,
            evidence_id,
            source_updated_at,
            collected_at,
            raw_payload,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
        SET
            dataset_id = EXCLUDED.dataset_id,
            proposition_id = EXCLUDED.proposition_id,
            house = EXCLUDED.house,
            vote_date = EXCLUDED.vote_date,
            vote_timestamp = EXCLUDED.vote_timestamp,
            description = EXCLUDED.description,
            result = EXCLUDED.result,
            vote_type = EXCLUDED.vote_type,
            approved = EXCLUDED.approved,
            total_votes = EXCLUDED.total_votes,
            yes_votes = EXCLUDED.yes_votes,
            no_votes = EXCLUDED.no_votes,
            other_votes = EXCLUDED.other_votes,
            source_url = EXCLUDED.source_url,
            raw_record_id = EXCLUDED.raw_record_id,
            evidence_id = EXCLUDED.evidence_id,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            raw_payload = EXCLUDED.raw_payload,
            metadata = EXCLUDED.metadata,
            updated_at = now()
        RETURNING id, source_id, dataset_id, proposition_id, external_id, house, vote_date, vote_timestamp, description, result, vote_type, approved, total_votes, yes_votes, no_votes, other_votes, source_url, raw_record_id, evidence_id, source_updated_at, collected_at, raw_payload, metadata, created_at, updated_at
        """,
        (
            source_id,
            dataset_id,
            proposition_id,
            str(vote_row["id"]),
            CAMARA_HOUSE,
            parse_iso_date(vote_row.get("data")),
            parse_iso_datetime(vote_row.get("dataHoraRegistro")),
            vote_row.get("descricao"),
            "Aprovado" if approved else "Rejeitado",
            "nominal" if total_votes else "simbolico",
            approved,
            total_votes,
            yes_votes,
            no_votes,
            other_votes,
            vote_row.get("uri"),
            raw_record_id,
            evidence_id,
            source_updated_at,
            collected_at,
            Jsonb(dict(vote_row)),
            Jsonb(
                {
                    "orgao": vote_row.get("siglaOrgao"),
                    "event_id": vote_row.get("idEvento"),
                    "event_url": vote_row.get("uriEvento"),
                    "proposition_object": vote_row.get("proposicaoObjeto"),
                    "proposition_object_url": vote_row.get("uriProposicaoObjeto"),
                }
            ),
        ),
    )


def _normalize_vote_value(label: str) -> tuple[str, str]:
    normalized = normalize_name(label)
    if normalized == "NAO":
        return "nao", label
    if normalized == "SIM":
        return "sim", label
    if normalized.startswith("ARTIGO"):
        return "artigo_17", label
    return normalized.lower().replace(" ", "_"), label


def upsert_vote_member(
    conn,
    *,
    source_id: str,
    vote_id: str,
    vote_member: Mapping[str, Any],
    raw_record_id: str,
    evidence_id: str,
    source_updated_at: datetime | None,
    collected_at: datetime,
) -> dict[str, Any]:
    deputy = vote_member["deputado_"]
    person = ensure_person(conn, source_id, vote_member)
    party = ensure_party(conn, source_id, deputy)
    vote_value, vote_label = _normalize_vote_value(vote_member.get("tipoVoto") or "desconhecido")

    return _fetch_one(
        conn,
        """
        INSERT INTO legislative_vote_members (
            vote_id,
            person_id,
            party_id,
            external_id,
            vote_value,
            vote_label,
            source_url,
            raw_record_id,
            evidence_id,
            source_updated_at,
            collected_at,
            raw_payload,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (vote_id, external_id) DO UPDATE
        SET
            person_id = EXCLUDED.person_id,
            party_id = EXCLUDED.party_id,
            vote_value = EXCLUDED.vote_value,
            vote_label = EXCLUDED.vote_label,
            source_url = EXCLUDED.source_url,
            raw_record_id = EXCLUDED.raw_record_id,
            evidence_id = EXCLUDED.evidence_id,
            source_updated_at = EXCLUDED.source_updated_at,
            collected_at = EXCLUDED.collected_at,
            raw_payload = EXCLUDED.raw_payload,
            metadata = EXCLUDED.metadata
        RETURNING id, vote_id, person_id, party_id, external_id, vote_value, vote_label, source_url, raw_record_id, evidence_id, source_updated_at, collected_at, raw_payload, metadata, created_at
        """,
        (
            vote_id,
            person["id"],
            party["id"] if party else None,
            str(deputy["id"]),
            vote_value,
            vote_label,
            deputy.get("uri"),
            raw_record_id,
            evidence_id,
            source_updated_at,
            collected_at,
            Jsonb(dict(vote_member)),
            Jsonb(
                {
                    "deputy_name": deputy.get("nome"),
                    "party_acronym": deputy.get("siglaPartido"),
                    "state": deputy.get("siglaUf"),
                }
            ),
        ),
    )


def upsert_vote_summary_fact_and_claim(
    conn,
    *,
    source_id: str,
    vote_id: str,
    vote_evidence_id: str,
    vote_row: Mapping[str, Any],
    yes_votes: int,
    no_votes: int,
    other_votes: int,
    total_votes: int,
) -> dict[str, Any]:
    conn.execute(
        """
        DELETE FROM claims_evidence
        WHERE claim_id IN (
            SELECT id
            FROM claims
            WHERE subject_type = 'legislative_vote'
              AND subject_id = %s
              AND claim_type = 'official_fact'
        )
        """,
        (vote_id,),
    )
    conn.execute(
        """
        DELETE FROM claims
        WHERE subject_type = 'legislative_vote'
          AND subject_id = %s
          AND claim_type = 'official_fact'
        """,
        (vote_id,),
    )
    conn.execute(
        """
        DELETE FROM facts
        WHERE subject_type = 'legislative_vote'
          AND subject_id = %s
          AND predicate IN ('approved', 'yes_votes', 'no_votes', 'other_votes', 'total_votes')
        """,
        (vote_id,),
    )

    facts: list[dict[str, Any]] = []
    facts.append(
        _fetch_one(
            conn,
            """
            INSERT INTO facts (
                subject_type,
                subject_id,
                predicate,
                object_type,
                object_id,
                value_boolean,
                source_id,
                evidence_id,
                calculation_method,
                metadata
            )
            VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s, %s)
            RETURNING id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric, value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method, metadata, created_at
            """,
            (
                "legislative_vote",
                vote_id,
                "approved",
                "boolean",
                bool(vote_row.get("aprovacao")),
                source_id,
                vote_evidence_id,
                "camara.votacoes.aprovacao",
                Jsonb({"vote_external_id": vote_row["id"]}),
            ),
        )
    )
    for predicate, value in (
        ("yes_votes", yes_votes),
        ("no_votes", no_votes),
        ("other_votes", other_votes),
        ("total_votes", total_votes),
    ):
        facts.append(
            _fetch_one(
                conn,
                """
                INSERT INTO facts (
                    subject_type,
                    subject_id,
                    predicate,
                    object_type,
                    object_id,
                    value_numeric,
                    unit,
                    source_id,
                    evidence_id,
                    calculation_method,
                    metadata
                )
                VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s)
                RETURNING id, subject_type, subject_id, predicate, object_type, object_id, value_text, value_numeric, value_boolean, value_date, unit, effective_date, source_id, evidence_id, calculation_method, metadata, created_at
                """,
                (
                    "legislative_vote",
                    vote_id,
                    predicate,
                    "numeric",
                    value,
                    "votes",
                    source_id,
                    vote_evidence_id,
                    "camara.votacoes.votos",
                    Jsonb({"vote_external_id": vote_row["id"]}),
                ),
            )
        )

    claim = _fetch_one(
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
        VALUES (%s, %s, %s, %s, %s, NULL, NULL, %s)
        RETURNING id, claim_type, statement, subject_type, subject_id, calculation_method, model_provider, model_name, metadata, created_at
        """,
        (
            "official_fact",
            vote_row["descricao"],
            "legislative_vote",
            vote_id,
            "camara.votacoes.descricao",
            Jsonb(
                {
                    "vote_external_id": vote_row["id"],
                    "proposition_external_id": vote_row.get("proposicaoObjeto"),
                    "approved": bool(vote_row.get("aprovacao")),
                }
            ),
        ),
    )
    upsert_claim_evidence(conn, claim["id"], vote_evidence_id)
    return {
        "facts": facts,
        "claim": claim,
    }


def ingest_official_bundle(conn, bundle: Mapping[str, Any], *, source_checksum_value: str | None = None) -> dict[str, Any]:
    catalog = ensure_catalog(conn, bundle)
    source = catalog["source"]
    proposition = bundle["proposition"]
    vote = bundle["vote"]
    votes = list(bundle["votes"])
    now = datetime.now(timezone.utc)

    proposition_run = ensure_ingestion_run(
        conn,
        source_id=source["id"],
        dataset_id=catalog["proposition_dataset"]["id"],
        pipeline="connector-camara-legislative",
        run_type="fixture",
        payload=proposition,
        started_at=parse_iso_datetime(proposition.get("dataApresentacao")),
        finished_at=parse_iso_datetime(proposition.get("dataApresentacao")),
        metadata={
            "bundle_kind": "proposition",
            "vote_external_id": vote["id"],
        },
        records_read=1,
    )
    proposition_raw = upsert_raw_record(
        conn,
        source_id=source["id"],
        dataset_id=catalog["proposition_dataset"]["id"],
        ingestion_run_id=proposition_run["id"],
        external_id=str(proposition["id"]),
        payload=proposition,
        source_updated_at=parse_iso_datetime(proposition.get("statusProposicao", {}).get("dataHora")),
        collected_at=now,
        metadata={
            "bundle_kind": "proposition",
            "vote_external_id": vote["id"],
        },
    )
    proposition_evidence = upsert_evidence(
        conn,
        source_id=source["id"],
        dataset_id=catalog["proposition_dataset"]["id"],
        raw_record_id=proposition_raw["id"],
        external_id=f"proposition:{proposition['id']}",
        source_url=proposition.get("uri") or proposition.get("urlInteiroTeor"),
        section="proposicoes",
        collected_at=now,
        payload=proposition,
        metadata={
            "bundle_kind": "proposition",
            "proposition_external_id": str(proposition["id"]),
        },
    )
    proposition_row = upsert_proposition(
        conn,
        source_id=source["id"],
        dataset_id=catalog["proposition_dataset"]["id"],
        proposition_row=proposition,
        raw_record_id=proposition_raw["id"],
        evidence_id=proposition_evidence["id"],
        source_updated_at=parse_iso_datetime(proposition.get("statusProposicao", {}).get("dataHora")),
        collected_at=now,
    )

    vote_run = ensure_ingestion_run(
        conn,
        source_id=source["id"],
        dataset_id=catalog["vote_dataset"]["id"],
        pipeline="connector-camara-legislative",
        run_type="fixture",
        payload=vote,
        started_at=parse_iso_datetime(vote.get("dataHoraRegistro")),
        finished_at=parse_iso_datetime(vote.get("dataHoraRegistro")),
        metadata={
            "bundle_kind": "vote",
            "proposition_external_id": proposition["id"],
        },
        records_read=1,
    )
    vote_raw = upsert_raw_record(
        conn,
        source_id=source["id"],
        dataset_id=catalog["vote_dataset"]["id"],
        ingestion_run_id=vote_run["id"],
        external_id=str(vote["id"]),
        payload=vote,
        source_updated_at=parse_iso_datetime(vote.get("dataHoraRegistro")),
        collected_at=now,
        metadata={
            "bundle_kind": "vote",
            "proposition_external_id": str(proposition["id"]),
        },
    )
    vote_evidence = upsert_evidence(
        conn,
        source_id=source["id"],
        dataset_id=catalog["vote_dataset"]["id"],
        raw_record_id=vote_raw["id"],
        external_id=f"vote:{vote['id']}",
        source_url=vote.get("uri") or vote.get("uriEvento"),
        section="votacoes",
        collected_at=now,
        payload=vote,
        metadata={
            "bundle_kind": "vote",
            "vote_external_id": vote["id"],
        },
    )

    vote_members_count = len(votes)
    yes_votes = 0
    no_votes = 0
    other_votes = 0
    for vote_member in votes:
        vote_value, _ = _normalize_vote_value(vote_member.get("tipoVoto") or "desconhecido")
        if vote_value == "sim":
            yes_votes += 1
        elif vote_value == "nao":
            no_votes += 1
        else:
            other_votes += 1

    total_votes = yes_votes + no_votes
    vote_row_db = upsert_vote(
        conn,
        source_id=source["id"],
        dataset_id=catalog["vote_dataset"]["id"],
        proposition_id=proposition_row["id"],
        vote_row=vote,
        raw_record_id=vote_raw["id"],
        evidence_id=vote_evidence["id"],
        source_updated_at=parse_iso_datetime(vote.get("dataHoraRegistro")),
        collected_at=now,
        yes_votes=yes_votes,
        no_votes=no_votes,
        other_votes=other_votes,
        total_votes=total_votes,
    )

    vote_members_run = ensure_ingestion_run(
        conn,
        source_id=source["id"],
        dataset_id=catalog["vote_members_dataset"]["id"],
        pipeline="connector-camara-legislative",
        run_type="fixture",
        payload=votes,
        started_at=parse_iso_datetime(vote.get("dataHoraRegistro")),
        finished_at=parse_iso_datetime(vote.get("dataHoraRegistro")),
        metadata={
            "bundle_kind": "vote_members",
            "vote_external_id": vote["id"],
        },
        records_read=vote_members_count,
    )
    vote_members_raw = upsert_raw_record(
        conn,
        source_id=source["id"],
        dataset_id=catalog["vote_members_dataset"]["id"],
        ingestion_run_id=vote_members_run["id"],
        external_id=f"{vote['id']}:votos",
        payload=votes,
        source_updated_at=parse_iso_datetime(vote.get("dataHoraRegistro")),
        collected_at=now,
        metadata={
            "bundle_kind": "vote_members",
            "vote_external_id": vote["id"],
        },
    )
    vote_members_evidence = upsert_evidence(
        conn,
        source_id=source["id"],
        dataset_id=catalog["vote_members_dataset"]["id"],
        raw_record_id=vote_members_raw["id"],
        external_id=f"vote-members:{vote['id']}",
        source_url=vote.get("uri") or vote.get("uriEvento"),
        section="votacoes-votos",
        collected_at=now,
        payload=votes,
        metadata={
            "bundle_kind": "vote_members",
            "vote_external_id": vote["id"],
        },
    )

    vote_members: list[dict[str, Any]] = []
    people: list[dict[str, Any]] = []
    parties: list[dict[str, Any]] = []

    for vote_member in votes:
        member = upsert_vote_member(
            conn,
            source_id=source["id"],
            vote_id=vote_row_db["id"],
            vote_member=vote_member,
            raw_record_id=vote_members_raw["id"],
            evidence_id=vote_members_evidence["id"],
            source_updated_at=parse_iso_datetime(vote_member.get("dataRegistroVoto")),
            collected_at=now,
        )
        vote_members.append(member)
        person = _fetch_one(
            conn,
            """
            SELECT id, canonical_name, normalized_name, birth_date, birth_place, metadata, created_at, updated_at
            FROM people
            WHERE id = %s
            LIMIT 1
            """,
            (member["person_id"],),
        )
        people.append(person)
        if member["party_id"] is not None:
            party = _fetch_one(
                conn,
                """
                SELECT id, external_id, name, acronym, number, official_url, logo_url, metadata, created_at, updated_at
                FROM parties
                WHERE id = %s
                LIMIT 1
                """,
                (member["party_id"],),
            )
            parties.append(party)

    summary = upsert_vote_summary_fact_and_claim(
        conn,
        source_id=source["id"],
        vote_id=vote_row_db["id"],
        vote_evidence_id=vote_evidence["id"],
        vote_row=vote,
        yes_votes=yes_votes,
        no_votes=no_votes,
        other_votes=other_votes,
        total_votes=total_votes,
    )

    return {
        "source": source,
        "datasets": catalog,
        "ingestion_runs": {
            "proposition": proposition_run,
            "vote": vote_run,
            "vote_members": vote_members_run,
        },
        "raw_records": {
            "proposition": proposition_raw,
            "vote": vote_raw,
            "vote_members": vote_members_raw,
        },
        "evidence": {
            "proposition": proposition_evidence,
            "vote": vote_evidence,
            "vote_members": vote_members_evidence,
        },
        "proposition": proposition_row,
        "vote": vote_row_db,
        "vote_payload": vote,
        "vote_members": vote_members,
        "people": people,
        "parties": parties,
        "facts": summary["facts"],
        "claim": summary["claim"],
        "counts": {
            "yes_votes": yes_votes,
            "no_votes": no_votes,
            "other_votes": other_votes,
            "total_votes": total_votes,
            "member_count": len(votes),
        },
    }


def fetch_vote_summary(conn, vote_external_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            lv.id AS vote_id,
            lv.external_id AS vote_external_id,
            lv.house,
            lv.vote_date,
            lv.vote_timestamp,
            lv.description,
            lv.result,
            lv.vote_type,
            lv.approved,
            lv.total_votes,
            lv.yes_votes,
            lv.no_votes,
            lv.other_votes,
            lv.source_url,
            lv.raw_record_id,
            lv.evidence_id,
            lv.source_updated_at,
            lv.collected_at,
            lv.raw_payload,
            lv.metadata,
            lp.id AS proposition_id,
            lp.external_id AS proposition_external_id,
            lp.sigla_tipo,
            lp.number,
            lp.year,
            lp.title AS proposition_title,
            lp.summary AS proposition_summary,
            lp.presented_at AS proposition_presented_at,
            lp.status AS proposition_status,
            lp.source_url AS proposition_source_url,
            s.id AS source_id,
            s.slug AS source_slug,
            s.name AS source_name,
            s.institution AS source_institution,
            s.base_url AS source_base_url,
            s.documentation_url AS source_documentation_url,
            s.license AS source_license,
            d.id AS dataset_id,
            d.slug AS dataset_slug,
            d.name AS dataset_name,
            f.id AS approved_fact_id,
            f.value_boolean AS approved_fact_value,
            f.evidence_id AS approved_fact_evidence_id,
            yes_fact.value_numeric AS yes_fact_value,
            no_fact.value_numeric AS no_fact_value,
            other_fact.value_numeric AS other_fact_value,
            total_fact.value_numeric AS total_fact_value,
            c.id AS claim_id,
            c.statement AS claim_statement,
            c.calculation_method AS claim_calculation_method,
            c.metadata AS claim_metadata
        FROM legislative_votes AS lv
        JOIN legislative_propositions AS lp ON lp.id = lv.proposition_id
        JOIN sources AS s ON s.id = lv.source_id
        JOIN datasets AS d ON d.id = lv.dataset_id
        LEFT JOIN facts AS f
               ON f.subject_type = 'legislative_vote'
              AND f.subject_id = lv.id
              AND f.predicate = 'approved'
        LEFT JOIN facts AS yes_fact
               ON yes_fact.subject_type = 'legislative_vote'
              AND yes_fact.subject_id = lv.id
              AND yes_fact.predicate = 'yes_votes'
        LEFT JOIN facts AS no_fact
               ON no_fact.subject_type = 'legislative_vote'
              AND no_fact.subject_id = lv.id
              AND no_fact.predicate = 'no_votes'
        LEFT JOIN facts AS other_fact
               ON other_fact.subject_type = 'legislative_vote'
              AND other_fact.subject_id = lv.id
              AND other_fact.predicate = 'other_votes'
        LEFT JOIN facts AS total_fact
               ON total_fact.subject_type = 'legislative_vote'
              AND total_fact.subject_id = lv.id
              AND total_fact.predicate = 'total_votes'
        LEFT JOIN claims AS c
               ON c.subject_type = 'legislative_vote'
              AND c.subject_id = lv.id
              AND c.claim_type = 'official_fact'
        WHERE lv.external_id = %s
        LIMIT 1
        """,
        (vote_external_id,),
    ).fetchone()
    if row is None:
        raise KeyError(vote_external_id)

    members = conn.execute(
        """
        SELECT
            lvm.id,
            lvm.vote_id,
            lvm.person_id,
            lvm.party_id,
            lvm.external_id,
            lvm.vote_value,
            lvm.vote_label,
            lvm.source_url,
            lvm.raw_record_id,
            lvm.evidence_id,
            lvm.source_updated_at,
            lvm.collected_at,
            lvm.raw_payload,
            lvm.metadata,
            p.canonical_name,
            p.normalized_name,
            p.birth_date,
            p.birth_place,
            p.metadata AS person_metadata,
            party.external_id AS party_external_id,
            party.name AS party_name,
            party.acronym AS party_acronym,
            party.number AS party_number,
            party.metadata AS party_metadata
        FROM legislative_vote_members AS lvm
        JOIN people AS p ON p.id = lvm.person_id
        LEFT JOIN parties AS party ON party.id = lvm.party_id
        WHERE lvm.vote_id = %s
        ORDER BY
            CASE lvm.vote_value
                WHEN 'sim' THEN 0
                WHEN 'nao' THEN 1
                ELSE 2
            END,
            p.canonical_name
        """,
        (row["vote_id"],),
    ).fetchall()

    return {
        "source": {
            "id": row["source_id"],
            "slug": row["source_slug"],
            "name": row["source_name"],
            "institution": row["source_institution"],
            "base_url": row["source_base_url"],
            "documentation_url": row["source_documentation_url"],
            "license": row["source_license"],
        },
        "dataset": {
            "id": row["dataset_id"],
            "slug": row["dataset_slug"],
            "name": row["dataset_name"],
        },
        "proposition": {
            "id": row["proposition_id"],
            "external_id": row["proposition_external_id"],
            "sigla_tipo": row["sigla_tipo"],
            "number": row["number"],
            "year": row["year"],
            "title": row["proposition_title"],
            "summary": row["proposition_summary"],
            "presented_at": row["proposition_presented_at"],
            "status": row["proposition_status"],
            "source_url": row["proposition_source_url"],
            "raw_record_id": row["raw_record_id"],
            "evidence_id": row["evidence_id"],
            "source_updated_at": row["source_updated_at"],
            "collected_at": row["collected_at"],
            "raw_payload": row["raw_payload"],
            "metadata": row["metadata"],
        },
        "vote": {
            "id": row["vote_id"],
            "external_id": row["vote_external_id"],
            "house": row["house"],
            "vote_date": row["vote_date"],
            "vote_timestamp": row["vote_timestamp"],
            "description": row["description"],
            "result": row["result"],
            "vote_type": row["vote_type"],
            "approved": row["approved"],
            "total_votes": row["total_votes"],
            "yes_votes": row["yes_votes"],
            "no_votes": row["no_votes"],
            "other_votes": row["other_votes"],
            "source_url": row["source_url"],
            "raw_record_id": row["raw_record_id"],
            "evidence_id": row["evidence_id"],
            "source_updated_at": row["source_updated_at"],
            "collected_at": row["collected_at"],
            "raw_payload": row["raw_payload"],
            "metadata": row["metadata"],
        },
        "members": [dict(member) for member in members],
        "claim": {
            "id": row["claim_id"],
            "statement": row["claim_statement"],
            "calculation_method": row["claim_calculation_method"],
            "metadata": row["claim_metadata"],
        }
        if row["claim_id"]
        else None,
        "facts": {
            "approved": row["approved_fact_value"],
            "approved_evidence_id": row["approved_fact_evidence_id"],
            "yes_votes": row["yes_fact_value"],
            "no_votes": row["no_fact_value"],
            "other_votes": row["other_fact_value"],
            "total_votes": row["total_fact_value"],
        },
    }


def fetch_person_vote_history(conn, person_id: str, limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 50))
    rows = conn.execute(
        """
        SELECT
            lv.id AS vote_id,
            lv.external_id AS vote_external_id,
            lv.house,
            lv.vote_date,
            lv.vote_timestamp,
            lv.description,
            lv.result,
            lv.vote_type,
            lv.approved,
            lv.total_votes,
            lv.yes_votes,
            lv.no_votes,
            lv.other_votes,
            lv.source_url AS vote_source_url,
            lv.raw_record_id AS vote_raw_record_id,
            lv.evidence_id AS vote_evidence_id,
            lp.id AS proposition_id,
            lp.external_id AS proposition_external_id,
            lp.sigla_tipo,
            lp.number,
            lp.year,
            lp.title AS proposition_title,
            lp.summary AS proposition_summary,
            lp.presented_at AS proposition_presented_at,
            lp.status AS proposition_status,
            lp.source_url AS proposition_source_url,
            lvm.id AS member_vote_id,
            lvm.external_id AS member_external_id,
            lvm.vote_value,
            lvm.vote_label,
            lvm.source_url AS member_source_url,
            lvm.raw_record_id AS member_raw_record_id,
            lvm.evidence_id AS member_evidence_id,
            lvm.source_updated_at AS member_source_updated_at,
            lvm.collected_at AS member_collected_at,
            party.acronym AS party_acronym,
            party.name AS party_name,
            party.number AS party_number
        FROM legislative_vote_members AS lvm
        JOIN legislative_votes AS lv ON lv.id = lvm.vote_id
        JOIN legislative_propositions AS lp ON lp.id = lv.proposition_id
        LEFT JOIN parties AS party ON party.id = lvm.party_id
        WHERE lvm.person_id = %s
          AND lv.approved = true
        ORDER BY lv.vote_date DESC NULLS LAST, lv.vote_timestamp DESC NULLS LAST, lv.collected_at DESC
        LIMIT %s
        """,
        (person_id, limit),
    ).fetchall()

    history: list[dict[str, Any]] = []
    yes_votes = 0
    no_votes = 0
    other_votes = 0

    for row in rows:
        vote_value = row["vote_value"]
        if vote_value == "sim":
            yes_votes += 1
        elif vote_value == "nao":
            no_votes += 1
        else:
            other_votes += 1

        history.append(
            {
                "vote": {
                    "id": row["vote_id"],
                    "external_id": row["vote_external_id"],
                    "house": row["house"],
                    "vote_date": row["vote_date"],
                    "vote_timestamp": row["vote_timestamp"],
                    "description": row["description"],
                    "result": row["result"],
                    "vote_type": row["vote_type"],
                    "approved": row["approved"],
                    "total_votes": row["total_votes"],
                    "yes_votes": row["yes_votes"],
                    "no_votes": row["no_votes"],
                    "other_votes": row["other_votes"],
                    "source_url": row["vote_source_url"],
                    "raw_record_id": row["vote_raw_record_id"],
                    "evidence_id": row["vote_evidence_id"],
                },
                "proposition": {
                    "id": row["proposition_id"],
                    "external_id": row["proposition_external_id"],
                    "sigla_tipo": row["sigla_tipo"],
                    "number": row["number"],
                    "year": row["year"],
                    "title": row["proposition_title"],
                    "summary": row["proposition_summary"],
                    "presented_at": row["proposition_presented_at"],
                    "status": row["proposition_status"],
                    "source_url": row["proposition_source_url"],
                },
                "member_vote": {
                    "id": row["member_vote_id"],
                    "external_id": row["member_external_id"],
                    "vote_value": row["vote_value"],
                    "vote_label": row["vote_label"],
                    "party_acronym": row["party_acronym"],
                    "party_name": row["party_name"],
                    "party_number": row["party_number"],
                    "source_url": row["member_source_url"],
                    "raw_record_id": row["member_raw_record_id"],
                    "evidence_id": row["member_evidence_id"],
                    "source_updated_at": row["member_source_updated_at"],
                    "collected_at": row["member_collected_at"],
                },
            }
        )

    return {
        "votes": history,
        "counts": {
            "yes_votes": yes_votes,
            "no_votes": no_votes,
            "other_votes": other_votes,
            "total_votes": len(history),
        },
    }


def query_vote_response(conn, vote_external_id: str) -> dict[str, Any]:
    try:
        summary = fetch_vote_summary(conn, vote_external_id)
    except KeyError:
        return {
            "status": "no_evidence",
            "vote": None,
            "citations": [],
        }
    return {
        "status": "ok",
        "vote": summary,
        "citations": [
            {
                "evidence_id": summary["vote"]["evidence_id"],
                "source_url": summary["vote"]["source_url"],
                "raw_record_id": summary["vote"]["raw_record_id"],
            },
            {
                "evidence_id": summary["proposition"]["evidence_id"],
                "source_url": summary["proposition"]["source_url"],
                "raw_record_id": summary["proposition"]["raw_record_id"],
            },
        ],
    }


def query_recent_votes_response(conn, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    rows = conn.execute(
        """
        SELECT
            lv.external_id AS vote_external_id,
            lv.vote_date,
            lv.vote_timestamp,
            lv.description,
            lv.result,
            lv.vote_type,
            lv.approved,
            lv.total_votes,
            lv.yes_votes,
            lv.no_votes,
            lv.other_votes,
            lv.source_url,
            lv.raw_record_id AS vote_raw_record_id,
            lv.evidence_id AS vote_evidence_id,
            lp.id AS proposition_id,
            lp.external_id AS proposition_external_id,
            lp.sigla_tipo,
            lp.number,
            lp.year,
            lp.title AS proposition_title,
            lp.summary AS proposition_summary,
            lp.presented_at AS proposition_presented_at,
            lp.status AS proposition_status,
            lp.source_url AS proposition_source_url,
            lp.raw_record_id AS proposition_raw_record_id,
            lp.evidence_id AS proposition_evidence_id,
            s.id AS source_id,
            s.slug AS source_slug,
            s.name AS source_name,
            s.institution AS source_institution,
            s.base_url AS source_base_url,
            s.documentation_url AS source_documentation_url,
            s.license AS source_license,
            d.id AS dataset_id,
            d.slug AS dataset_slug,
            d.name AS dataset_name,
            (
                SELECT COUNT(*)
                FROM legislative_vote_members AS lvm
                WHERE lvm.vote_id = lv.id
            ) AS member_count
        FROM legislative_votes AS lv
        JOIN legislative_propositions AS lp ON lp.id = lv.proposition_id
        JOIN sources AS s ON s.id = lv.source_id
        JOIN datasets AS d ON d.id = lv.dataset_id
        WHERE lv.approved = true
        ORDER BY lv.vote_date DESC NULLS LAST, lv.vote_timestamp DESC NULLS LAST, lv.collected_at DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()

    votes = [
        {
            "source": {
                "id": row["source_id"],
                "slug": row["source_slug"],
                "name": row["source_name"],
                "institution": row["source_institution"],
                "base_url": row["source_base_url"],
                "documentation_url": row["source_documentation_url"],
                "license": row["source_license"],
            },
            "dataset": {
                "id": row["dataset_id"],
                "slug": row["dataset_slug"],
                "name": row["dataset_name"],
            },
            "proposition": {
                "id": row["proposition_id"],
                "external_id": row["proposition_external_id"],
                "house": CAMARA_HOUSE,
                "sigla_tipo": row["sigla_tipo"],
                "number": row["number"],
                "year": row["year"],
                "title": row["proposition_title"],
                "summary": row["proposition_summary"],
                "presented_at": row["proposition_presented_at"],
                "status": row["proposition_status"],
                "source_url": row["proposition_source_url"],
                "raw_record_id": row["proposition_raw_record_id"],
                "evidence_id": row["proposition_evidence_id"],
            },
            "vote": {
                "id": row["vote_external_id"],
                "external_id": row["vote_external_id"],
                "house": CAMARA_HOUSE,
                "vote_date": row["vote_date"],
                "vote_timestamp": row["vote_timestamp"],
                "description": row["description"],
                "result": row["result"],
                "vote_type": row["vote_type"],
                "approved": row["approved"],
                "total_votes": row["total_votes"],
                "yes_votes": row["yes_votes"],
                "no_votes": row["no_votes"],
                "other_votes": row["other_votes"],
                "source_url": row["source_url"],
                "raw_record_id": row["vote_raw_record_id"],
                "evidence_id": row["vote_evidence_id"],
            },
            "member_count": row["member_count"],
            "citations": [
                {
                    "evidence_id": row["vote_evidence_id"],
                    "source_url": row["source_url"],
                    "raw_record_id": row["vote_raw_record_id"],
                },
                {
                    "evidence_id": row["proposition_evidence_id"],
                    "source_url": row["proposition_source_url"],
                    "raw_record_id": row["proposition_raw_record_id"],
                },
            ],
        }
        for row in rows
    ]

    return {
        "status": "ok",
        "count": len(votes),
        "votes": votes,
    }


def query_proposition_response(conn, proposition_external_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            lp.id AS proposition_id,
            lp.external_id AS proposition_external_id,
            lp.house,
            lp.sigla_tipo,
            lp.number,
            lp.year,
            lp.title,
            lp.summary,
            lp.presented_at,
            lp.status,
            lp.source_url,
            lp.raw_record_id,
            lp.evidence_id,
            lp.source_updated_at,
            lp.collected_at,
            lp.raw_payload,
            lp.metadata,
            s.id AS source_id,
            s.slug AS source_slug,
            s.name AS source_name
        FROM legislative_propositions AS lp
        JOIN sources AS s ON s.id = lp.source_id
        WHERE lp.external_id = %s
        LIMIT 1
        """,
        (proposition_external_id,),
    ).fetchone()
    if row is None:
        return {
            "status": "no_evidence",
            "proposition": None,
            "votes": [],
        }

    votes = conn.execute(
        """
        SELECT
            lv.id,
            lv.external_id,
            lv.vote_date,
            lv.vote_timestamp,
            lv.description,
            lv.result,
            lv.vote_type,
            lv.approved,
            lv.total_votes,
            lv.yes_votes,
            lv.no_votes,
            lv.other_votes,
            lv.source_url,
            lv.raw_record_id,
            lv.evidence_id
        FROM legislative_votes AS lv
        WHERE lv.proposition_id = %s
        ORDER BY lv.vote_date DESC, lv.vote_timestamp DESC
        """,
        (row["proposition_id"],),
    ).fetchall()

    return {
        "status": "ok",
        "proposition": {
            "id": row["proposition_id"],
            "external_id": row["proposition_external_id"],
            "house": row["house"],
            "sigla_tipo": row["sigla_tipo"],
            "number": row["number"],
            "year": row["year"],
            "title": row["title"],
            "summary": row["summary"],
            "presented_at": row["presented_at"],
            "status": row["status"],
            "source_url": row["source_url"],
            "raw_record_id": row["raw_record_id"],
            "evidence_id": row["evidence_id"],
            "source_updated_at": row["source_updated_at"],
            "collected_at": row["collected_at"],
            "raw_payload": row["raw_payload"],
            "metadata": row["metadata"],
        },
        "votes": [dict(vote) for vote in votes],
    }
