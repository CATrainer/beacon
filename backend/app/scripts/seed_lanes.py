"""Insert the default Clinics & Travel lanes if they don't already exist.

Usage:
    python -m app.scripts.seed_lanes
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models.lane import Lane
from app.seeds.lanes import DEFAULT_LANES


def main() -> int:
    with SessionLocal() as db:
        for spec in DEFAULT_LANES:
            existing = db.scalar(select(Lane).where(Lane.name == spec["name"]))
            if existing:
                print(f"Lane '{spec['name']}' already exists (id={existing.id}); skipping.")
                continue
            lane = Lane(
                name=spec["name"],
                description=spec["description"],
                config=spec["config"],
            )
            db.add(lane)
            db.commit()
            db.refresh(lane)
            print(f"Seeded lane '{lane.name}' (id={lane.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
