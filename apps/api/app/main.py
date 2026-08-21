from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from app.db import db_connection
from app.tse_v1 import fetch_candidate_summary

app = FastAPI(title="FonteAberta AI Service", version="0.2.0")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "fonteaberta-ai",
        "phase": "02-tse-v1",
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
