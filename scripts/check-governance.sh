#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker compose -f "$repo_root/docker-compose.yml" exec -T postgres \
  psql -U "${POSTGRES_USER:-fonteaberta}" \
       -d "${POSTGRES_DB:-fonteaberta}" \
       -v ON_ERROR_STOP=1 \
       < "$repo_root/tests/data_governance_smoke.sql"
