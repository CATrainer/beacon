# Setup & local development

## Prerequisites

- **Docker Desktop** (the only hard requirement for running the app).
- Optional, for working on the backend/frontend outside Docker: Python 3.12+,
  Node 22+.

## Run the stack

```bash
docker compose up --build
```

This starts four services:

| Service  | URL / port              | Notes                                  |
| -------- | ----------------------- | -------------------------------------- |
| frontend | http://localhost:5173   | Vite dev server (HMR)                  |
| backend  | http://localhost:8000   | FastAPI; `/docs` for OpenAPI UI        |
| worker   | (no port)               | arq worker — runs sourcing/AI jobs     |
| db       | localhost:5432          | Postgres 16 (`beacon`/`beacon`)        |
| redis    | localhost:6379          | Job queue (arq)                        |

On boot the backend runs migrations (`alembic upgrade head`) and idempotently
seeds the default **Clinics** and **Travel** lanes.

## Logging in

For **local Docker**, a login is auto-seeded on first boot (set via
`DEV_AUTOSEED_*` in `docker-compose.yml`, gated to `APP_ENV=local`):

- email: `caleb@heuricity.com`
- password: `beacon-local`

No command needed. To create your own credentials, change Peter's, or add users
(no public signup):

```bash
docker compose exec backend python -m app.scripts.seed_user \
  --email you@heuricity.com --name "Your Name"
```

Re-running with the same email updates that user's name/password. In production
there is no auto-seed — create the first user with this script (see
[DEPLOYMENT.md](DEPLOYMENT.md)).

## Environment variables

The app boots with **none** of these set. Copy the template and fill in keys as
you obtain them:

```bash
cp .env.example .env        # repo root
```

Compose loads the root `.env` into the backend automatically (infra wiring like
`DATABASE_URL` is forced to the compose services regardless). Restart the backend
after editing: `docker compose restart backend`.

### What each key unlocks and where to get it

| Variable | Unlocks | Where to get it |
| --- | --- | --- |
| `SECRET_KEY` | JWT signing (set a real one before any non-local use) | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ANTHROPIC_API_KEY` | Research briefs, drafting, directory ingest (slice 4+) | platform.claude.com → API keys |
| `CQC_SUBSCRIPTION_KEY` | CQC clinics source (slice 2) | api-portal.service.cqc.org.uk (free) |
| `GOOGLE_PLACES_API_KEY` | Wealth signals: reviews/rating (slice 2) | Google Cloud Console → Places API |
| `COMPANIES_HOUSE_API_KEY` | Director enrichment (slice 2) | developer.company-information.service.gov.uk |
| `PERPLEXITY_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | GEO pre-check engines (slice 5); each degrades independently | respective consoles |
| `HUNTER_API_KEY` + `EMAIL_RESOLVER_PROVIDER=hunter` | Email verification backstop (slice 4) | hunter.io |
| `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` | Gmail-draft sending (slice 7) | Google Cloud Console → OAuth client |
| `CAL_LINK` / `CAL_WEBHOOK_SECRET` | Booking link + booking detection (slice 8) | cal.com |

ATOL (travel), manual paste, and directory ingest need no key (directory ingest
uses the Anthropic key for extraction).

The model tier per stage is tunable without code: `MODEL_DEFAULT` (Sonnet),
`MODEL_HIGH` (Opus), `MODEL_CHEAP` (Haiku).

## Common commands

```bash
# Tail logs (backend or the job worker)
docker compose logs -f backend
docker compose logs -f worker

# Open a shell in the backend container
docker compose exec backend bash

# Run backend tests (SQLite-backed; no DB needed)
docker compose exec backend pytest
# …or locally:  cd backend && pytest

# Lint / autofix backend
cd backend && ruff check app tests          # or: ruff check --fix app tests

# Create a new migration after changing models
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head

# Frontend type-check
cd frontend && npm run typecheck

# Reset the database (destroys local data)
docker compose down -v && docker compose up --build
```

## Working without Docker (optional)

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements-dev.txt
# point DATABASE_URL at a local Postgres, then:
alembic upgrade head && uvicorn app.main:app --reload

# Frontend
cd frontend
npm install && npm run dev
```
