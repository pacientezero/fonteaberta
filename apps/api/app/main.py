from datetime import datetime, timezone

from fastapi import FastAPI

app = FastAPI(title="FonteAberta AI Service", version="0.1.0")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "fonteaberta-ai",
        "phase": "00-bootstrap",
        "status": "ok",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
