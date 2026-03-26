from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.services.pipeline import classify_and_generate


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = Path("app/database/schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn


def _insert_lead_with_contact(
    conn: sqlite3.Connection,
    *,
    row_number: int,
    email: str,
    last_contacted_at: str | None,
    follow_up_due_at: str | None,
    angle: str | None = None,
) -> None:
    now = "2026-03-24T12:00:00Z"
    conn.execute(
        """
        INSERT INTO leads (
            external_id, source_sheet, source_row_number, company_name, website, notes,
            segment, angle, human_response, source_status, raw_contact_name, raw_contact_value,
            last_contacted_at, follow_up_due_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            "TEST",
            row_number,
            f"Shop {row_number}",
            None,
            None,
            "other",
            angle,
            None,
            "",
            None,
            email,
            last_contacted_at,
            follow_up_due_at,
            now,
            now,
        ),
    )
    lead_id = int(
        conn.execute(
            "SELECT id FROM leads WHERE source_sheet = ? AND source_row_number = ?",
            ("TEST", row_number),
        ).fetchone()["id"]
    )
    conn.execute(
        """
        INSERT INTO contacts (
            lead_id, full_name, raw_value, email, contact_form_url,
            malformed_value, channel, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            None,
            email,
            email,
            None,
            None,
            "EMAIL",
            now,
            now,
        ),
    )


def test_rerun_does_not_create_duplicate_first_touch_drafts() -> None:
    conn = _make_conn()
    _insert_lead_with_contact(
        conn,
        row_number=2,
        email="owner@example.com",
        last_contacted_at=None,
        follow_up_due_at=None,
    )

    first_run = classify_and_generate(conn)
    second_run = classify_and_generate(conn)

    draft_count = int(conn.execute("SELECT COUNT(*) AS c FROM drafts").fetchone()["c"])
    conn.close()

    assert first_run["drafts_created"] == 1
    assert second_run["drafts_created"] == 0
    assert second_run["drafts_reused"] == 1
    assert draft_count == 1


def test_follow_up_progression_stops_after_stage_two() -> None:
    conn = _make_conn()
    today_iso = datetime.now(timezone.utc).date().isoformat()
    _insert_lead_with_contact(
        conn,
        row_number=3,
        email="followup@example.com",
        last_contacted_at="2026-03-01T09:00:00Z",
        follow_up_due_at=today_iso,
    )

    run_one = classify_and_generate(conn)
    run_two = classify_and_generate(conn)
    run_three = classify_and_generate(conn)

    outreach = conn.execute(
        "SELECT classification, follow_up_stage FROM outreach_items"
    ).fetchone()
    draft_rows = conn.execute(
        "SELECT version FROM drafts ORDER BY version ASC"
    ).fetchall()
    conn.close()

    assert run_one["classifications"]["FOLLOW_UP_READY"] == 1
    assert run_two["classifications"]["FOLLOW_UP_READY"] == 1
    assert run_three["classifications"]["DONE"] == 1

    assert outreach is not None
    assert outreach["follow_up_stage"] == 2
    assert outreach["classification"] == "DONE"

    assert [int(row["version"]) for row in draft_rows] == [1, 2]


def test_variant_tracking_is_saved_on_outreach_item() -> None:
    conn = _make_conn()
    _insert_lead_with_contact(
        conn,
        row_number=4,
        email="variant@example.com",
        last_contacted_at=None,
        follow_up_due_at=None,
        angle="VAG tuning",
    )

    classify_and_generate(conn)

    outreach = conn.execute(
        """
        SELECT
            classification,
            template_variant,
            opener_variant,
            personalization_used,
            follow_up_stage
        FROM outreach_items
        """
    ).fetchone()
    conn.close()

    assert outreach is not None
    assert outreach["classification"] == "FIRST_TOUCH_READY"
    assert outreach["template_variant"] in ("soft", "direct", "bold")
    assert outreach["opener_variant"]
    assert int(outreach["personalization_used"]) == 1
    assert int(outreach["follow_up_stage"]) == 0


def test_follow_up_reuses_subject_from_original_first_touch_draft() -> None:
    conn = _make_conn()
    _insert_lead_with_contact(
        conn,
        row_number=5,
        email="threading@example.com",
        last_contacted_at=None,
        follow_up_due_at=None,
    )

    classify_and_generate(conn)
    first_touch_subject = str(
        conn.execute("SELECT subject FROM drafts WHERE version = 1").fetchone()["subject"]
    )

    conn.execute(
        """
        UPDATE leads
        SET last_contacted_at = ?, follow_up_due_at = ?, updated_at = ?
        WHERE source_sheet = ? AND source_row_number = ?
        """,
        (
            "2026-03-01T09:00:00Z",
            datetime.now(timezone.utc).date().isoformat(),
            "2026-03-24T12:00:00Z",
            "TEST",
            5,
        ),
    )
    conn.commit()

    classify_and_generate(conn)
    follow_up_subject = str(
        conn.execute("SELECT subject FROM drafts WHERE version = 2").fetchone()["subject"]
    )
    conn.close()

    assert follow_up_subject == first_touch_subject

