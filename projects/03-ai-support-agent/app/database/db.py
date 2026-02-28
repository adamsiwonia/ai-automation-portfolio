from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]  # .../projects/03-ai-support-agent
DB_PATH = PROJECT_DIR / "app" / "database" / "support_agent.sqlite"
SCHEMA_PATH = PROJECT_DIR / "app" / "database" / "schema.sql"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=3, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=3000;")
    return conn


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


def fetch_logs(limit: int = 50, parse_ok: int | None = None, category: str | None = None):
    q = """
    SELECT id, request_id, created_at, source, customer_from, subject,
           category, reply, next_step, parse_ok, error_message
    FROM support_logs
    """
    where = []
    params = []

    if parse_ok is not None:
        where.append("parse_ok = ?")
        params.append(parse_ok)

    if category:
        where.append("category = ?")
        params.append(category)

    if where:
        q += " WHERE " + " AND ".join(where)

    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]