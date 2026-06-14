# Production deployment

Target topology (per the design doc): **backend + Postgres + Redis on Railway**,
**frontend on Vercel**. Keep this document in lockstep with the deploy as it
evolves — see [MAINTENANCE.md](MAINTENANCE.md).

> Status: deployment is documented but not yet provisioned. The app currently
> runs locally via Docker. When we provision, update the "Current state" note
> here and in [CLAUDE.md](../CLAUDE.md).

## Backend + datastores — Railway

1. **Create a Railway project.** Add two plugins: **PostgreSQL** and **Redis**.
   Railway provides `DATABASE_URL` and `REDIS_URL` reference variables.
2. **Add a service from the repo**, root directory `backend/` (Railway detects
   the `Dockerfile`). The image's `entrypoint.sh` runs `alembic upgrade head`
   then starts uvicorn, so migrations apply automatically on each deploy.
   - Railway sets `DATABASE_URL` as `postgresql://…`. SQLAlchemy + psycopg3 needs
     the `+psycopg` driver suffix. Either set
     `DATABASE_URL=postgresql+psycopg://…` explicitly (recommended) or add a small
     normaliser. **Action item when provisioning:** confirm the URL scheme.
3. **Set environment variables** (Railway → Variables). Required:
   - `SECRET_KEY` — a real secret (`secrets.token_urlsafe(48)`).
   - `APP_ENV=production`
   - `CORS_ORIGINS=https://<your-vercel-domain>`
   - Plus any integration keys you want live (see SETUP.md table).
4. **Worker (required from slice 2).** Add a second Railway service from the same
   `backend/` image, overriding the start command to
   `arq app.worker.WorkerSettings` (the image entrypoint passes the command
   through after waiting for the DB). It needs the same `DATABASE_URL` /
   `REDIS_URL` / API-key env as the backend. Without it, sourcing/research/audit
   jobs won't process (the API falls back to inline execution only if Redis is
   unreachable).
5. **Seed the first user** via Railway's one-off command / shell:
   `python -m app.scripts.seed_user --email … --name … --password …`

## Frontend — Vercel

1. **Import the repo**, set the project root to `frontend/`.
2. Build command `npm run build`, output directory `dist` (Vite defaults).
3. **Environment variable:** `VITE_API_URL=https://<railway-backend-domain>`.
4. Add the Vercel domain to the backend's `CORS_ORIGINS`.
5. SPA routing: Vercel serves `index.html` for unknown routes by default for
   Vite SPAs; if deep links 404, add a rewrite of `/(.*)` → `/index.html`.

## Post-deploy smoke test

1. `GET https://<backend>/api/health` → `{"status":"ok"}`.
2. `GET https://<backend>/api/status` → integrations reflect the keys you set.
3. Load the Vercel URL, sign in with the seeded user, view the queue and lanes.

## Secrets

All secrets via platform environment variables only — never committed. Rotate
`SECRET_KEY` and any leaked API key immediately; rotating `SECRET_KEY`
invalidates existing sessions (fine — re-login).
