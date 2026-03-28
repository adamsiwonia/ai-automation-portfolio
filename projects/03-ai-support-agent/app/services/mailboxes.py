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


@dataclass(frozen=True)
class GmailMailboxRecord:
    id: int
    client_name: str
    mailbox_email: str
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


def list_gmail_mailboxes(limit: int = 200) -> list[GmailMailboxRecord]:
    if limit < 1:
        raise ValueError("limit must be >= 1")

    query = """
    SELECT
      id,
      client_name,
      mailbox_email,
      processed_label,
      skipped_label,
      active,
      created_at,
      updated_at
    FROM gmail_mailboxes
    ORDER BY updated_at DESC, id DESC
    LIMIT ?
    """

    try:
        with get_conn() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Could not list gmail_mailboxes from DB: %r", exc)
        return []

    items: list[GmailMailboxRecord] = []
    for row in rows:
        items.append(
            GmailMailboxRecord(
                id=int(row["id"]),
                client_name=(row["client_name"] or "").strip(),
                mailbox_email=(row["mailbox_email"] or "").strip().lower(),
                processed_label=(row["processed_label"] or DEFAULT_PROCESSED_LABEL).strip(),
                skipped_label=(row["skipped_label"] or DEFAULT_SKIPPED_LABEL).strip(),
                active=bool(row["active"]),
                created_at=(row["created_at"] or ""),
                updated_at=(row["updated_at"] or ""),
            )
        )

    return items


def fetch_gmail_mailbox_counts() -> dict[str, int]:
    query = """
    SELECT
      COUNT(*) AS total_count,
      SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS active_count
    FROM gmail_mailboxes
    """

    try:
        with get_conn() as conn:
            row = conn.execute(query).fetchone()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Could not fetch gmail_mailbox counts from DB: %r", exc)
        return {"total": 0, "active": 0, "inactive": 0}

    total = int((row["total_count"] or 0) if row else 0)
    active = int((row["active_count"] or 0) if row else 0)
    inactive = max(0, total - active)
    return {"total": total, "active": active, "inactive": inactive}


def set_gmail_mailbox_active(*, mailbox_id: int, active: bool) -> bool:
    if mailbox_id <= 0:
        raise ValueError("mailbox_id must be positive")

    query = """
    UPDATE gmail_mailboxes
    SET active = ?, updated_at = ?
    WHERE id = ?
    """

    with get_conn() as conn:
        cursor = conn.execute(
            query,
            (
                1 if active else 0,
                _now_utc_iso(),
                mailbox_id,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_mailbox_tokens(
    *,
    mailbox_id: int,
    access_token: str | None,
    refresh_token: str | None,
    token_expiry: str | None,
) -> None:
    normalized_refresh_token = (refresh_token or "").strip() or None

    query = """
    UPDATE gmail_mailboxes
    SET access_token = ?, refresh_token = COALESCE(?, refresh_token), token_expiry = ?, updated_at = ?
    WHERE id = ?
    """

    try:
        with get_conn() as conn:
            conn.execute(
                query,
                (
                    access_token,
                    normalized_refresh_token,
                    token_expiry,
                    _now_utc_iso(),
                    mailbox_id,
                ),
            )
            conn.commit()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Failed to update mailbox token state for mailbox_id=%s: %r", mailbox_id, exc)


def _normalize_scopes_for_storage(scopes: list[str] | str | None) -> str:
    if scopes is None:
        cleaned = DEFAULT_GMAIL_SCOPES.copy()
    elif isinstance(scopes, str):
        cleaned = _parse_scopes(scopes)
    else:
        cleaned = [str(item).strip() for item in scopes if str(item).strip()]
        if not cleaned:
            cleaned = DEFAULT_GMAIL_SCOPES.copy()

    return json.dumps(cleaned, ensure_ascii=True)


def upsert_gmail_mailbox_oauth(
    *,
    client_name: str,
    mailbox_email: str,
    access_token: str,
    refresh_token: str | None,
    token_expiry: str | None,
    scopes: list[str] | str | None,
    processed_label: str | None,
    skipped_label: str | None,
    active: bool = True,
) -> dict[str, object]:
    normalized_email = (mailbox_email or "").strip().lower()
    if not normalized_email:
        raise ValueError("mailbox_email is required")

    normalized_client_name = (client_name or normalized_email).strip() or normalized_email
    normalized_access_token = (access_token or "").strip()
    if not normalized_access_token:
        raise ValueError("access_token is required")

    normalized_refresh_token = (refresh_token or "").strip() or None
    normalized_processed_label = (processed_label or DEFAULT_PROCESSED_LABEL).strip() or DEFAULT_PROCESSED_LABEL
    normalized_skipped_label = (skipped_label or DEFAULT_SKIPPED_LABEL).strip() or DEFAULT_SKIPPED_LABEL
    scopes_json = _normalize_scopes_for_storage(scopes)
    now = _now_utc_iso()

    insert_query = """
    INSERT INTO gmail_mailboxes
    (
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
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(mailbox_email) DO UPDATE SET
      client_name = excluded.client_name,
      access_token = excluded.access_token,
      refresh_token = COALESCE(excluded.refresh_token, gmail_mailboxes.refresh_token),
      token_expiry = excluded.token_expiry,
      scopes = excluded.scopes,
      processed_label = excluded.processed_label,
      skipped_label = excluded.skipped_label,
      active = excluded.active,
      updated_at = excluded.updated_at
    """

    try:
        with get_conn() as conn:
            existing_row = conn.execute(
                "SELECT id FROM gmail_mailboxes WHERE mailbox_email = ?",
                (normalized_email,),
            ).fetchone()
            created = existing_row is None

            conn.execute(
                insert_query,
                (
                    normalized_client_name,
                    normalized_email,
                    normalized_access_token,
                    normalized_refresh_token,
                    token_expiry,
                    scopes_json,
                    normalized_processed_label,
                    normalized_skipped_label,
                    1 if active else 0,
                    now,
                    now,
                ),
            )

            row = conn.execute(
                "SELECT id, mailbox_email, active FROM gmail_mailboxes WHERE mailbox_email = ?",
                (normalized_email,),
            ).fetchone()
            conn.commit()

            if not row:
                raise RuntimeError("Mailbox upsert succeeded but row could not be reloaded")

            return {
                "id": int(row["id"]),
                "mailbox_email": (row["mailbox_email"] or "").strip().lower(),
                "active": bool(row["active"]),
                "created": created,
            }

    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.exception("Failed to upsert gmail mailbox | mailbox_email=%s | error=%r", normalized_email, exc)
        raise
