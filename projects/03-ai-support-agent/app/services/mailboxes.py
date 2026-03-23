from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from app.database.db import get_conn

DEFAULT_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

DEFAULT_PROCESSED_LABEL = "AI_PROCESSED"
DEFAULT_SKIPPED_LABEL = "AI_SKIPPED"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GmailMailbox:
    id: int
    client_name: str
    mailbox_email: str
    access_token: str
    refresh_token: str
    token_expiry: str | None
    scopes: list[str]
    processed_label: str
    skipped_label: str
    active: bool
    created_at: str
    updated_at: str


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_scopes(raw_scopes: str | None) -> list[str]:
    if not raw_scopes:
        return DEFAULT_GMAIL_SCOPES.copy()

    raw = raw_scopes.strip()
    if not raw:
        return DEFAULT_GMAIL_SCOPES.copy()

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                cleaned = [str(item).strip() for item in parsed if str(item).strip()]
                if cleaned:
                    return cleaned
        except json.JSONDecodeError:
            logger.warning("Invalid mailbox scopes JSON, falling back to tokenized parsing: %r", raw_scopes)

    if " " in raw:
        scopes = [part.strip() for part in raw.split(" ") if part.strip()]
        if scopes:
            return scopes

    if "," in raw:
        scopes = [part.strip() for part in raw.split(",") if part.strip()]
        if scopes:
            return scopes

    return [raw]


def load_active_gmail_mailboxes() -> list[GmailMailbox]:
    query = """
    SELECT
      id,
      client_name,
      mailbox_email,
      access_token,
      refresh_token,
      token_expiry,
      scopes,
      processed_label,
      skipped_label,
      active,
      created_at,
      updated_at
    FROM gmail_mailboxes
    WHERE active = 1
    ORDER BY id ASC
    """

    try:
        with get_conn() as conn:
            rows = conn.execute(query).fetchall()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        # Schema may not be initialized yet for standalone worker runs.
        logger.warning("Could not load gmail_mailboxes from DB: %r", exc)
        return []

    mailboxes: list[GmailMailbox] = []
    for row in rows:
        mailboxes.append(
            GmailMailbox(
                id=int(row["id"]),
                client_name=(row["client_name"] or "").strip(),
                mailbox_email=(row["mailbox_email"] or "").strip().lower(),
                access_token=(row["access_token"] or "").strip(),
                refresh_token=(row["refresh_token"] or "").strip(),
                token_expiry=(row["token_expiry"] or None),
                scopes=_parse_scopes(row["scopes"]),
                processed_label=(row["processed_label"] or DEFAULT_PROCESSED_LABEL).strip(),
                skipped_label=(row["skipped_label"] or DEFAULT_SKIPPED_LABEL).strip(),
                active=bool(row["active"]),
                created_at=(row["created_at"] or ""),
                updated_at=(row["updated_at"] or ""),
            )
        )

    return mailboxes


def update_mailbox_tokens(
    *,
    mailbox_id: int,
    access_token: str | None,
    refresh_token: str | None,
    token_expiry: str | None,
) -> None:
    query = """
    UPDATE gmail_mailboxes
    SET access_token = ?, refresh_token = ?, token_expiry = ?, updated_at = ?
    WHERE id = ?
    """

    try:
        with get_conn() as conn:
            conn.execute(
                query,
                (
                    access_token,
                    refresh_token,
                    token_expiry,
                    _now_utc_iso(),
                    mailbox_id,
                ),
            )
            conn.commit()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Failed to update mailbox token state for mailbox_id=%s: %r", mailbox_id, exc)
