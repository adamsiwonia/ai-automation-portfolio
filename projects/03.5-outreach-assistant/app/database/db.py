from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "app" / "database" / "schema.sql"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    resolved_path = Path(db_path) if db_path else get_settings().db_path
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(resolved_path, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db(db_path: Path | None = None) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_conn(db_path) as conn:
        conn.executescript(schema)
        _ensure_leads_columns(conn)
        _ensure_outreach_items_classification_values(conn)
        _ensure_outreach_items_columns(conn)
        _backfill_gmail_draft_for_draft_id(conn)
        conn.commit()


def _ensure_leads_columns(conn: sqlite3.Connection) -> None:
    columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(leads)").fetchall()
    }
    if "segment" not in columns:
        conn.execute("ALTER TABLE leads ADD COLUMN segment TEXT")
    if "human_response" not in columns:
        conn.execute("ALTER TABLE leads ADD COLUMN human_response TEXT")
    if "angle" not in columns:
        conn.execute("ALTER TABLE leads ADD COLUMN angle TEXT")


def _ensure_outreach_items_classification_values(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'outreach_items'
        """
    ).fetchone()
    if not row or not row["sql"]:
        return

    table_sql = str(row["sql"])
    if "FOLLOW_UP_SKIPPED" in table_sql:
        return

    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;

        CREATE TABLE outreach_items_new (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          lead_id INTEGER NOT NULL,
          contact_id INTEGER,
          classification TEXT NOT NULL
            CHECK (
              classification IN (
                'FIRST_TOUCH_READY',
                'FOLLOW_UP_READY',
                'FOLLOW_UP_SKIPPED',
                'CONTACT_FORM_REVIEW',
                'EMAIL_NEEDS_REVIEW',
                'DONE'
              )
            ),
          reason TEXT,
          duplicate_flag INTEGER NOT NULL DEFAULT 0
            CHECK (duplicate_flag IN (0, 1)),
          duplicate_type TEXT
            CHECK (duplicate_type IN ('HARD', 'SOFT') OR duplicate_type IS NULL),
          duplicate_of_lead_id INTEGER,
          duplicate_reason TEXT,
          template_variant TEXT,
          opener_variant TEXT,
          personalization_used INTEGER NOT NULL DEFAULT 0
            CHECK (personalization_used IN (0, 1)),
          follow_up_stage INTEGER NOT NULL DEFAULT 0,
          pipeline_state TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (pipeline_state IN ('PENDING', 'DRAFTED', 'REVIEWED', 'DONE')),
          selected_for_sync INTEGER NOT NULL DEFAULT 1,
          gmail_draft_id TEXT,
          gmail_draft_for_draft_id INTEGER,
          gmail_draft_created_at TEXT,
          source_last_synced_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE (lead_id),
          FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
          FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL,
          FOREIGN KEY (duplicate_of_lead_id) REFERENCES leads(id) ON DELETE SET NULL
        );

        INSERT INTO outreach_items_new (
          id,
          lead_id,
          contact_id,
          classification,
          reason,
          duplicate_flag,
          duplicate_type,
          duplicate_of_lead_id,
          duplicate_reason,
          template_variant,
          opener_variant,
          personalization_used,
          follow_up_stage,
          pipeline_state,
          selected_for_sync,
          gmail_draft_id,
          gmail_draft_for_draft_id,
          gmail_draft_created_at,
          source_last_synced_at,
          created_at,
          updated_at
        )
        SELECT
          id,
          lead_id,
          contact_id,
          classification,
          reason,
          0 AS duplicate_flag,
          NULL AS duplicate_type,
          NULL AS duplicate_of_lead_id,
          NULL AS duplicate_reason,
          NULL AS template_variant,
          NULL AS opener_variant,
          0 AS personalization_used,
          0 AS follow_up_stage,
          pipeline_state,
          selected_for_sync,
          NULL AS gmail_draft_id,
          NULL AS gmail_draft_for_draft_id,
          NULL AS gmail_draft_created_at,
          source_last_synced_at,
          created_at,
          updated_at
        FROM outreach_items;

        DROP TABLE outreach_items;
        ALTER TABLE outreach_items_new RENAME TO outreach_items;

        CREATE INDEX IF NOT EXISTS idx_outreach_classification
          ON outreach_items(classification);
        CREATE INDEX IF NOT EXISTS idx_outreach_selected
          ON outreach_items(selected_for_sync);
        CREATE INDEX IF NOT EXISTS idx_outreach_duplicate_flag
          ON outreach_items(duplicate_flag);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_outreach_gmail_draft_id
          ON outreach_items(gmail_draft_id);

        PRAGMA foreign_keys = ON;
        """
    )


def _ensure_outreach_items_columns(conn: sqlite3.Connection) -> None:
    columns = {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(outreach_items)").fetchall()
    }
    if "gmail_draft_id" not in columns:
        conn.execute("ALTER TABLE outreach_items ADD COLUMN gmail_draft_id TEXT")
    if "gmail_draft_for_draft_id" not in columns:
        conn.execute(
            "ALTER TABLE outreach_items ADD COLUMN gmail_draft_for_draft_id INTEGER"
        )
    if "gmail_draft_created_at" not in columns:
        conn.execute("ALTER TABLE outreach_items ADD COLUMN gmail_draft_created_at TEXT")
    if "duplicate_flag" not in columns:
        conn.execute(
            "ALTER TABLE outreach_items ADD COLUMN duplicate_flag INTEGER NOT NULL DEFAULT 0"
        )
    if "duplicate_type" not in columns:
        conn.execute("ALTER TABLE outreach_items ADD COLUMN duplicate_type TEXT")
    if "duplicate_of_lead_id" not in columns:
        conn.execute("ALTER TABLE outreach_items ADD COLUMN duplicate_of_lead_id INTEGER")
    if "duplicate_reason" not in columns:
        conn.execute("ALTER TABLE outreach_items ADD COLUMN duplicate_reason TEXT")
    if "template_variant" not in columns:
        conn.execute("ALTER TABLE outreach_items ADD COLUMN template_variant TEXT")
    if "opener_variant" not in columns:
        conn.execute("ALTER TABLE outreach_items ADD COLUMN opener_variant TEXT")
    if "personalization_used" not in columns:
        conn.execute(
            "ALTER TABLE outreach_items ADD COLUMN personalization_used INTEGER NOT NULL DEFAULT 0"
        )
    if "follow_up_stage" not in columns:
        conn.execute(
            "ALTER TABLE outreach_items ADD COLUMN follow_up_stage INTEGER NOT NULL DEFAULT 0"
        )

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_outreach_gmail_draft_id
          ON outreach_items(gmail_draft_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_duplicate_flag
          ON outreach_items(duplicate_flag)
        """
    )


def _backfill_gmail_draft_for_draft_id(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE outreach_items
        SET gmail_draft_for_draft_id = (
            SELECT d.id
            FROM drafts d
            WHERE d.outreach_item_id = outreach_items.id
              AND (
                  outreach_items.gmail_draft_created_at IS NULL
                  OR d.created_at <= outreach_items.gmail_draft_created_at
              )
            ORDER BY d.version DESC
            LIMIT 1
        )
        WHERE gmail_draft_id IS NOT NULL
          AND gmail_draft_for_draft_id IS NULL
        """
    )
