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

## What ARIA Is

ARIA is an audit risk assessment copilot. It combines structured transaction
analytics, model-assisted fraud risk scoring, dashboard summaries, findings
workflows, and a LiveKit-powered conversational interface. The intended use is
to help internal audit teams prioritize review areas, interrogate risk drivers,
and draft better questions and findings faster.

ARIA is not designed to replace auditor judgment, issue final audit opinions,
make disciplinary decisions, block transactions, or serve as an autonomous
regulatory reporting system. Its output should be treated as decision support:
useful for triage, exploration, and evidence organization, but subject to human
review before any audit conclusion is recorded.

## Model Performance

The current fraud risk model is an XGBoost binary classifier trained to rank
transactions by likely fraud risk. It is paired with a transparent risk scorer
that converts model probability and business risk factors into LOW, MEDIUM, and
HIGH portfolio risk categories.

| Attribute | Current value |
| --- | --- |
| Model family | XGBoost classifier |
| Intended task | Fraud likelihood and audit risk triage |
| Validation method | 5-fold stratified cross-validation |
| Training/evaluation sample size | 335,017 transactions |
| Fraud-positive cases | 1,135 |
| Observed fraud rate | 0.339% |
| Mean F1 score | 0.580 +/- 0.014 |
| Mean precision | 0.525 +/- 0.032 |
| Mean recall | 0.651 +/- 0.028 |
| Mean ROC-AUC | 0.9917 +/- 0.0024 |
| Operating threshold | 0.49 |

The high ROC-AUC indicates strong ranking separation between ordinary and
higher-risk transactions. The moderate precision and recall are expected in an
imbalanced fraud setting where positives are rare. Practically, this means ARIA
is strongest as a prioritization and sampling tool: it can surface a meaningful
review queue, but its alerts are not proof of fraud and its non-alerts are not a
guarantee of absence.

The current operating threshold of `0.49` balances precision and recall for the
demo model. In production, that threshold should be governed by audit risk
appetite, review capacity, false-positive tolerance, and the consequences of
missed issues. Threshold changes should be versioned and reviewed, not adjusted
ad hoc.

## Risk Scoring Approach

ARIA separates predictive modeling from audit risk scoring so that auditors can
understand and challenge the final risk posture. The transaction risk score is a
weighted composite of:

- Model fraud probability
- Transaction amount percentile
- Amount-to-credit-limit ratio
- PIN staleness
- No-chip card indicator
- Customer credit score component

Scores are clipped to a 0-100 range and mapped into risk categories. The latest
artifact metadata shows approximately 11.16% of scored transactions in HIGH
risk, 3.68% in MEDIUM risk, and 96.20% in LOW risk. This distribution is meant
to focus audit attention without claiming that every high-risk transaction is
fraudulent.

## Internal Audit Applications

ARIA is built for internal audit workflows where the core question is not only
"is this transaction fraudulent?" but also "where should audit spend scarce
review time?" Useful applications include:

- Risk assessment scoping: identify products, customer segments, merchants, or
  transaction patterns that justify deeper audit procedures.
- Audit planning: convert model and portfolio signals into candidate audit
  objectives, control hypotheses, and sampling strategies.
- Control testing support: surface unusual patterns such as high-risk merchant
  categories, limit pressure, stale authentication behavior, or concentrated
  exposure.
- Findings development: help auditors structure observations, potential root
  causes, risk impact, and recommended next steps.
- Executive reporting: summarize portfolio risk posture and explain why the
  audit team is prioritizing specific areas.
- Interactive review: allow auditors to ask natural-language questions while
  staying grounded in the loaded data and API-backed summaries.

The conversational agent is especially useful when an auditor needs to move
quickly from a dashboard signal to investigative questions. Instead of forcing a
linear dashboard-only workflow, ARIA lets the auditor ask, clarify, interrupt,
and redirect the review in real time.

## ARB Review Board Defense

For an Architecture Review Board or AI governance review, the defensible
position is that ARIA is a controlled audit-assistive system, not an autonomous
decisioning system. The core controls are:

- Human-in-the-loop: ARIA recommends, summarizes, and prioritizes; auditors own
  conclusions, workpapers, and final sign-off.
- Bounded scope: the system is limited to audit risk assessment, transaction
  review support, and findings assistance.
- Transparent model card: model family, metrics, training sample size,
  threshold, and limitations are documented in this repository.
- Explainable risk score: the risk category is based on visible risk factors,
  not an opaque conversational-only judgment.
- Environment isolation: production configuration comes from Railway variables;
  secrets are not hardcoded or committed.
- Data minimization: full raw sample datasets are intentionally excluded from
  GitHub, and Railway is seeded through controlled scripts.
- Operational diagnostics: deployment checks verify database connectivity,
  expected table counts, LiveKit configuration presence, and frontend URL
  configuration.
- Reproducibility: model artifacts, threshold files, and evaluation reports are
  stored under `ml/artifacts/` for inspection.
- Auditability: API routes, seed scripts, and diagnostic tooling create a
  traceable path from data load to dashboard and session behavior.

Key risks and mitigations:

| Risk | Mitigation |
| --- | --- |
| Hallucinated or unsupported explanations | Keep conclusions grounded in API/database summaries; require auditor review before use in workpapers. |
| Overreliance on AI output | Position ARIA as triage and drafting support, not final audit evidence or final opinion. |
| False positives | Treat alerts as review candidates; tune threshold to audit capacity and document reviewer disposition. |
| False negatives | Do not use ARIA as the sole control; combine with standard audit procedures and sampling. |
| Data drift | Revalidate metrics periodically and compare current population characteristics to training data. |
| Prompt injection or unsafe tool use | Keep agent capabilities bounded to approved APIs and avoid arbitrary filesystem or credential access. |
| Confidentiality exposure | Use managed secrets, avoid committed datasets, and restrict production access through platform controls. |
| Operational misconfiguration | Run deployment diagnostics and require production URL validation so localhost fallbacks cannot silently leak into Railway. |

Recommended approval posture: approve ARIA for a controlled pilot in audit risk
assessment and audit planning, with human review, documented limitations, and
read-only or assistive use. Do not approve ARIA for autonomous control
operation, final audit opinion generation, direct customer impact decisions, or
regulatory filing without additional validation, monitoring, access controls,
and model risk governance.

## LiveKit Voice Agent Demo

The real ARIA voice experience runs as two deployed app services plus a LiveKit
agent worker. For the current demo, the agent worker can run locally from your
Mac and still join the deployed LiveKit room. For a fully productionized setup,
the same worker can later be deployed as its own Railway service.

- `aria-api` creates LiveKit room tokens and exposes audit/data APIs.
- `aria-frontend` joins a LiveKit room from `/session` and publishes microphone audio.
- Local or deployed agent worker runs `backend/agent/agent.py`, joins LiveKit rooms, and speaks with the selected Cartesia voice.

Required variables for the local or deployed agent worker:

```bash
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
OPENAI_API_KEY=
CARTESIA_API_KEY=
ASSEMBLYAI_API_KEY=
ARIA_API_URL=https://your-api-domain.up.railway.app
ARIA_AGENT_CONTEXT_SOURCE=api
```

Run the local worker from the repo root:

```bash
.venv/bin/python -m backend.agent.agent start
```

Required Railway variables for `aria-frontend`:

```bash
ARIA_API_URL=https://your-api-domain.up.railway.app
NEXT_PUBLIC_API_URL=https://your-api-domain.up.railway.app
NEXT_PUBLIC_WS_URL=wss://your-api-domain.up.railway.app
NEXT_PUBLIC_LIVEKIT_URL=wss://your-livekit-project.livekit.cloud
```

Required Railway variables for `aria-api`:

```bash
DATABASE_URL=
LIVEKIT_URL=wss://your-livekit-project.livekit.cloud
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
ENVIRONMENT=production
ARIA_ENV=production
FRONTEND_URL=https://your-frontend-domain.up.railway.app
```

Do not set any production URL variable to `localhost`. In production the
frontend requires `NEXT_PUBLIC_API_URL`, the server-side proxy uses
`ARIA_API_URL` or `API_INTERNAL_URL`, and subtitle websockets use the FastAPI
backend websocket endpoint. LiveKit media is separate: `/api/v1/sessions`
returns the `livekit_url` and token that the browser uses to join the LiveKit
room.

Run deployment diagnostics without printing secrets:

```bash
python backend/scripts/diagnose_deployment.py
cd frontend && NODE_ENV=production npm run diagnose:env
```

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
