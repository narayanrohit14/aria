#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/.local-demo/logs"
PID_DIR="$ROOT_DIR/.local-demo/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

LOCAL_DATABASE_URL="${LOCAL_DATABASE_URL:-postgresql://aria:aria@localhost:5432/aria}"
LOCAL_POSTGRES_URL="${LOCAL_POSTGRES_URL:-postgresql+asyncpg://aria:aria@localhost:5432/aria}"
LOCAL_REDIS_URL="${LOCAL_REDIS_URL:-redis://localhost:6379}"
LOCAL_API_URL="${LOCAL_API_URL:-http://localhost:8000}"
LOCAL_FRONTEND_URL="${LOCAL_FRONTEND_URL:-http://localhost:3000}"
ARIA_LOCAL_DEMO_SEED_LIMIT="${ARIA_LOCAL_DEMO_SEED_LIMIT:-100000}"
ARIA_LOCAL_DEMO_SEED="${ARIA_LOCAL_DEMO_SEED:-auto}"
ARIA_LOCAL_DEMO_AGENT="${ARIA_LOCAL_DEMO_AGENT:-auto}"

export DATABASE_URL="$LOCAL_DATABASE_URL"
export POSTGRES_URL="$LOCAL_POSTGRES_URL"
export REDIS_URL="$LOCAL_REDIS_URL"
export ARIA_ENV="${ARIA_ENV:-development}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export ARIA_API_URL="$LOCAL_API_URL"
export NEXT_PUBLIC_API_URL="$LOCAL_API_URL"
export NEXT_PUBLIC_WS_URL="${NEXT_PUBLIC_WS_URL:-ws://localhost:8000}"
export ARIA_AGENT_CONTEXT_SOURCE="${ARIA_AGENT_CONTEXT_SOURCE:-api}"

log() {
  printf '[ARIA local demo] %s\n' "$1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

is_port_open() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-60}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$label is ready"
      return 0
    fi
    sleep 1
  done

  log "$label did not become ready at $url"
  return 1
}

wait_for_postgres() {
  for _ in $(seq 1 60); do
    if docker compose exec -T postgres pg_isready -U aria -d aria >/dev/null 2>&1; then
      log "Postgres is ready"
      return 0
    fi
    sleep 1
  done

  log "Postgres did not become ready"
  return 1
}

start_background() {
  local name="$1"
  shift

  local log_file="$LOG_DIR/${name}.log"
  log "Starting $name. Logs: $log_file"
  "$@" >"$log_file" 2>&1 &
  echo "$!" >"$PID_DIR/${name}.pid"
}

stop_background() {
  for pid_file in "$PID_DIR"/*.pid; do
    [ -e "$pid_file" ] || continue
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}

cleanup() {
  log "Stopping local demo processes"
  stop_background
}

trap cleanup EXIT INT TERM

seed_tables_exist() {
  DATABASE_URL="$LOCAL_DATABASE_URL" .venv/bin/python backend/scripts/check_db_counts.py \
    >"$LOG_DIR/db-counts.log" 2>&1
}

seed_database_if_needed() {
  if [ "$ARIA_LOCAL_DEMO_SEED" = "never" ]; then
    log "Skipping database seed because ARIA_LOCAL_DEMO_SEED=never"
    return 0
  fi

  if [ "$ARIA_LOCAL_DEMO_SEED" = "auto" ] && seed_tables_exist; then
    if grep -q "aria_transactions: 0" "$LOG_DIR/db-counts.log"; then
      log "Local seed tables exist but transactions are empty"
    else
      log "Local seed tables already contain data"
      cat "$LOG_DIR/db-counts.log"
      return 0
    fi
  fi

  if [ ! -f backend/data/sample-data/transactions_data.csv ]; then
    log "Raw sample CSVs are missing. Skipping DB seed; demo findings will still be created."
    return 0
  fi

  log "Seeding local Postgres representative dataset (${ARIA_LOCAL_DEMO_SEED_LIMIT} transactions max)"
  ARIA_SEED_MODE=representative \
    ARIA_SEED_REPRESENTATIVE_TX_LIMIT="$ARIA_LOCAL_DEMO_SEED_LIMIT" \
    ARIA_SEED_CSV_BATCH_SIZE=5000 \
    ARIA_SEED_FRAUD_BATCH_SIZE=25000 \
    ARIA_SEED_MAX_RETRIES=4 \
    DATABASE_URL="$LOCAL_DATABASE_URL" \
    .venv/bin/python backend/scripts/seed_railway_postgres.py \
    >"$LOG_DIR/seed.log" 2>&1

  DATABASE_URL="$LOCAL_DATABASE_URL" .venv/bin/python backend/scripts/check_db_counts.py
}

create_demo_findings() {
  log "Creating demo audit findings if the findings table is empty"
  .venv/bin/python - <<'PY'
import json
import urllib.error
import urllib.request

BASE = "http://localhost:8000"

def request(path, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status == 204:
            return None
        return json.loads(response.read().decode())

try:
    current = request("/api/v1/findings?limit=1")
    if current and current.get("total", 0) > 0:
        print("Demo findings already exist")
        raise SystemExit(0)
except urllib.error.HTTPError as exc:
    print(f"Could not inspect findings: {exc}")
    raise SystemExit(0)

findings = [
    {
        "title": "Elevated fraud-label concentration in representative sample",
        "criteria": "Fraud monitoring controls should identify anomalous transaction behavior and maintain calibrated alert thresholds.",
        "condition": "The seeded representative dataset includes a concentrated population of fraud-positive transaction labels for demonstration analysis.",
        "cause": "Representative seeding intentionally preserves fraud-positive cases to support model and audit workflow demonstrations on local infrastructure.",
        "consequence": "Without clear threshold governance, fraud queues can over-prioritize recall and create operational review burden.",
        "corrective_action": "Document demo sampling assumptions and calibrate production thresholds against full-population fraud prevalence.",
        "risk_level": "HIGH",
    },
    {
        "title": "Manual review workflow requires escalation evidence",
        "criteria": "High-risk transaction alerts should retain evidence of review, escalation, and disposition.",
        "condition": "The current demo workflow surfaces high-risk transactions but does not yet capture full reviewer disposition history.",
        "cause": "Case-management persistence is planned after the core voice and risk-analysis demo path.",
        "consequence": "Audit teams may lack a defensible trail for management action and follow-up validation.",
        "corrective_action": "Add review status, owner, disposition notes, and remediation due dates to the transaction analysis workflow.",
        "risk_level": "MEDIUM",
    },
    {
        "title": "Model monitoring dashboard needs production SLA thresholds",
        "criteria": "Model risk governance should define acceptable performance thresholds, drift triggers, and retraining cadence.",
        "condition": "The local dashboard reports model and dataset metrics but does not yet enforce production alert thresholds.",
        "cause": "Phase-one demo scope prioritized end-to-end interaction over full MRM control automation.",
        "consequence": "Performance degradation could go undetected without formal thresholding and ownership.",
        "corrective_action": "Define model monitoring KRIs for precision, recall, fraud rate drift, and feature stability.",
        "risk_level": "LOW",
    },
]

for finding in findings:
    created = request("/api/v1/findings", method="POST", payload=finding)
    print(f"Created finding: {created['title']}")
PY
}

require_cmd docker
require_cmd curl
require_cmd lsof

if [ ! -x .venv/bin/python ]; then
  log "Missing .venv. Create it and install dependencies first."
  exit 1
fi

if [ ! -d frontend/node_modules ]; then
  log "Missing frontend/node_modules. Run: cd frontend && npm install"
  exit 1
fi

log "Starting local infrastructure"
docker compose up postgres redis -d
wait_for_postgres

log "Running database migrations"
(cd backend/api && DATABASE_URL="$LOCAL_DATABASE_URL" POSTGRES_URL="$LOCAL_POSTGRES_URL" ../../.venv/bin/alembic upgrade head)

seed_database_if_needed

if is_port_open 8000; then
  log "Port 8000 is already in use; assuming FastAPI is running"
else
  start_background api .venv/bin/uvicorn backend.api.main:app --reload --port 8000
fi
wait_for_http "$LOCAL_API_URL/health" "FastAPI"

create_demo_findings

if is_port_open 3000; then
  log "Port 3000 is already in use; assuming Next.js is running"
else
  start_background frontend bash -lc "cd frontend && NEXT_PUBLIC_API_URL='$LOCAL_API_URL' NEXT_PUBLIC_WS_URL='ws://localhost:8000' npm run dev"
fi
wait_for_http "$LOCAL_FRONTEND_URL" "Next.js" 90

if [ "$ARIA_LOCAL_DEMO_AGENT" != "never" ]; then
  if [ -n "${LIVEKIT_URL:-}" ] || grep -q "^LIVEKIT_URL=." .env 2>/dev/null; then
    if is_port_open 8081; then
      log "Port 8081 is already in use; assuming LiveKit agent worker is running"
    else
      start_background agent .venv/bin/python -m backend.agent.agent start
    fi
  else
    log "Skipping voice agent because LIVEKIT_URL is not configured. Set ARIA_LOCAL_DEMO_AGENT=never to silence this."
  fi
fi

log "Local demo is running:"
log "  Frontend: $LOCAL_FRONTEND_URL"
log "  API:      $LOCAL_API_URL"
log "  Logs:     $LOG_DIR"
log "Press Ctrl+C to stop API/frontend/agent. Docker Postgres/Redis will remain running."

while true; do
  sleep 3600
done
