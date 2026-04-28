# ARIA

ARIA (Audit Risk & Insights Agent) is a monorepo for building a real-time audit and risk intelligence platform. It combines a web frontend, backend APIs and agent services, ML workflows, and infrastructure tooling in one repository.

## Tech Stack

- Next.js for the frontend application
- FastAPI for backend APIs and agent-facing services
- PostgreSQL for transactional and analytical data storage
- Redis for caching, queues, and short-lived state
- LiveKit for real-time voice and media workflows
- XGBoost for risk scoring and predictive models

## Quickstart

1. Copy the environment template and fill in secrets.
2. Start local dependencies.
3. Run the frontend and backend services.

```bash
cp .env.example .env
docker compose up -d

# placeholder commands
cd frontend && npm install && npm run dev
cd backend/api && uvicorn main:app --reload
```

## Structure

- `frontend/` contains the Next.js application
- `backend/api/` contains FastAPI endpoints
- `backend/agent/` contains agent orchestration code
- `backend/data/` contains data-access and ingestion code
- `ml/` contains training and inference workflows
- `infra/docker/` contains container and local environment assets

## LiveKit Voice Agent Demo

The real ARIA voice experience runs as three services:

- `aria-api` creates LiveKit room tokens and exposes audit/data APIs.
- `aria-frontend` joins a LiveKit room from `/session` and publishes microphone audio.
- `aria-agent` runs `backend/agent/agent.py`, joins LiveKit rooms, and speaks with the selected Cartesia voice.

Required Railway variables for `aria-agent`:

```bash
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
OPENAI_API_KEY=
CARTESIA_API_KEY=
ASSEMBLYAI_API_KEY=
ARIA_API_URL=https://your-api-domain.up.railway.app
```

Required Railway variables for `aria-frontend`:

```bash
ARIA_API_URL=https://your-api-domain.up.railway.app
NEXT_PUBLIC_WS_URL=wss://your-api-domain.up.railway.app
```

Do not set `NEXT_PUBLIC_API_URL` to `localhost` in Railway. If it is unset, the frontend uses its `/api/backend` proxy and `ARIA_API_URL`.

## Seeding Railway Postgres

The full ARIA sample dataset is intentionally not committed to GitHub. The CSV
and JSON files under `backend/data/sample-data/` are too large for normal Git
hosting and are ignored by `.gitignore`.

Keep these files local:

- `backend/data/sample-data/transactions_data.csv`
- `backend/data/sample-data/cards_data.csv`
- `backend/data/sample-data/users_data.csv`
- `backend/data/sample-data/mcc_codes.json`
- `backend/data/sample-data/train_fraud_labels.json`

Set your Railway Postgres connection string locally:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DBNAME"
```

Then seed the database from the repo root:

```bash
python backend/scripts/seed_railway_postgres.py
```

For small Railway Postgres instances, use representative mode instead of the
full 13M-row transaction load:

```bash
ARIA_SEED_MODE=representative \
ARIA_SEED_REPRESENTATIVE_TX_LIMIT=250000 \
ARIA_SEED_CSV_BATCH_SIZE=5000 \
ARIA_SEED_FRAUD_BATCH_SIZE=25000 \
python backend/scripts/seed_railway_postgres.py
```

Representative mode keeps all users, cards, MCC codes, all fraud-positive
labeled transactions, and enough non-fraud context transactions to preserve
useful deployed behavior without requiring the full database footprint.

Verify row counts:

```bash
python backend/scripts/check_db_counts.py
```

If a partial remote seed fills the database, inspect size and optionally remove
only the ARIA seed tables:

```bash
python backend/scripts/db_size_report.py

ARIA_CONFIRM_RESET=yes python backend/scripts/reset_seed_tables.py
```

The seed script creates `aria_users`, `aria_cards`, `aria_transactions`,
`aria_mcc_codes`, and `aria_fraud_labels`. CSV files are streamed through
PostgreSQL `COPY`, and fraud labels are loaded in batches so the full dataset is
not held in memory. The load is idempotent: rerunning the script will not
duplicate rows.
