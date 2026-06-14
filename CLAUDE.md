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
    api/               system, auth, lanes, leads, sources, jobs, router
    adapters/          base (registry), cqc, atol, google_places,
                       directory_ingest, manual_paste, fixtures/
    services/          http, dedupe, qualification, sourcing, scoring, research,
                       contacts, email_resolver, geo, ai, companies_house
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
                       ResearchLane, GeoCheckLane
    pages/             Login, Queue, Lanes, LaneEditor, LeadDetail
docker-compose.yml
docs/                  SETUP, DEPLOYMENT, MAINTENANCE
```

## Data model

`users`, `lanes`, `jobs`, `leads` (+ `source_hits`, `research_briefs`,
`geo_checks`, `contacts`, `evidence`, `emails`, `activity_log`), `suppression`.
A lead carries
funnel `stage` and CRM `status` independently, sub-scores in `score_breakdown`
JSONB, and a `dedupe_key` (unique per lane).

## Current state

**Slice 5 complete** — Stage-4b GEO gap pre-check (`app/services/geo.py`): runs the
lane's buyer-intent queries (templates filled with the lead's location +
high-ticket service) through engine APIs (Perplexity/OpenAI/Gemini) behind
graceful degradation; an LLM extraction classifies named/recommended/competitors/
cited-sources; `severity_and_hook` → gap severity + hook type (absence /
weak_presence / no_gap), aggregated into `gap_score` which feeds `final_score`.
**Triage only, never the deliverable** — disclaimer enforced in code (`GEO_DISCLAIMER`),
API (`GET /api/geo/disclaimer`), and UI. No engine key → graceful no-op (no
fabricated gap) unless `force_fixtures`. Gated to top-N / on-demand
(`POST /lanes/{id}/geo`, `.../geo/estimate`). New GEO_CHECK job + worker fn. Lead
detail shows GEO results. Verified live (fixtures): gap 90 → final recomputed.
Backend: 43 tests pass, ruff clean; frontend builds.

Earlier: Slice 4 — Stage-4a research agent (`research.py`) + contact waterfall
(`contacts.py` / `email_resolver.py`), reachability → final; Slice 3 — Stage-3
scoring + ranked queue; Slice 2 — adapters + Stage-2 qualification + worker;
Slice 1 — scaffold/auth/lanes.

Next: **Slice 6** — prep workflow screen (audit-query copy-out, screenshot
upload, draft generation/edit, approve → queue).

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
- [ ] 6 — Prep workflow screen (checklist, query copy-out, screenshot upload, drafting).
- [ ] 7 — Gmail-draft sending + send queue + CRM/pipeline + activity log.
- [ ] 8–10 — follow-ups/booking, managed-send, directory/manual adapters & polish.
