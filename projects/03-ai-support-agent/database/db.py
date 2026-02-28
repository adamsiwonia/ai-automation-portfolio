import sqlite3
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "database" / "support_agent.sqlite"
SCHEMA_PATH = PROJECT_DIR / "database" / "schema.sql"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_conn() as conn:
        conn.executescript(schema)


def insert_log(
    *,
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
            (created_at, source, customer_from, subject, category, reply, next_step,
             raw_email, raw_model_output, parse_ok, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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