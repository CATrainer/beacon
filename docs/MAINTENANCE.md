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
§3). When the adapter framework lands in slice 2, the steps will be:

1. Implement the `SourceAdapter` protocol (`key`, `fetch(lane, limit) -> list[RawCandidate]`)
   in a new file under `backend/app/adapters/`.
2. Register it in the adapter registry.
3. Reference its `key` in a lane's `config.sources` (in the UI or `seeds/lanes.py`).
4. Add any new env key to `config.py`, `.env.example`, SETUP.md, and `/api/status`.
5. Document the adapter in this file's table above.

(This section will be expanded with the concrete API once slice 2 implements it.)

## How to add / tune a lane

Lanes are **data, not code**. Create or edit them in the UI (Lanes → New lane).
The config JSON is validated against `LaneConfig`
(`backend/app/schemas/lane.py`). The two shipped defaults live in
`backend/app/seeds/lanes.py` — edit those only to change what new installs seed.

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
