# Maintenance notes (keep the docs alive)

These are the standing instructions for keeping Beacon's documentation accurate
for the lifetime of the project. **Read this before finishing any slice or
non-trivial change.**

## The doc-update checklist (run at the end of every change)

When you finish a slice or any change that alters behaviour, surface area, setup,
or deploy steps, update **all** of the following that are affected — in the same
change, not "later":

- [ ] **[CLAUDE.md](../CLAUDE.md)** — "Current State", "Project Structure" (if
      files/dirs were added), any new conventions, and the per-slice checklist.
- [ ] **[README.md](../README.md)** — quick start, build status, architecture if
      it shifted.
- [ ] **[docs/SETUP.md](SETUP.md)** — any new environment variable (add it to the
      key table with *what it unlocks* and *where to get it*), new commands, new
      services.
- [ ] **[docs/DEPLOYMENT.md](DEPLOYMENT.md)** — any new service (e.g. the worker),
      new env var that must be set in prod, new migration/runtime concern.
- [ ] **`.env.example`** — every new key, with an inline comment on what it does
      and that it's optional.
- [ ] **`/api/status`** (`backend/app/api/system.py`) — if you added an
      integration, report its configured/enabled state so the UI can show it.

A change that adds an env var but not its row in SETUP.md, its line in
`.env.example`, and (if relevant) its flag in `/api/status` is **incomplete**.

## Where things live

| Concern | Location |
| --- | --- |
| Config / settings (all env vars) | `backend/app/config.py` |
| Data model | `backend/app/models/` |
| Pydantic schemas (incl. `LaneConfig`) | `backend/app/schemas/` |
| API routes | `backend/app/api/` |
| Auth | `backend/app/core/` |
| Source adapters (slice 2+) | `backend/app/adapters/` |
| Default lane configs | `backend/app/seeds/lanes.py` |
| Admin scripts (seed user/lanes) | `backend/app/scripts/` |
| Migrations | `backend/alembic/versions/` |
| Frontend pages | `frontend/src/pages/` |
| API types (mirror backend schemas) | `frontend/src/types.ts` |

## How to add a source adapter (slice 2+ pattern)

A new source must be **a new class + a registry entry, nothing else** (design doc
§3). Concrete steps (framework lives in `backend/app/adapters/base.py`):

1. Create `backend/app/adapters/<key>.py`. Subclass `SourceAdapter`, set `key`,
   `description`, and `fixture_file`; implement `available(self, source_params)`
   and `_fetch_live(self, source_params, limit, lane_config) -> list[RawCandidate]`.
   Do **not** override `fetch()` — the base handles the fixture fallback.
2. Decorate the class with `@register`.
3. Import the module in `app/adapters/__init__.py` (side-effect registration).
4. Add a `fixtures/<fixture_file>` so the source runs keyless; tag nothing — the
   base adds `raw_meta.fixture=true` automatically.
5. Reference its `key` in a lane's `config.sources` (UI or `seeds/lanes.py`).
6. Add any new env key to `config.py` (+ an `*_enabled` helper), `.env.example`,
   SETUP.md's key table, and `/api/status`.
7. Add a row to the adapters table above and a unit test.

Enrichment sources (e.g. Companies House) are NOT discovery adapters — they live
in `app/services/` and are called from `app/services/sourcing.py`.

## How to add / tune a lane

Lanes are **data, not code**. Create or edit them in the UI (Lanes → New lane).
The config JSON is validated against `LaneConfig`
(`backend/app/schemas/lane.py`). The two shipped defaults live in
`backend/app/seeds/lanes.py` — edit those only to change what new installs seed.
After changing a lane's `scoring.signals` weights, hit **Re-score** on the lane
card (or `POST /lanes/{id}/rescore`) to recompute existing leads.

## How to add a scoring signal (slice 3)

1. Add a strength function `_s_<name>(ctx) -> float` (0.0–1.0) in
   `backend/app/services/scoring.py` and register it in `STRENGTH_FUNCS`.
2. If it needs new evidence, extend `ScoreContext` / `build_context` (e.g. a new
   keyword lexicon, or a field pulled from `source_hit.raw_meta`).
3. Reference the signal name with a weight in a lane's `scoring.signals`.
   Unknown signal names score 0 and are ignored, so this is safe to roll out.

## Migrations

After any change to `backend/app/models/`, generate and commit a migration:

```bash
docker compose exec backend alembic revision --autogenerate -m "what changed"
```

Review the generated file (autogenerate misses some things — server defaults,
CHECK constraints from `native_enum=False` enums, JSON type changes) before
committing. Never edit a migration that has already run in production; add a new
one.

## Keeping frontend types in sync

`frontend/src/types.ts` mirrors the backend Pydantic schemas by hand. When you
change a schema that crosses the wire, update the matching TS type in the same
change.
