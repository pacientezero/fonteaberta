from datetime import datetime, timezone
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

from app.db import db_connection
from app.documents_rag import (
    hashed_embedding,
    index_document_bundle,
    query_documents,
    resolve_query_scope,
)
from app.camara_expansion import query_mandate_response as query_camara_mandate_response
from app.camara_legislative import (
    query_proposition_response as query_camara_proposition_response,
)
from app.camara_legislative import query_recent_votes_response as query_camara_recent_votes_response
from app.camara_legislative import query_vote_response as query_camara_vote_response
from app.bcb_expansion import fetch_series_summary, query_observation_response
from app.ibge_expansion import fetch_series_summary as fetch_ibge_series_summary
from app.ibge_expansion import query_observation_response as query_ibge_observation_response
from app.comprasgov_expansion import (
    COMPRASGOV_ACTIVE,
    COMPRASGOV_PAGE,
    COMPRASGOV_PAGE_SIZE,
    query_supplier_response,
    query_supplier_row_response,
)
from app.senado_expansion import query_mandate_response as query_senado_mandate_response
from app.tse_v1 import fetch_candidate_summary, query_candidate_catalog_response
from app.tesouro_expansion import (
    TESOURO_ANEXO,
    query_rreo_response,
    query_rreo_row_response,
)
from app.transparencia_expansion import (
    query_expense_response,
    query_expense_row_response,
)

app = FastAPI(title="FonteAberta AI Service", version="0.3.0")
logger = logging.getLogger("fonteaberta.api")


@app.middleware("http")
async def add_security_and_observability_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    started_at = time.perf_counter()

    response = await call_next(request)

    duration_ms = (time.perf_counter() - started_at) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"

    logger.info(
        "request method=%s path=%s status=%s request_id=%s duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
        duration_ms,
    )
    return response


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "fonteaberta-ai",
        "phase": "05-expansion",
        "status": "ok",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/tse/candidatos/{sq_candidato}")
def tse_candidate(sq_candidato: str) -> dict[str, object]:
    with db_connection() as connection:
        try:
            return fetch_candidate_summary(connection, sq_candidato)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Candidate not found") from exc


@app.get("/tse/candidatos")
def tse_candidate_catalog(limit: int = 20) -> dict[str, object]:
    with db_connection() as connection:
        return query_candidate_catalog_response(connection, limit=limit)


@app.post("/v1/entities/resolve")
def resolve_entities(payload: dict[str, object]) -> dict[str, object]:
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    return resolve_query_scope(question)


@app.post("/v1/embed")
def embed(payload: dict[str, object]) -> dict[str, object]:
    texts = payload.get("texts")
    if not isinstance(texts, list) or not texts:
        raise HTTPException(status_code=400, detail="texts must be a non-empty list")
    return {
        "model": "hashed-bow",
        "dimension": 384,
        "embeddings": [hashed_embedding(str(text)) for text in texts],
    }


@app.post("/v1/documents/index")
def index_documents(payload: dict[str, object]) -> dict[str, object]:
    if "source" not in payload or "document" not in payload or "version" not in payload:
        raise HTTPException(status_code=400, detail="source, document and version are required")
    with db_connection() as connection:
        return index_document_bundle(connection, payload)


@app.post("/v1/query")
def rag_query(payload: dict[str, object]) -> dict[str, object]:
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    limit = int(payload.get("limit", 5))
    with db_connection() as connection:
        return query_documents(connection, question, limit=limit)


@app.get("/v1/economic/bcb/selic")
def bcb_selic_summary() -> dict[str, object]:
    with db_connection() as connection:
        try:
            return fetch_series_summary(connection)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Selic series not found") from exc


@app.get("/v1/economic/bcb/selic/{observation_date}")
def bcb_selic_observation(observation_date: str) -> dict[str, object]:
    with db_connection() as connection:
        try:
            return query_observation_response(connection, observation_date)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Selic series not found") from exc


@app.get("/v1/economic/ibge/ipca")
def ibge_ipca_summary() -> dict[str, object]:
    with db_connection() as connection:
        try:
            return fetch_ibge_series_summary(connection)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="IPCA series not found") from exc


@app.get("/v1/economic/ibge/ipca/{period}")
def ibge_ipca_observation(period: str) -> dict[str, object]:
    with db_connection() as connection:
        try:
            return query_ibge_observation_response(connection, period)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="IPCA series not found") from exc


@app.get("/v1/government/camara/deputados/{deputy_id}")
def camara_deputado_mandate(deputy_id: str, legislature_id: int = 57) -> dict[str, object]:
    with db_connection() as connection:
        return query_camara_mandate_response(connection, deputy_id, legislature_id)


@app.get("/v1/government/camara/proposicoes/{proposition_id}")
def camara_proposition(proposition_id: str) -> dict[str, object]:
    with db_connection() as connection:
        return query_camara_proposition_response(connection, proposition_id)


@app.get("/v1/government/camara/votacoes/{vote_id}")
def camara_vote(vote_id: str) -> dict[str, object]:
    with db_connection() as connection:
        return query_camara_vote_response(connection, vote_id)


@app.get("/v1/government/camara/votacoes")
def camara_votes(limit: int = 15) -> dict[str, object]:
    with db_connection() as connection:
        return query_camara_recent_votes_response(connection, limit=limit)


@app.get("/v1/government/camara/votacoes/{vote_id}/votos")
def camara_vote_members(vote_id: str) -> dict[str, object]:
    with db_connection() as connection:
        response = query_camara_vote_response(connection, vote_id)
        if response["status"] != "ok":
            return response
        return {
            "status": response["status"],
            "members": response["vote"]["members"],
            "vote": response["vote"]["vote"],
            "proposition": response["vote"]["proposition"],
            "citations": response["citations"],
        }


@app.get("/v1/government/senado/senadores/{mandate_identifier}")
def senado_mandate(mandate_identifier: str) -> dict[str, object]:
    with db_connection() as connection:
        return query_senado_mandate_response(connection, mandate_identifier)


@app.get("/v1/government/transparencia/despesas")
def transparencia_expenses_latest() -> dict[str, object]:
    with db_connection() as connection:
        return query_expense_response(connection)


@app.get("/v1/government/transparencia/despesas/{expense_period}")
def transparencia_expenses_summary(expense_period: str) -> dict[str, object]:
    with db_connection() as connection:
        return query_expense_response(connection, expense_period)


@app.get("/v1/government/transparencia/despesas/{expense_period}/{external_id}")
def transparencia_expenses_detail(expense_period: str, external_id: str) -> dict[str, object]:
    with db_connection() as connection:
        return query_expense_row_response(connection, expense_period, external_id)


@app.get("/v1/government/comprasgov/fornecedores")
def comprasgov_suppliers(
    page: int = COMPRASGOV_PAGE,
    page_size: int = COMPRASGOV_PAGE_SIZE,
    active: bool = COMPRASGOV_ACTIVE,
) -> dict[str, object]:
    with db_connection() as connection:
        return query_supplier_response(connection, page, page_size, active)


@app.get("/v1/government/comprasgov/fornecedores/{external_id}")
def comprasgov_supplier(
    external_id: str,
    page: int = COMPRASGOV_PAGE,
    page_size: int = COMPRASGOV_PAGE_SIZE,
    active: bool = COMPRASGOV_ACTIVE,
) -> dict[str, object]:
    with db_connection() as connection:
        return query_supplier_row_response(connection, external_id, page, page_size, active)


@app.get("/v1/government/tesouro/rreo/{exercise}/{period}/{entity_code}")
def tesouro_rreo_summary(exercise: int, period: int, entity_code: int, annex: str = TESOURO_ANEXO) -> dict[str, object]:
    with db_connection() as connection:
        return query_rreo_response(connection, entity_code, exercise, period, annex)


@app.get("/v1/government/tesouro/rreo/{exercise}/{period}/{entity_code}/{external_id}")
def tesouro_rreo_detail(
    exercise: int,
    period: int,
    entity_code: int,
    external_id: str,
    annex: str = TESOURO_ANEXO,
) -> dict[str, object]:
    with db_connection() as connection:
        return query_rreo_row_response(connection, entity_code, exercise, period, external_id, annex)
