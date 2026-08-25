#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402


EXPECTED_ROUTES = {
    "/",
    "/health",
    "/tse/candidatos",
    "/tse/candidatos/{sq_candidato}",
    "/v1/economic/bcb/selic",
    "/v1/economic/bcb/selic/{observation_date}",
    "/v1/economic/ibge/ipca",
    "/v1/economic/ibge/ipca/{period}",
    "/v1/government/camara/deputados/{deputy_id}",
    "/v1/government/camara/votacoes",
    "/v1/government/camara/votacoes/{vote_id}",
    "/v1/government/camara/votacoes/{vote_id}/votos",
    "/v1/government/senado/senadores/{mandate_identifier}",
    "/v1/government/transparencia/despesas",
    "/v1/government/transparencia/despesas/{expense_period}",
    "/v1/government/transparencia/despesas/{expense_period}/{external_id}",
    "/v1/government/comprasgov/fornecedores",
    "/v1/government/comprasgov/fornecedores/{external_id}",
    "/v1/government/tesouro/rreo/{exercise}/{period}/{entity_code}",
    "/v1/government/tesouro/rreo/{exercise}/{period}/{entity_code}/{external_id}",
}


def main() -> int:
    route_paths = {route.path for route in app.routes if getattr(route, "methods", None)}
    missing = sorted(EXPECTED_ROUTES.difference(route_paths))
    if missing:
        raise SystemExit(f"Missing API routes: {missing}")

    print(
        json.dumps(
            {
                "verified_routes": sorted(EXPECTED_ROUTES),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
