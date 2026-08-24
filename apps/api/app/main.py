from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from app.db import db_connection
from app.documents_rag import (
    hashed_embedding,
    index_document_bundle,
    query_documents,
    resolve_query_scope,
)
from app.bcb_expansion import fetch_series_summary, query_observation_response
from app.ibge_expansion import fetch_series_summary as fetch_ibge_series_summary
from app.ibge_expansion import query_observation_response as query_ibge_observation_response
from app.tse_v1 import fetch_candidate_summary

app = FastAPI(title="FonteAberta AI Service", version="0.3.0")


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
