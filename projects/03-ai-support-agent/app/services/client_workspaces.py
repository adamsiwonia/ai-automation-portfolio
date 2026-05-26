from __future__ import annotations

import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from app.database.db import get_conn

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClientWorkspaceRecord:
    id: int
    name: str
    contact_email: str | None
    onboarding_token: str
    active: bool
    created_at: str
    updated_at: str
    mailbox_count: int
    active_mailbox_count: int


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_name(name: str | None) -> str:
    normalized = (name or "").strip()
    if not normalized:
        raise ValueError("Workspace name is required")
    return normalized


def _normalize_contact_email(contact_email: str | None) -> str | None:
    normalized = (contact_email or "").strip().lower()
    return normalized or None


def _generate_onboarding_token() -> str:
    return secrets.token_urlsafe(24)


def _create_unique_onboarding_token(conn: sqlite3.Connection) -> str:
    for _ in range(8):
        token = _generate_onboarding_token()
        row = conn.execute(
            "SELECT id FROM client_workspaces WHERE onboarding_token = ?",
            (token,),
        ).fetchone()
        if row is None:
            return token
    raise RuntimeError("Could not generate a unique onboarding token")


def create_client_workspace(*, name: str, contact_email: str | None = None, active: bool = True) -> dict[str, object]:
    normalized_name = _normalize_name(name)
    normalized_contact_email = _normalize_contact_email(contact_email)
    now = _now_utc_iso()

    try:
        with get_conn() as conn:
            onboarding_token = _create_unique_onboarding_token(conn)
            cursor = conn.execute(
                """
                INSERT INTO client_workspaces
                (name, contact_email, onboarding_token, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_name,
                    normalized_contact_email,
                    onboarding_token,
                    1 if active else 0,
                    now,
                    now,
                ),
            )
            workspace_id = int(cursor.lastrowid)

            row = conn.execute(
                """
                SELECT id, name, contact_email, onboarding_token, active, created_at, updated_at
                FROM client_workspaces
                WHERE id = ?
                """,
                (workspace_id,),
            ).fetchone()
            conn.commit()

            if not row:
                raise RuntimeError("Workspace was created but could not be reloaded")

            return {
                "id": int(row["id"]),
                "name": (row["name"] or "").strip(),
                "contact_email": (row["contact_email"] or "").strip() or None,
                "onboarding_token": (row["onboarding_token"] or "").strip(),
                "active": bool(row["active"]),
                "created_at": (row["created_at"] or "").strip(),
                "updated_at": (row["updated_at"] or "").strip(),
            }
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.exception("Failed to create client workspace | name=%s | error=%r", normalized_name, exc)
        raise


def list_client_workspaces(limit: int = 200) -> list[ClientWorkspaceRecord]:
    if limit < 1:
        raise ValueError("limit must be >= 1")

    query = """
    SELECT
      w.id,
      w.name,
      w.contact_email,
      w.onboarding_token,
      w.active,
      w.created_at,
      w.updated_at,
      COUNT(m.id) AS mailbox_count,
      SUM(CASE WHEN m.active = 1 THEN 1 ELSE 0 END) AS active_mailbox_count
    FROM client_workspaces w
    LEFT JOIN gmail_mailboxes m ON m.client_workspace_id = w.id
    GROUP BY w.id
    ORDER BY w.created_at DESC, w.id DESC
    LIMIT ?
    """

    try:
        with get_conn() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Could not list client_workspaces from DB: %r", exc)
        return []

    records: list[ClientWorkspaceRecord] = []
    for row in rows:
        records.append(
            ClientWorkspaceRecord(
                id=int(row["id"]),
                name=(row["name"] or "").strip(),
                contact_email=(row["contact_email"] or "").strip() or None,
                onboarding_token=(row["onboarding_token"] or "").strip(),
                active=bool(row["active"]),
                created_at=(row["created_at"] or "").strip(),
                updated_at=(row["updated_at"] or "").strip(),
                mailbox_count=int(row["mailbox_count"] or 0),
                active_mailbox_count=int(row["active_mailbox_count"] or 0),
            )
        )
    return records


def get_client_workspace_by_token(token: str, *, require_active: bool = True) -> dict[str, object] | None:
    normalized_token = (token or "").strip()
    if not normalized_token:
        return None

    query = """
    SELECT id, name, contact_email, onboarding_token, active, created_at, updated_at
    FROM client_workspaces
    WHERE onboarding_token = ?
    """
    params: tuple[object, ...]
    if require_active:
        query += " AND active = 1"
        params = (normalized_token,)
    else:
        params = (normalized_token,)

    try:
        with get_conn() as conn:
            row = conn.execute(query, params).fetchone()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Could not fetch workspace by onboarding token: %r", exc)
        return None

    if not row:
        return None

    return {
        "id": int(row["id"]),
        "name": (row["name"] or "").strip(),
        "contact_email": (row["contact_email"] or "").strip() or None,
        "onboarding_token": (row["onboarding_token"] or "").strip(),
        "active": bool(row["active"]),
        "created_at": (row["created_at"] or "").strip(),
        "updated_at": (row["updated_at"] or "").strip(),
    }


def get_client_workspace_by_id(workspace_id: int) -> dict[str, object] | None:
    if workspace_id <= 0:
        return None

    query = """
    SELECT id, name, contact_email, onboarding_token, active, created_at, updated_at
    FROM client_workspaces
    WHERE id = ?
    """

    try:
        with get_conn() as conn:
            row = conn.execute(query, (workspace_id,)).fetchone()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Could not fetch workspace by id=%s: %r", workspace_id, exc)
        return None

    if not row:
        return None

    return {
        "id": int(row["id"]),
        "name": (row["name"] or "").strip(),
        "contact_email": (row["contact_email"] or "").strip() or None,
        "onboarding_token": (row["onboarding_token"] or "").strip(),
        "active": bool(row["active"]),
        "created_at": (row["created_at"] or "").strip(),
        "updated_at": (row["updated_at"] or "").strip(),
    }
