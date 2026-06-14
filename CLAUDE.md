# CLAUDE.md — Beacon

Context for contributors (human or AI) working in this repo. Keep the **Current
State** and **Project Structure** sections accurate — see
[docs/MAINTENANCE.md](docs/MAINTENANCE.md) for the doc-update checklist that must
run at the end of every change.

## What this is

Beacon is Heuricity's internal lead engine & GEO-audit CRM. Two users. Internal
only. Built in working slices per the design doc's Build Order. The MVP is slices
1–7.

## Tech stack

- **Backend:** FastAPI, **synchronous** SQLAlchemy 2.0 (psycopg3), Alembic,
  Pydantic v2, PyJWT + passlib[bcrypt]. Python 3.12. DB-touching endpoints are
  plain `def` (run in FastAPI's threadpool) — do not introduce async sessions
  without a deliberate reason.
- **Frontend:** React 18 + Vite + TypeScript, TanStack Query, React Router v7,
  Tailwind v3. Dense internal-tool UI; honour focus-visible & reduced-motion.
- **Background jobs (slice 2+):** `arq` on Redis.
- **AI (slice 4+):** `anthropic` SDK. Model per stage is config (`MODEL_DEFAULT`
  = Sonnet `claude-sonnet-4-6`, `MODEL_HIGH` = Opus `claude-opus-4-8`,
  `MODEL_CHEAP` = Haiku `claude-haiku-4-5`). Use adaptive thinking + structured
  output (`output_config.format` / `messages.parse`).
- **Run:** Docker Compose locally (db, redis, backend, frontend). Prod: Railway
  (backend/pg/redis) + Vercel (frontend).

## Conventions

- Everything external lives behind an interface and **degrades gracefully when
  its key is missing** — the app must boot and run with an empty `.env`.
  `/api/status` reports what's configured; the UI shows it.
- Settings come only from `app/config.py` (`Settings`). Add `*_enabled` helpers
  for new optional integrations.
- Enums are VARCHAR-backed (`native_enum=False`) — see `app/models/enums.py`.
- JSONB via `app/models/types.py` (`JSONB`) so models stay portable (Postgres in
  prod, SQLite in tests).
- Lanes are **data, not code** — `LaneConfig` (`app/schemas/lane.py`) validates
  the config blob.
- Money-spending AI (stage 4) only runs on top-N / on-demand, never the whole
  universe; show a running cost estimate.
- Never auto-send email without a per-lead human approval step.
- Tests run on SQLite (no DB dependency): `cd backend && pytest`.
- Lint: `ruff check app tests` (line length 100).

## Project structure

```
backend/
  app/
    main.py            FastAPI app + CORS + router wiring
    config.py          Settings (all env vars + *_enabled helpers)
    db.py              Engine, SessionLocal, get_db
    core/              security.py (hash/JWT), deps.py (current user)
    models/            base, types, enums, user, lane, lead (+ children)
    schemas/           auth, lane (LaneConfig), lead
    api/               system (health/status), auth, lanes, leads, router
    seeds/lanes.py     Default Clinics & Travel lanes
    scripts/           seed_user.py, seed_lanes.py
  alembic/             Migration env + versions/
  tests/               SQLite-backed pytest suite
frontend/
  src/
    main.tsx, App.tsx  Bootstrap + routing (+ RequireAuth)
    lib/api.ts         Fetch wrapper (JWT, errors, OAuth2 login)
    lib/auth.tsx       Auth context
    types.ts           API types (mirror backend schemas)
    components/Layout.tsx
    pages/             Login, Queue, Lanes, LaneEditor
docker-compose.yml
docs/                  SETUP, DEPLOYMENT, MAINTENANCE
```

## Data model (slice 1)

`users`, `lanes`, `leads` (+ `source_hits`, `research_briefs`, `geo_checks`,
`contacts`, `evidence`, `emails`, `activity_log`), `suppression`. A lead carries
funnel `stage` and CRM `status` independently, sub-scores in `score_breakdown`
JSONB, and a `dedupe_key` (unique per lane).

## Current state

**Slice 1 complete** — monorepo scaffold, full data model + initial migration,
JWT auth + seed scripts, Lane CRUD (API + UI), empty ranked-queue view, Docker
compose, docs. Backend: 8 tests pass, ruff clean.

Next: **Slice 2** — source adapters (CQC, ATOL, Google Places, Companies House,
directory ingest, manual paste) + Stage-2 qualification + background job runner.

## Build Order checklist (MVP = 1–7)

- [x] 1 — Skeleton + data model + auth + Lane CRUD UI; empty queue.
- [ ] 2 — Stage 1–2: primary adapters per lane + qualification + job runner.
- [ ] 3 — Stage 3 scoring + queue ranking UI with score breakdowns.
- [ ] 4 — Stage 4a research agent + contact waterfall.
- [ ] 5 — Stage 4b GEO pre-check + gap severity into ranking.
- [ ] 6 — Prep workflow screen (checklist, query copy-out, screenshot upload, drafting).
- [ ] 7 — Gmail-draft sending + send queue + CRM/pipeline + activity log.
- [ ] 8–10 — follow-ups/booking, managed-send, directory/manual adapters & polish.
