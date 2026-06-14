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
  `MODEL_CHEAP` = Haiku `claude-haiku-4-5`). **Route all JSON extraction through
  `app/services/ai.py::complete_json`**, which uses *forced tool use* (one tool
  whose `input_schema` is the desired shape + `tool_choice` pinned to it). This is
  stable across SDK versions; the newer `output_config`/`messages.parse` API is
  NOT supported by the pinned SDK — don't reintroduce it without bumping the SDK.
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
    models/            base, types, enums, user, lane, lead (+ children), job
    schemas/           auth, lane (LaneConfig), lead, job
    api/               system, auth, lanes, leads, sources, prep, crm,
                       integrations, jobs, router
    adapters/          base (registry), cqc, atol, google_places,
                       directory_ingest, manual_paste, fixtures/
    services/          http, dedupe, qualification, sourcing, scoring, research,
                       contacts, email_resolver, geo, drafting, sender, sending,
                       app_settings, ai, companies_house
    uploads served at /uploads (StaticFiles, dir = settings.uploads_dir)
    worker.py / queue.py   arq worker + enqueue helper
    seeds/lanes.py     Default Clinics & Travel lanes
    scripts/           seed_user.py, seed_lanes.py, seed_dev_user.py
  alembic/             Migration env + versions/
  tests/               SQLite-backed pytest suite
frontend/
  src/
    main.tsx, App.tsx  Bootstrap + routing (+ RequireAuth)
    lib/api.ts         Fetch wrapper (JWT, errors, OAuth2 login)
    lib/auth.tsx       Auth context
    types.ts           API types (mirror backend schemas)
    components/        Layout, JobProgress, RunSources, ManualAdd, ReScore,
                       ResearchLane, GeoCheckLane, PrepChecklist
    pages/             Login, Queue, Pipeline, Lanes, LaneEditor, LeadDetail, Settings
docker-compose.yml
docs/                  SETUP, DEPLOYMENT, MAINTENANCE
```

## Data model

`users`, `lanes`, `jobs`, `leads` (+ `source_hits`, `research_briefs`,
`geo_checks`, `contacts`, `evidence`, `emails`, `activity_log`), `suppression`,
`oauth_credentials`, `app_settings`. A lead carries
funnel `stage` and CRM `status` independently, sub-scores in `score_breakdown`
JSONB, and a `dedupe_key` (unique per lane).

## Current state

**Slice 7 complete — MVP (slices 1–7) done.** Gmail-draft sending + send queue +
CRM. `app/services/sender.py` (swappable Sender: GmailSender via OAuth, LogSender
fallback that simulates drafts; google libs lazy-imported), `app/services/sending.py`
(send queue: per-identity daily cap, send window, randomised spacing, suppression
check, never auto-sends LOW-confidence). `app/api/integrations.py` (Gmail OAuth
connect/callback/status), `app/api/crm.py` (`/send/process`, `/settings/sending`,
`/suppression`, `/pipeline`, `/leads/{id}/status`, `/leads/{id}/activity`).
Operator-editable settings in `app_settings` table; Gmail tokens in
`oauth_credentials`. UI: Settings (Gmail + sending + suppression), Pipeline board,
activity log + status control on the lead. Verified live: approve → process →
simulated draft, lead SENT, pipeline + activity updated. 59 tests pass, ruff clean.

Earlier: Slice 6 — prep workflow (`prep.py`/`drafting.py`): audit-query copy-out,
screenshot upload (served at `/uploads`), Opus drafts under §8 constraints, edit
inline, approve → queue. Slice 5 — GEO gap pre-check (`geo.py`) → gap severity.
Slice 4 — research agent + contact waterfall. Slice 3 — scoring + ranked queue.
Slice 2 — adapters + Stage-2 qualification + worker. Slice 1 — scaffold/auth/lanes.

**MVP complete (slices 1–7).** Next up are the scale-ups (design-doc 8–10):
follow-ups + reply/booking detection (Cal.com webhook); managed-send mode
(flag-gated, per-identity caps, scheduling); DirectoryIngest/ManualPaste polish.

### Adapters & background work (slice 2)
- Adapter contract + registry: `app/adapters/base.py`. Add a source = new class
  with `@register` + a fixture file; reference its `key` in a lane's
  `config.sources`. Fixtures in `app/adapters/fixtures/` make every source run
  keyless.
- Orchestration: `app/services/sourcing.py` (fetch → dedupe/merge → qualify →
  CH enrich). Dedupe: `app/services/dedupe.py`. Qualify: `app/services/qualification.py`.
- Polite fetching (UA, rate limit, robots): `app/services/http.py`.
- AI helper (structured JSON, cost estimate): `app/services/ai.py`.
- Jobs: `app/models/job.py`, enqueue `app/queue.py` (falls back to inline
  BackgroundTasks if Redis is down), worker `app/worker.py` (compose `worker`
  service runs `arq app.worker.WorkerSettings`).

## Build Order checklist (MVP = 1–7)

- [x] 1 — Skeleton + data model + auth + Lane CRUD UI; empty queue.
- [x] 2 — Stage 1–2: primary adapters per lane + qualification + job runner.
- [x] 3 — Stage 3 scoring + queue ranking UI with score breakdowns.
- [x] 4 — Stage 4a research agent + contact waterfall.
- [x] 5 — Stage 4b GEO pre-check + gap severity into ranking.
- [x] 6 — Prep workflow screen (checklist, query copy-out, screenshot upload, drafting).
- [x] 7 — Gmail-draft sending + send queue + CRM/pipeline + activity log. **MVP done.**
- [ ] 8–10 — follow-ups/booking, managed-send, directory/manual adapters & polish.
