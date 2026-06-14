# Beacon

Heuricity's internal lead engine & GEO-audit CRM. Beacon sources, qualifies,
scores, researches and GEO-audits potential clients, presents them as a
quality-ranked queue, supports a human-in-the-loop prep step (including the
manual ChatGPT/Gemini/Perplexity screenshot work), drafts personalised outreach,
and manages a send / follow-up queue. It is also Heuricity's CRM.

Two users (Caleb and Peter). Internal only — no public surface, no multi-tenant,
no billing.

---

## Quick start (local, Docker)

You need **Docker Desktop** running. Nothing else — the whole stack boots with
zero API keys.

```bash
# 1. From the repo root, start everything (Postgres, Redis, API, web):
docker compose up --build

# 2. In a second terminal, create your login (one-time):
docker compose exec backend python -m app.scripts.seed_user \
  --email caleb@heuricity.com --name "Caleb Trainer"
# (you'll be prompted for a password)

# 3. Open the app:
#    Web UI   → http://localhost:5173
#    API docs → http://localhost:8000/docs
```

The default **Clinics** and **Travel** lanes are seeded automatically on first
boot. The queue is empty until sourcing lands (Build Order slice 2).

> No API keys are required to run. As you obtain them (CQC, Google Places,
> Anthropic, etc.), copy `.env.example` to `.env` in the repo root and fill them
> in — each integration lights up on its own and the UI shows what's configured.

See **[docs/SETUP.md](docs/SETUP.md)** for full setup, every environment
variable, where to get each key, and how to run tests.

---

## Architecture

Monorepo:

```
beacon/
├── backend/      FastAPI + SQLAlchemy + Alembic (Python 3.12)
├── frontend/     React + Vite + TanStack Query + Tailwind (TypeScript)
├── docker-compose.yml
└── docs/         SETUP, DEPLOYMENT, MAINTENANCE
```

- **Backend:** FastAPI, synchronous SQLAlchemy 2.0 on Postgres, Alembic
  migrations, Pydantic v2 throughout. JWT email/password auth.
- **Frontend:** React (Vite), TanStack Query for server state, React Router,
  Tailwind. Dense, keyboard-fast internal power tool.
- **Background work** (slice 2+): `arq` on Redis for long-running sourcing /
  research / audit jobs that report pollable progress.
- **AI** (slice 4+): Anthropic API. Sonnet by default, Opus where ROI is clear,
  Haiku for bulk classification — the model per stage is a config setting.

The pipeline is a cheapest-filters-first funnel: **Source → Qualify → Score →
Enrich + GEO pre-check → Ranked queue**. Expensive AI (stage 4) runs only on the
top-N by cheap score or on demand.

---

## Build status

Built in working slices (see the design doc's Build Order). Current state and
the per-slice checklist live in **[CLAUDE.md](CLAUDE.md)**.

- ✅ **Slice 1** — skeleton, data model, auth, Lane CRUD, empty queue.
- ⏳ Slices 2–7 (the MVP) in progress.

---

## Docs

- **[docs/SETUP.md](docs/SETUP.md)** — local dev, env vars, keys, tests.
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — production deploy (Railway + Vercel).
- **[docs/MAINTENANCE.md](docs/MAINTENANCE.md)** — keeping docs current; how to add a source adapter / lane.
- **[CLAUDE.md](CLAUDE.md)** — conventions & current state for contributors (human or AI).
