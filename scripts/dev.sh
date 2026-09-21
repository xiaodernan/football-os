#!/usr/bin/env bash
# Start the API and the web app for local development.
#   scripts/dev.sh            -> api :8731 + web :3210
#   scripts/dev.sh api        -> API only
#   scripts/dev.sh web        -> web only
#   scripts/dev.sh infra      -> PostgreSQL + pgvector in Docker
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8731}"
WEB_PORT="${WEB_PORT:-3210}"
TARGET="${1:-all}"

if [[ "$TARGET" == "infra" ]]; then
  docker compose -f "$ROOT/infra/docker-compose.yml" up -d db
  echo "PostgreSQL on localhost:54321 (pgvector). Set DATABASE_URL=postgresql+psycopg2://football:football@localhost:54321/football_os in apps/api/.env"
  exit 0
fi

if [[ "$TARGET" == "all" || "$TARGET" == "api" ]]; then
  (cd "$ROOT/apps/api" && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$API_PORT") &
  API_PID=$!
  trap 'kill $API_PID 2>/dev/null || true' EXIT
  echo "API  -> http://127.0.0.1:$API_PORT/api/v1/healthz"
fi

if [[ "$TARGET" == "all" || "$TARGET" == "web" ]]; then
  (cd "$ROOT/apps/web" && npm run dev -- --port "$WEB_PORT")
fi
