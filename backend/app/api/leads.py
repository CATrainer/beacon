"""Lead queue listing. Sorted by final score desc; filterable (§5).

Slice 1 ships the read path so the operator sees an (empty) ranked queue.
Sourcing that fills it lands in Slice 2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.enums import LeadStage, LeadStatus
from app.models.lead import Lead
from app.schemas.lead import LeadListItem, LeadListResponse

router = APIRouter(prefix="/leads", tags=["leads"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=LeadListResponse)
def list_leads(
    db: Session = Depends(get_db),
    lane_id: int | None = None,
    stage: LeadStage | None = None,
    status: LeadStatus | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    q: str | None = Query(default=None, description="Search company / domain"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> LeadListResponse:
    conditions = []
    if lane_id is not None:
        conditions.append(Lead.lane_id == lane_id)
    if stage is not None:
        conditions.append(Lead.stage == stage)
    if status is not None:
        conditions.append(Lead.status == status)
    if min_score is not None:
        conditions.append(Lead.final_score >= min_score)
    if q:
        like = f"%{q.strip()}%"
        conditions.append((Lead.company.ilike(like)) | (Lead.domain.ilike(like)))

    total = db.scalar(select(func.count(Lead.id)).where(*conditions)) or 0
    rows = db.scalars(
        select(Lead)
        .where(*conditions)
        .order_by(Lead.final_score.desc().nullslast(), Lead.updated_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return LeadListResponse(
        items=[LeadListItem.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
