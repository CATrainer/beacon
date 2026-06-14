"""Gmail OAuth connect flow + status (§7). Drafts are created on this account."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user
from app.db import get_db
from app.models.integration import OAuthCredential
from app.schemas.crm import GmailStatus
from app.services import sender

log = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/gmail", tags=["integrations"])


@router.get("/status", response_model=GmailStatus, dependencies=[Depends(get_current_user)])
def gmail_status(db: Session = Depends(get_db)) -> GmailStatus:
    cred = db.scalar(select(OAuthCredential).where(OAuthCredential.provider == "gmail"))
    return GmailStatus(
        connected=cred is not None,
        configured=settings.gmail_enabled,
        account_email=cred.account_email if cred else None,
    )


@router.get("/connect", dependencies=[Depends(get_current_user)])
def gmail_connect() -> dict:
    if not settings.gmail_enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Gmail OAuth not configured (set GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET)",
        )
    return {"auth_url": sender.gmail_auth_url()}


@router.get("/callback")
def gmail_callback(code: str | None = None, error: str | None = None,
                   db: Session = Depends(get_db)) -> RedirectResponse:
    """Google redirects here (no bearer). Exchange the code and store the tokens."""
    if error or not code:
        return RedirectResponse(f"{settings.frontend_url}/settings?gmail=error")
    try:
        account_email, token_json = sender.gmail_exchange(code)
    except Exception as exc:  # noqa: BLE001
        log.exception("gmail token exchange failed")
        return RedirectResponse(f"{settings.frontend_url}/settings?gmail=error&msg={exc}")

    cred = db.scalar(select(OAuthCredential).where(OAuthCredential.provider == "gmail"))
    if cred is None:
        cred = OAuthCredential(provider="gmail")
        db.add(cred)
    cred.account_email = account_email
    cred.token_json = token_json
    db.commit()
    return RedirectResponse(f"{settings.frontend_url}/settings?gmail=connected")


@router.post("/disconnect", dependencies=[Depends(get_current_user)], status_code=204)
def gmail_disconnect(db: Session = Depends(get_db)):
    cred = db.scalar(select(OAuthCredential).where(OAuthCredential.provider == "gmail"))
    if cred is not None:
        db.delete(cred)
        db.commit()
    from fastapi import Response

    return Response(status_code=204)
