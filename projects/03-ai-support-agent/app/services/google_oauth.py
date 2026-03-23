from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests

from app.services.mailboxes import DEFAULT_GMAIL_SCOPES

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"


class GoogleOAuthConfigError(RuntimeError):
    pass


class GoogleOAuthStateError(ValueError):
    pass


class GoogleOAuthExchangeError(RuntimeError):
    pass


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]


def _parse_scopes(raw_scopes: str | None) -> list[str]:
    if not raw_scopes:
        return DEFAULT_GMAIL_SCOPES.copy()

    cleaned = raw_scopes.replace(",", " ")
    scopes = [part.strip() for part in cleaned.split(" ") if part.strip()]
    return scopes or DEFAULT_GMAIL_SCOPES.copy()


def get_google_oauth_config() -> GoogleOAuthConfig:
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("GOOGLE_REDIRECT_URI") or "").strip()
    scopes = _parse_scopes(os.getenv("GOOGLE_OAUTH_SCOPES"))

    missing = []
    if not client_id:
        missing.append("GOOGLE_CLIENT_ID")
    if not client_secret:
        missing.append("GOOGLE_CLIENT_SECRET")
    if not redirect_uri:
        missing.append("GOOGLE_REDIRECT_URI")

    if missing:
        raise GoogleOAuthConfigError(f"Missing required Google OAuth env var(s): {', '.join(missing)}")

    return GoogleOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )


def _to_base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _from_base64url(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def create_oauth_state(payload: dict[str, str], secret: str) -> str:
    state_payload = {
        **payload,
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
    }
    body = json.dumps(state_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded_body = _to_base64url(body)
    signature = hmac.new(secret.encode("utf-8"), encoded_body.encode("utf-8"), hashlib.sha256).digest()
    encoded_sig = _to_base64url(signature)
    return f"{encoded_body}.{encoded_sig}"


def parse_oauth_state(state: str, secret: str, *, max_age_seconds: int = 900) -> dict[str, str]:
    if not state or "." not in state:
        raise GoogleOAuthStateError("Invalid state format")

    encoded_body, encoded_sig = state.split(".", 1)
    expected_sig = _to_base64url(
        hmac.new(secret.encode("utf-8"), encoded_body.encode("utf-8"), hashlib.sha256).digest()
    )

    if not hmac.compare_digest(encoded_sig, expected_sig):
        raise GoogleOAuthStateError("State signature mismatch")

    try:
        payload = json.loads(_from_base64url(encoded_body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise GoogleOAuthStateError("State payload is not valid JSON") from exc

    issued_at = payload.get("iat")
    if not isinstance(issued_at, int):
        raise GoogleOAuthStateError("State is missing iat")

    age = int(time.time()) - issued_at
    if age < 0 or age > max_age_seconds:
        raise GoogleOAuthStateError("State expired")

    return payload


def build_google_auth_url(config: GoogleOAuthConfig, state: str) -> str:
    query = urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{GOOGLE_AUTH_URL}?{query}"


def exchange_google_code(config: GoogleOAuthConfig, code: str) -> dict:
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": config.redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )

    if not response.ok:
        body_preview = (response.text or "")[:300]
        raise GoogleOAuthExchangeError(
            f"Google token exchange failed (status={response.status_code}). response={body_preview!r}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleOAuthExchangeError("Google token exchange returned non-JSON response") from exc

    access_token = (payload.get("access_token") or "").strip()
    if not access_token:
        raise GoogleOAuthExchangeError("Google token exchange did not return access_token")

    return payload


def fetch_gmail_mailbox_email(access_token: str) -> str:
    response = requests.get(
        GOOGLE_GMAIL_PROFILE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )

    if not response.ok:
        body_preview = (response.text or "")[:300]
        raise GoogleOAuthExchangeError(
            f"Failed to fetch Gmail profile (status={response.status_code}). response={body_preview!r}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise GoogleOAuthExchangeError("Gmail profile response was not valid JSON") from exc

    mailbox_email = (payload.get("emailAddress") or "").strip().lower()
    if not mailbox_email:
        raise GoogleOAuthExchangeError("Gmail profile response did not include emailAddress")

    return mailbox_email


def derive_token_expiry_iso(expires_in: object) -> str | None:
    if expires_in is None:
        return None

    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None

    if seconds <= 0:
        return None

    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
