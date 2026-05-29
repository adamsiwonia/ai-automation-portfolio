from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "local_agent_office.sqlite"

LEAD_STATUSES = {
    "DISCOVERED",
    "QUALIFIED",
    "REVIEW",
    "APPROVED_FOR_OUTREACH",
    "REJECTED",
    "DRAFT_CREATED",
    "DONE",
    # Internal skip/dedupe statuses used by the lead pipeline.
    "SKIPPED",
    "DUPLICATE_LOCAL",
    "DUPLICATE_SHEET",
}


LEAD_FIELDS = [
    "company_name",
    "website_url",
    "normalized_domain",
    "contact_email",
    "niche",
    "score",
    "status",
    "recommended_angle",
    "personal_note",
    "reason",
    "source_query",
    "source",
    "raw_model_output",
    "parsed_json",
    "duplicate_reason",
    "pre_filter_passed",
    "pre_filter_reason",
    "pre_filter_flags",
    "sheet_status",
    "sheet_duplicate_reason",
    "lead_source_mode",
    "snippet",
    "exported_at",
]


LEAD_MIGRATIONS = {
    "pre_filter_passed": "INTEGER",
    "pre_filter_reason": "TEXT",
    "pre_filter_flags": "TEXT",
    "sheet_status": "TEXT",
    "sheet_duplicate_reason": "TEXT",
    "lead_source_mode": "TEXT",
    "snippet": "TEXT",
    "exported_at": "TEXT",
}


LOG_MIGRATIONS = {
    "event": "TEXT",
    "company_name": "TEXT",
    "details": "TEXT",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                website_url TEXT,
                normalized_domain TEXT,
                contact_email TEXT,
                niche TEXT,
                score INTEGER,
                status TEXT NOT NULL DEFAULT 'DISCOVERED',
                recommended_angle TEXT,
                personal_note TEXT,
                reason TEXT,
                source_query TEXT,
                source TEXT,
                raw_model_output TEXT,
                parsed_json TEXT,
                duplicate_reason TEXT,
                pre_filter_passed INTEGER,
                pre_filter_reason TEXT,
                pre_filter_flags TEXT,
                sheet_status TEXT,
                sheet_duplicate_reason TEXT,
                lead_source_mode TEXT,
                snippet TEXT,
                exported_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                task TEXT,
                metadata TEXT,
                event TEXT,
                company_name TEXT,
                details TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_query TEXT,
                limit_requested INTEGER,
                model_name TEXT,
                status TEXT NOT NULL,
                discovered_count INTEGER NOT NULL DEFAULT 0,
                qualified_count INTEGER NOT NULL DEFAULT 0,
                review_count INTEGER NOT NULL DEFAULT 0,
                rejected_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                metadata TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_leads_normalized_domain
                ON leads(normalized_domain);
            CREATE INDEX IF NOT EXISTS idx_leads_contact_email
                ON leads(contact_email);
            CREATE INDEX IF NOT EXISTS idx_leads_status
                ON leads(status);
            CREATE INDEX IF NOT EXISTS idx_logs_created_at
                ON logs(created_at);
            """
        )
        _ensure_columns(conn, "leads", LEAD_MIGRATIONS)
        _ensure_columns(conn, "logs", LOG_MIGRATIONS)


def _ensure_columns(conn: sqlite3.Connection, table: str, migrations: dict[str, str]) -> None:
    existing = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for column, column_type in migrations.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def add_log(
    level: str,
    message: str,
    task: str | None = None,
    metadata: dict[str, Any] | None = None,
    event: str | None = None,
    company_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    init_db()
    detail_payload = details if details is not None else metadata or {}
    payload = json.dumps(metadata or {}, ensure_ascii=True)
    details_json = json.dumps(detail_payload, ensure_ascii=True)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO logs (level, message, task, metadata, event, company_name, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (level.upper(), message, task, payload, event or task or "general", company_name, details_json, utc_now()),
        )


def create_run(source_query: str, limit_requested: int, model_name: str) -> int:
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO runs (source_query, limit_requested, model_name, status, started_at)
            VALUES (?, ?, ?, 'RUNNING', ?)
            """,
            (source_query, limit_requested, model_name, utc_now()),
        )
        return int(cursor.lastrowid)


def finish_run(run_id: int, status: str, counts: dict[str, int], metadata: dict[str, Any] | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE runs
            SET status = ?,
                discovered_count = ?,
                qualified_count = ?,
                review_count = ?,
                rejected_count = ?,
                duplicate_count = ?,
                error_count = ?,
                completed_at = ?,
                metadata = ?
            WHERE id = ?
            """,
            (
                status,
                counts.get("discovered", 0),
                counts.get("qualified", 0),
                counts.get("review", 0),
                counts.get("rejected", 0),
                counts.get("duplicates", 0),
                counts.get("errors", 0),
                utc_now(),
                json.dumps(metadata or {}, ensure_ascii=True),
                run_id,
            ),
        )


def insert_lead(lead: dict[str, Any]) -> int:
    from services.deduplication import normalize_domain, normalize_email

    init_db()
    now = utc_now()
    clean = {field: lead.get(field) for field in LEAD_FIELDS}
    clean["company_name"] = clean["company_name"] or "Unknown Company"
    clean["normalized_domain"] = clean["normalized_domain"] or normalize_domain(clean.get("website_url"))
    clean["contact_email"] = normalize_email(clean.get("contact_email"))
    clean["status"] = clean["status"] or "DISCOVERED"
    if clean["status"] not in LEAD_STATUSES:
        clean["status"] = "REVIEW"
    if isinstance(clean.get("pre_filter_flags"), list):
        clean["pre_filter_flags"] = json.dumps(clean["pre_filter_flags"], ensure_ascii=True)
    if isinstance(clean.get("pre_filter_passed"), bool):
        clean["pre_filter_passed"] = 1 if clean["pre_filter_passed"] else 0

    values = [clean[field] for field in LEAD_FIELDS] + [now, now]
    placeholders = ", ".join(["?"] * (len(LEAD_FIELDS) + 2))
    columns = ", ".join(LEAD_FIELDS + ["created_at", "updated_at"])
    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO leads ({columns}) VALUES ({placeholders})",
            values,
        )
        return int(cursor.lastrowid)


def get_lead(lead_id: int) -> dict[str, Any] | None:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(row) if row else None


def update_lead_sheet_status(
    lead_id: int,
    sheet_status: str,
    sheet_duplicate_reason: str | None = None,
) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE leads
            SET sheet_status = ?,
                sheet_duplicate_reason = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (sheet_status, sheet_duplicate_reason, utc_now(), lead_id),
        )


def update_lead_status(lead_id: int, status: str, reason: str | None = None) -> bool:
    init_db()
    normalized_status = status.strip().upper()
    if normalized_status not in LEAD_STATUSES:
        raise ValueError(f"Unsupported lead status: {status}")

    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not existing:
            return False

        if reason:
            conn.execute(
                """
                UPDATE leads
                SET status = ?,
                    reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (normalized_status, reason, utc_now(), lead_id),
            )
        else:
            conn.execute(
                """
                UPDATE leads
                SET status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (normalized_status, utc_now(), lead_id),
            )
    return True


def find_duplicate_lead(lead: dict[str, Any]) -> str | None:
    from services.deduplication import normalize_domain, normalize_email, normalize_website_url

    init_db()
    domain = normalize_domain(lead.get("normalized_domain") or lead.get("website_url"))
    email = normalize_email(lead.get("contact_email"))
    website = normalize_website_url(lead.get("website_url"))

    with get_connection() as conn:
        if domain:
            row = conn.execute(
                """
                SELECT id, company_name
                FROM leads
                WHERE normalized_domain = ?
                LIMIT 1
                """,
                (domain,),
            ).fetchone()
            if row:
                return f"normalized_domain matched lead #{row['id']} ({row['company_name']})"

        if email:
            row = conn.execute(
                """
                SELECT id, company_name
                FROM leads
                WHERE contact_email = ?
                LIMIT 1
                """,
                (email,),
            ).fetchone()
            if row:
                return f"contact_email matched lead #{row['id']} ({row['company_name']})"

        if website:
            rows = conn.execute(
                "SELECT id, company_name, website_url FROM leads WHERE website_url IS NOT NULL"
            ).fetchall()
            for row in rows:
                if normalize_website_url(row["website_url"]) == website:
                    return f"website_url matched lead #{row['id']} ({row['company_name']})"

    return None


def get_recent_logs(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, level, message, task, metadata, event, company_name, details, created_at
            FROM logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    logs: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw_details = item.get("details") or item.get("metadata") or "{}"
        try:
            parsed_details = json.loads(raw_details)
        except json.JSONDecodeError:
            parsed_details = {"raw": raw_details}
        if not isinstance(parsed_details, dict):
            parsed_details = {"value": parsed_details}
        item["details"] = parsed_details
        item["event"] = item.get("event") or item.get("task") or "general"
        item["company_name"] = item.get("company_name") or parsed_details.get("company_name") or parsed_details.get("company")
        item.pop("metadata", None)
        item.pop("task", None)
        logs.append(item)
    return logs


def get_latest_leads(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM leads
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_latest_run() -> dict[str, Any] | None:
    init_db()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM runs
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def get_counts() -> dict[str, int]:
    init_db()
    with get_connection() as conn:
        discovered = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        qualified = conn.execute("SELECT COUNT(*) FROM leads WHERE status = 'QUALIFIED'").fetchone()[0]
        review = conn.execute("SELECT COUNT(*) FROM leads WHERE status = 'REVIEW'").fetchone()[0]
        rejected = conn.execute("SELECT COUNT(*) FROM leads WHERE status = 'REJECTED'").fetchone()[0]
        duplicates = conn.execute(
            """
            SELECT COUNT(*)
            FROM leads
            WHERE status IN ('DUPLICATE_LOCAL', 'DUPLICATE_SHEET')
            """
        ).fetchone()[0]
        errors = conn.execute("SELECT COUNT(*) FROM logs WHERE level = 'ERROR'").fetchone()[0]

    return {
        "discovered": int(discovered),
        "qualified": int(qualified),
        "review": int(review),
        "rejected": int(rejected),
        "duplicates": int(duplicates),
        "errors": int(errors),
    }
