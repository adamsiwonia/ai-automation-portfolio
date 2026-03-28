from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Any

PROJECT_DIR = Path(__file__).resolve().parents[2]  # .../projects/03-ai-support-agent

logger = logging.getLogger(__name__)

DB_PATH = Path(
    os.getenv(
        "DB_PATH",
        PROJECT_DIR / "app" / "database" / "support_agent.sqlite"
    )
)

SCHEMA_PATH = PROJECT_DIR / "app" / "database" / "schema.sql"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=3, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=3000;")
    return conn


# FastAPI dependency used by auth and protected endpoints.
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_conn() as conn:
        conn.executescript(schema)
        conn.commit()


def insert_log(
    *,
    request_id: str,
    created_at: str,
    source: str,
    customer_from: str | None,
    subject: str | None,
    category: str | None,
    reply: str | None,
    next_step: str | None,
    raw_email: str,
    raw_model_output: str | None,
    parse_ok: int,
    error_message: str | None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO support_logs
            (request_id, created_at, source, customer_from, subject, category, reply, next_step,
             raw_email, raw_model_output, parse_ok, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                created_at,
                source,
                customer_from,
                subject,
                category,
                reply,
                next_step,
                raw_email,
                raw_model_output,
                parse_ok,
                error_message,
            ),
        )
        conn.commit()


def fetch_logs(
    limit: int = 50,
    parse_ok: int | None = None,
    category: str | None = None,
    created_after: str | None = None,
) -> list[dict[str, Any]]:
    q = """
    SELECT id, request_id, created_at, source, customer_from, subject,
           category, reply, next_step, parse_ok, error_message
    FROM support_logs
    """
    where = []
    params: list[Any] = []

    if parse_ok is not None:
        where.append("parse_ok = ?")
        params.append(parse_ok)

    if category:
        where.append("category = ?")
        params.append(category)

    if created_after:
        where.append("created_at >= ?")
        params.append(created_after)

    if where:
        q += " WHERE " + " AND ".join(where)

    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def fetch_recent_support_metrics(hours: int = 24) -> dict[str, int]:
    if hours <= 0:
        raise ValueError("hours must be > 0")

    window_start = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    query = """
    SELECT
      COUNT(*) AS total_count,
      SUM(CASE WHEN parse_ok = 0 OR error_message IS NOT NULL THEN 1 ELSE 0 END) AS error_count
    FROM support_logs
    WHERE created_at >= ?
    """

    try:
        with get_conn() as conn:
            row = conn.execute(query, (window_start,)).fetchone()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as exc:
        logger.warning("Could not fetch recent support metrics: %r", exc)
        return {"recent_total": 0, "recent_errors": 0}

    recent_total = int((row["total_count"] or 0) if row else 0)
    recent_errors = int((row["error_count"] or 0) if row else 0)
    return {"recent_total": recent_total, "recent_errors": recent_errors}

