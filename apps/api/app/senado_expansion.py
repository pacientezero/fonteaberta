from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

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

BR_TZ = ZoneInfo("America/Sao_Paulo")
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = next(
    (
        parent
        for parent in CURRENT_FILE.parents
        if (parent / "tests" / "fixtures" / "senado" / "senadores_em_exercicio_57.json").exists()
    ),
    CURRENT_FILE.parent.parent,
)
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "senado" / "senadores_em_exercicio_57.json"

SENADO_SOURCE_SLUG = "senado"
SENADO_DATASET_SLUG = "senadores-em-exercicio-57"
SENADO_DATASET_EXTERNAL_ID = "senado-senadores-em-exercicio-57"
SENADO_LEGISLATURE_EXTERNAL_ID = "senado-legislatura-57"
SENADO_CHAMBER = "senado"


def load_fixture_bundle(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_br_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    if "T" in value:
        parsed = parse_iso_datetime(value)
        if parsed is not None:
            return parsed.astimezone(BR_TZ)
    return datetime.strptime(value, "%d/%m/%Y %H:%M:%S").replace(tzinfo=BR_TZ)


def get_snapshot_datetime(bundle: Mapping[str, Any]) -> datetime:
    snapshot_value = bundle["snapshot"]["ListaParlamentarEmExercicio"]["Metadados"]["Versao"]
    snapshot_dt = parse_br_datetime(snapshot_value)
    if snapshot_dt is None:
        raise ValueError("Senado snapshot version is missing")
    return snapshot_dt


def select_current_exercise(mandate_payload: Mapping[str, Any], snapshot_dt: datetime) -> dict[str, Any]:
    exercises_payload = mandate_payload.get("Exercicios") or {}
    exercises = exercises_payload.get("Exercicio") or []
    if isinstance(exercises, Mapping):
        exercises = [exercises]

    matches: list[dict[str, Any]] = []
    snapshot_date = snapshot_dt.date()
    for exercise in exercises:
        start_date = parse_iso_date(exercise.get("DataInicio"))
        end_date = parse_iso_date(exercise.get("DataFim"))
        if start_date is None:
            continue
        if snapshot_date < start_date:
            continue
        if end_date is not None and snapshot_date > end_date:
            continue
        matches.append(dict(exercise))

    if not matches:
        raise ValueError("Senado mandate does not expose a current exercise")
    if len(matches) > 1:
        raise ValueError("Senado mandate current exercise is ambiguous")
    return matches[0]


def resolve_legislature_number(mandate_payload: Mapping[str, Any], snapshot_dt: datetime) -> str:
    snapshot_date = snapshot_dt.date()
    matches: list[str] = []
    for key in ("PrimeiraLegislaturaDoMandato", "SegundaLegislaturaDoMandato"):
        legislature = mandate_payload.get(key) or {}
        start_date = parse_iso_date(legislature.get("DataInicio"))
        end_date = parse_iso_date(legislature.get("DataFim"))
        if start_date is None:
            continue
        if snapshot_date < start_date:
            continue
        if end_date is not None and snapshot_date > end_date:
            continue
        legislature_number = legislature.get("NumeroLegislatura")
        if legislature_number is not None:
            matches.append(str(legislature_number))

    if not matches:
        raise ValueError("Senado mandate does not resolve a legislature for the snapshot date")
    if len(matches) > 1:
        raise ValueError("Senado mandate matches multiple legislatures for the snapshot date")
    return matches[0]


def resolve_party_id(conn, party_acronym: str | None) -> str | None:
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


def ensure_ingestion_run(
    conn,
    *,
    source_id: str,
    dataset_id: str,
    bundle: Mapping[str, Any],
    source_checksum_value: str | None,
) -> dict[str, Any]:
    list_meta = bundle["snapshot"]["ListaParlamentarEmExercicio"]["Metadados"]
    collected_at = parse_iso_datetime(bundle.get("raw_record", {}).get("collected_at")) or datetime.now(timezone.utc)
    started_at = collected_at
    finished_at = collected_at
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
        (source_id, dataset_id, "connector-senado-expansion", source_checksum_value),
    )
    if existing is not None:
        return existing

    metadata = dict(bundle.get("ingestion_run", {}).get("metadata") or {})
    metadata.setdefault("source_update_version", list_meta.get("Versao"))
    metadata.setdefault("snapshot_version", list_meta.get("Versao"))
    metadata.setdefault("service_version", list_meta.get("VersaoServico"))
    metadata.setdefault("selected_parliamentarians", len(bundle.get("selected_parliamentarians") or []))
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
            "connector-senado-expansion",
            "full",
            started_at,
            finished_at,
            "success",
            len(bundle.get("selected_parliamentarians") or []),
            len(bundle.get("selected_parliamentarians") or []),
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
    payload = bundle["snapshot"]
    collected_at = parse_iso_datetime(raw_record_payload.get("collected_at")) or datetime.now(timezone.utc)
    source_updated_at = parse_br_datetime(payload["ListaParlamentarEmExercicio"]["Metadados"]["Versao"])
    metadata = dict(raw_record_payload.get("metadata") or {})
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
            raw_record_payload.get("external_id", f"{SENADO_DATASET_EXTERNAL_ID}-snapshot"),
            Jsonb(payload),
            source_checksum_value or payload_hash(payload),
            source_updated_at.date() if source_updated_at else None,
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
            evidence_payload.get("external_id", f"{SENADO_DATASET_EXTERNAL_ID}-evidence"),
            evidence_payload.get(
                "source_url",
                bundle["snapshot"]["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"][0]["IdentificacaoParlamentar"]["UrlPaginaParlamentar"],
            ),
            evidence_payload.get("page"),
            evidence_payload.get("section", "senadores em exercicio"),
            parse_iso_datetime(evidence_payload.get("collected_at")) or datetime.now(timezone.utc),
            evidence_payload.get("payload_hash", payload_hash(bundle["snapshot"])),
            Jsonb(metadata),
        ),
    )


def ensure_person(
    conn,
    source_id: str,
    senator_bundle: Mapping[str, Any],
    *,
    snapshot_dt: datetime,
) -> dict[str, Any]:
    list_row = senator_bundle["list_row"]
    list_ident = list_row["IdentificacaoParlamentar"]
    mandate = list_row["Mandato"]
    exercise = select_current_exercise(mandate, snapshot_dt)
    legislature_number = resolve_legislature_number(mandate, snapshot_dt)
    external_id = str(list_ident["CodigoParlamentar"])
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

    canonical_name = list_ident.get("NomeCompletoParlamentar") or list_ident.get("NomeParlamentar")
    display_name = list_ident.get("NomeParlamentar")
    metadata = {
        "display_name": display_name,
        "public_code": list_ident.get("CodigoPublicoNaLegAtual"),
        "party_acronym": list_ident.get("SiglaPartidoParlamentar"),
        "state": list_ident.get("UfParlamentar"),
        "legislature": legislature_number,
        "mandate_code": mandate["CodigoMandato"],
        "exercise_code": exercise.get("CodigoExercicio"),
        "role": mandate.get("DescricaoParticipacao"),
        "forma_tratamento": list_ident.get("FormaTratamento"),
        "sex": list_ident.get("SexoParlamentar"),
        "profile_url": list_ident.get("UrlPaginaParlamentar"),
        "photo_url": list_ident.get("UrlFotoParlamentar"),
        "email": list_ident.get("EmailParlamentar"),
        "bloco": list_ident.get("Bloco"),
        "member_mesa": list_ident.get("MembroMesa"),
        "member_lideranca": list_ident.get("MembroLideranca"),
        "phones": list_ident.get("Telefones"),
        "list_url": "https://legis.senado.leg.br/dadosabertos/senador/lista/atual?v=4",
        "snapshot_version": snapshot_dt.isoformat(),
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
                None,
                None,
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
                display_name,
                Jsonb(
                    {
                        "codigo_parlamentar": external_id,
                        "public_code": list_ident.get("CodigoPublicoNaLegAtual"),
                        "mandate_code": mandate.get("CodigoMandato"),
                        "exercise_code": exercise.get("CodigoExercicio"),
                        "party_acronym": list_ident.get("SiglaPartidoParlamentar"),
                        "state": list_ident.get("UfParlamentar"),
                    }
                ),
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
            birth_date = %s,
            birth_place = %s,
            metadata = %s
        WHERE id = %s
        RETURNING id, canonical_name, normalized_name, birth_date, birth_place, metadata, created_at, updated_at
        """,
        (
            canonical_name,
            normalize_name(canonical_name),
            None,
            None,
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
            display_name,
            Jsonb(
                {
                    "codigo_parlamentar": external_id,
                    "public_code": list_ident.get("CodigoPublicoNaLegAtual"),
                    "mandate_code": mandate.get("CodigoMandato"),
                    "exercise_code": exercise.get("CodigoExercicio"),
                    "party_acronym": list_ident.get("SiglaPartidoParlamentar"),
                    "state": list_ident.get("UfParlamentar"),
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
    senator_bundle: Mapping[str, Any],
    snapshot_dt: datetime,
) -> dict[str, Any]:
    list_row = senator_bundle["list_row"]
    list_ident = list_row["IdentificacaoParlamentar"]
    mandate = list_row["Mandato"]
    exercise = select_current_exercise(mandate, snapshot_dt)
    mandate_external_id = f"senado-mandato-{mandate['CodigoMandato']}-exercicio-{exercise['CodigoExercicio']}"
    legislature_number = resolve_legislature_number(mandate, snapshot_dt)
    party_acronym = list_ident.get("SiglaPartidoParlamentar")
    party_id = resolve_party_id(conn, party_acronym)
    started_at = parse_iso_date(exercise.get("DataInicio"))
    ended_at = parse_iso_date(exercise.get("DataFim"))
    source_updated_at = snapshot_dt.date()
    metadata = {
        "list_url": "https://legis.senado.leg.br/dadosabertos/senador/lista/atual?v=4",
        "bloco": list_ident.get("Bloco"),
        "phones": list_ident.get("Telefones"),
        "current_legislature": legislature_number,
        "exercise_code": exercise.get("CodigoExercicio"),
        "exercise_start": exercise.get("DataInicio"),
        "snapshot_version": snapshot_dt.isoformat(),
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
        (source_id, mandate_external_id),
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
            mandate_external_id,
            f"{SENADO_LEGISLATURE_EXTERNAL_ID}-{legislature_number}",
            SENADO_CHAMBER,
            list_ident.get("NomeParlamentar"),
            list_ident.get("UfParlamentar"),
            party_acronym,
            "em_exercicio",
            list_ident.get("EmailParlamentar"),
            list_ident.get("UrlPaginaParlamentar"),
            list_ident.get("UrlFotoParlamentar"),
            started_at,
            ended_at,
            source_updated_at,
            parse_iso_datetime(senator_bundle.get("raw_record", {}).get("collected_at")) or datetime.now(timezone.utc),
            Jsonb({"list_row": list_row}),
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
    statement_value = mandate["electoral_name"]
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
            statement_value,
            None,
            None,
            effective_date,
            None,
            effective_date,
            source_id,
            evidence_id,
            "senado.senador.lista.atual",
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
    snapshot_date = mandate.get("source_updated_at")
    snapshot_label = snapshot_date.strftime("%d/%m/%Y") if snapshot_date else "data da coleta"
    statement = (
        f"Em {snapshot_label}, {person['canonical_name']} constava como senador em exercício "
        f"pela {legislature_number}ª legislatura."
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
            "senado.senador.lista.atual",
            "manual",
            "senado-expansion",
            Jsonb(
                {
                    "fact_id": str(fact_id),
                    "mandate_id": str(mandate["id"]),
                    "legislature_number": legislature_number,
                }
            ),
        ),
    )


def ingest_official_bundle(conn, bundle: Mapping[str, Any], *, source_checksum_value: str | None = None) -> dict[str, Any]:
    source = ensure_source(conn, bundle["source"])
    dataset = ensure_dataset(conn, source["id"], bundle["dataset"])
    snapshot_dt = get_snapshot_datetime(bundle)
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
    for senator_bundle in bundle["selected_parliamentarians"]:
        person = ensure_person(conn, source["id"], senator_bundle, snapshot_dt=snapshot_dt)
        mandate = ensure_mandate(
            conn,
            source_id=source["id"],
            dataset_id=dataset["id"],
            person_id=person["id"],
            senator_bundle=senator_bundle,
            snapshot_dt=snapshot_dt,
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
            f.value_text AS fact_value_text,
            f.predicate AS fact_predicate,
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
              AND rr.external_id = %s
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
        (f"{SENADO_DATASET_EXTERNAL_ID}-snapshot", mandate_external_id),
    )
    if row is None:
        raise KeyError(mandate_external_id)
    return row


def query_mandate_response(conn, mandate_identifier: str) -> dict[str, Any]:
    if mandate_identifier.startswith("senado-mandato-"):
        mandate_external_id = mandate_identifier
    else:
        mandate_external_id = f"senado-mandato-{mandate_identifier}"
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
