"""Create or update a user (no public signup — §1).

Usage:
    python -m app.scripts.seed_user \
        --email you@heuricity.com --name "Your Name" [--password ...]

If --password is omitted you'll be prompted (input hidden). Re-running with an
existing email updates that user's name/password.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db import SessionLocal
from app.models.user import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update a Beacon user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if not password or len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1

    email = args.email.lower().strip()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=args.name, password_hash=hash_password(password))
            db.add(user)
            action = "Created"
        else:
            user.name = args.name
            user.password_hash = hash_password(password)
            user.is_active = True
            action = "Updated"
        db.commit()
        print(f"{action} user {email} (id={user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
