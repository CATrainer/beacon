"""Sender abstraction (§7). Gmail-draft mode is the launch default & safest.

The provider is swappable (Gmail now; an ESP/Smartlead later) and degrades: when
Gmail isn't connected the LogSender simulates draft creation so the pipeline is
demoable end-to-end. Google libraries are imported lazily so the app runs without
them installed.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from email.mime.text import MIMEText

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.integration import OAuthCredential

log = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


@dataclass
class DraftResult:
    draft_id: str
    thread_id: str | None
    simulated: bool = False


def _build_raw(to: str, subject: str, body: str, from_addr: str) -> str:
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["From"] = from_addr
    msg["Subject"] = subject or ""
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


class Sender:
    simulated = False

    def create_draft(self, to: str, subject: str, body: str, from_addr: str) -> DraftResult:
        raise NotImplementedError


class LogSender(Sender):
    """Fallback when Gmail isn't connected — simulates a draft so flows work."""

    simulated = True

    def create_draft(self, to: str, subject: str, body: str, from_addr: str) -> DraftResult:
        log.info("[LogSender] would create Gmail draft to=%s subject=%r", to, subject)
        import uuid

        return DraftResult(draft_id=f"sim_{uuid.uuid4().hex[:12]}", thread_id=None, simulated=True)


class GmailSender(Sender):
    """Creates real Gmail drafts via the Gmail API (OAuth on the sending account)."""

    simulated = False

    def __init__(self, token_json: dict) -> None:
        self._token_json = token_json

    def _service(self):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_info(self._token_json, GMAIL_SCOPES)
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def create_draft(self, to: str, subject: str, body: str, from_addr: str) -> DraftResult:
        service = self._service()
        raw = _build_raw(to, subject, body, from_addr)
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        message = draft.get("message", {})
        return DraftResult(
            draft_id=draft.get("id", ""), thread_id=message.get("threadId"), simulated=False
        )


def get_sender(db: Session) -> Sender:
    """Real GmailSender when connected + configured; otherwise LogSender."""
    if settings.gmail_enabled:
        cred = db.scalar(select(OAuthCredential).where(OAuthCredential.provider == "gmail"))
        if cred and cred.token_json:
            return GmailSender(cred.token_json)
    return LogSender()


# --------------------------------------------------------------------------- #
# Gmail OAuth flow (lazy google imports)
# --------------------------------------------------------------------------- #
def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.gmail_redirect_uri],
        }
    }


def gmail_auth_url() -> str:
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(), scopes=GMAIL_SCOPES, redirect_uri=settings.gmail_redirect_uri
    )
    url, _state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    return url


def gmail_exchange(code: str) -> tuple[str | None, dict]:
    """Exchange an auth code for tokens; returns (account_email, token_json)."""
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build

    flow = Flow.from_client_config(
        _client_config(), scopes=GMAIL_SCOPES, redirect_uri=settings.gmail_redirect_uri
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_json = json.loads(creds.to_json())
    account_email = None
    try:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        account_email = service.users().getProfile(userId="me").execute().get("emailAddress")
    except Exception as exc:  # noqa: BLE001
        log.info("could not fetch Gmail profile email: %s", exc)
    return account_email, token_json
