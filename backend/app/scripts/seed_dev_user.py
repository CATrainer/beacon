"""Idempotently seed a local-dev login from env (DEV_AUTOSEED_EMAIL/PASSWORD).

Runs from the entrypoint only when APP_ENV=local, so you can sign in to the local
stack without running anything. Never overwrites an existing user's password, and
never runs in production.

Usage (normally automatic):
    python -m app.scripts.seed_dev_user
"""

from __future__ import annotations

from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.db import SessionLocal
from app.models.user import User


def main() -> int:
    if settings.app_env.lower() != "local":
        print("[dev-autoseed] not local; skipping.")
        return 0

    email = settings.dev_autoseed_email.lower().strip()
    password = settings.dev_autoseed_password
    if not email or not password:
        print("[dev-autoseed] DEV_AUTOSEED_EMAIL/PASSWORD not set; skipping.")
        return 0

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            print(f"[dev-autoseed] user {email} already exists; leaving as-is.")
            return 0
        db.add(
            User(
                email=email,
                name=settings.dev_autoseed_name,
                password_hash=hash_password(password),
            )
        )
        db.commit()
        print(f"[dev-autoseed] created local login {email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
