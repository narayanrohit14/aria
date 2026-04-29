# ARIA Local Demo

This fallback path runs ARIA locally without Railway. It uses Docker Postgres/Redis,
the local FastAPI backend, the local Next.js frontend, and the local LiveKit agent
worker if LiveKit credentials are present in `.env`.

## One-command start

```bash
./infra/run-local-demo.sh
```

Then open:

```text
http://localhost:3000
```

The script:

- Starts local Postgres and Redis with `docker compose`.
- Runs Alembic migrations.
- Seeds a representative local dataset if raw sample files are present.
- Starts FastAPI at `http://localhost:8000`.
- Creates three demo audit findings if none exist.
- Starts Next.js at `http://localhost:3000`.
- Starts the local LiveKit voice agent if LiveKit credentials are configured.

## Useful options

Use a smaller local seed for speed:

```bash
ARIA_LOCAL_DEMO_SEED_LIMIT=25000 ./infra/run-local-demo.sh
```

Skip database seeding:

```bash
ARIA_LOCAL_DEMO_SEED=never ./infra/run-local-demo.sh
```

Skip the voice agent:

```bash
ARIA_LOCAL_DEMO_AGENT=never ./infra/run-local-demo.sh
```

## Logs

Logs are written to:

```text
.local-demo/logs/
```

Common files:

- `api.log`
- `frontend.log`
- `agent.log`
- `seed.log`
- `db-counts.log`

## Voice demo note

The app is fully local except for LiveKit/OpenAI/Cartesia/AssemblyAI cloud APIs.
For the voice demo, keep these values in `.env`:

```text
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
OPENAI_API_KEY=
CARTESIA_API_KEY=
ASSEMBLYAI_API_KEY=
```

If those are not available, the dashboard, findings, health, dataset summary,
and transaction analysis demo still run locally.
