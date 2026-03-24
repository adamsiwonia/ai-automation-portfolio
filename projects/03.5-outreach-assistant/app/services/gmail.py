from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.core.config import Settings

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


@dataclass(frozen=True)
class GmailDraftPayload:
    to_email: str
    subject: str
    body: str


def get_gmail_service(settings: Settings) -> Any:
    if not settings.gmail_oauth_client_secrets_path:
        raise RuntimeError(
            "Missing GMAIL_OAUTH_CLIENT_SECRETS. Set path to OAuth client JSON."
        )
    if not settings.gmail_oauth_client_secrets_path.exists():
        raise RuntimeError(
            f"GMAIL_OAUTH_CLIENT_SECRETS does not exist: {settings.gmail_oauth_client_secrets_path}"
        )

    creds = _load_or_authenticate(
        client_secrets_path=settings.gmail_oauth_client_secrets_path,
        token_path=settings.gmail_token_path,
    )

    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=creds)


def create_gmail_draft(service: Any, payload: GmailDraftPayload) -> str:
    message = EmailMessage()
    message["To"] = payload.to_email
    message["Subject"] = payload.subject
    message.set_content(payload.body)

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    response = (
        service.users()
        .drafts()
        .create(
            userId="me",
            body={"message": {"raw": raw_message}},
        )
        .execute()
    )
    draft_id = (response or {}).get("id")
    if not draft_id:
        raise RuntimeError("Gmail API did not return a draft id.")
    return str(draft_id)


def _load_or_authenticate(*, client_secrets_path: Path, token_path: Path) -> Credentials:
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(token_path, creds)
        return creds

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_path),
        scopes=GMAIL_SCOPES,
    )
    creds = flow.run_local_server(port=0)
    _save_token(token_path, creds)
    return creds


def _save_token(token_path: Path, creds: Credentials) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_data = creds.to_json()
    parsed = json.loads(token_data)
    token_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")

