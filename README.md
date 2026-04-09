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
