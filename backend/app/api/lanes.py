"""Lane CRUD. Creating/editing a lane must not need a code change (§3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.lane import Lane
from app.models.lead import Lead
from app.schemas.lane import LaneCreate, LaneOut, LaneUpdate

router = APIRouter(prefix="/lanes", tags=["lanes"], dependencies=[Depends(get_current_user)])


def _to_out(lane: Lane, lead_count: int = 0) -> LaneOut:
    return LaneOut(
        id=lane.id,
        name=lane.name,
        description=lane.description,
        is_active=lane.is_active,
        config=lane.config or {},
        lead_count=lead_count,
    )


@router.get("", response_model=list[LaneOut])
def list_lanes(db: Session = Depends(get_db)) -> list[LaneOut]:
    counts = dict(
        db.execute(select(Lead.lane_id, func.count(Lead.id)).group_by(Lead.lane_id)).all()
    )
    lanes = db.scalars(select(Lane).order_by(Lane.name)).all()
    return [_to_out(lane, counts.get(lane.id, 0)) for lane in lanes]


@router.post("", response_model=LaneOut, status_code=status.HTTP_201_CREATED)
def create_lane(payload: LaneCreate, db: Session = Depends(get_db)) -> LaneOut:
    if db.scalar(select(Lane).where(Lane.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A lane with that name already exists")
    lane = Lane(
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        config=payload.config.model_dump(),
    )
    db.add(lane)
    db.commit()
    db.refresh(lane)
    return _to_out(lane)


@router.get("/{lane_id}", response_model=LaneOut)
def get_lane(lane_id: int, db: Session = Depends(get_db)) -> LaneOut:
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")
    count = db.scalar(select(func.count(Lead.id)).where(Lead.lane_id == lane_id)) or 0
    return _to_out(lane, count)


@router.patch("/{lane_id}", response_model=LaneOut)
def update_lane(lane_id: int, payload: LaneUpdate, db: Session = Depends(get_db)) -> LaneOut:
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")

    if payload.name is not None and payload.name != lane.name:
        if db.scalar(select(Lane).where(Lane.name == payload.name, Lane.id != lane_id)):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="A lane with that name exists")
        lane.name = payload.name
    if payload.description is not None:
        lane.description = payload.description
    if payload.is_active is not None:
        lane.is_active = payload.is_active
    if payload.config is not None:
        lane.config = payload.config.model_dump()

    db.commit()
    db.refresh(lane)
    count = db.scalar(select(func.count(Lead.id)).where(Lead.lane_id == lane_id)) or 0
    return _to_out(lane, count)


@router.delete("/{lane_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lane(lane_id: int, db: Session = Depends(get_db)) -> Response:
    lane = db.get(Lane, lane_id)
    if lane is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lane not found")
    lead_count = db.scalar(select(func.count(Lead.id)).where(Lead.lane_id == lane_id)) or 0
    if lead_count > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Lane has {lead_count} leads; deactivate it instead of deleting.",
        )
    db.delete(lane)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
