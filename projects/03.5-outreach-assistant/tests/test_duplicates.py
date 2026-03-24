from __future__ import annotations

import sqlite3
from pathlib import Path

from app.repositories.leads import list_gmail_draft_candidates, list_sync_candidates
from app.services.pipeline import classify_and_generate


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = Path("app/database/schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn


def _insert_lead_with_email(
    conn: sqlite3.Connection,
    *,
    row_number: int,
    email: str,
    source_sheet: str = "TEST",
) -> int:
    now = "2026-03-24T12:00:00Z"
    conn.execute(
        """
        INSERT INTO leads (
            external_id, source_sheet, source_row_number, company_name, website, notes,
            segment, human_response, source_status, raw_contact_name, raw_contact_value,
            last_contacted_at, follow_up_due_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            source_sheet,
            row_number,
            f"Shop {row_number}",
            None,
            None,
            "other",
            None,
            "",
            None,
            email,
            None,
            None,
            now,
            now,
        ),
    )
    lead_id = int(
        conn.execute(
            "SELECT id FROM leads WHERE source_sheet = ? AND source_row_number = ?",
            (source_sheet, row_number),
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
    return lead_id


def test_hard_duplicate_email_is_blocked_from_outreach_and_gmail() -> None:
    conn = _make_conn()
    first_lead_id = _insert_lead_with_email(conn, row_number=2, email="owner@example.com")
    _insert_lead_with_email(conn, row_number=3, email="owner@example.com")

    stats = classify_and_generate(conn)

    rows = conn.execute(
        """
        SELECT l.source_row_number, o.classification, o.duplicate_flag, o.duplicate_type,
               o.duplicate_of_lead_id, o.duplicate_reason
        FROM outreach_items o
        JOIN leads l ON l.id = o.lead_id
        ORDER BY l.source_row_number
        """
    ).fetchall()
    draft_count = int(conn.execute("SELECT COUNT(*) AS c FROM drafts").fetchone()["c"])
    gmail_candidates = list_gmail_draft_candidates(conn, limit=10, only_selected=True, force=False)
    conn.close()

    assert stats["processed"] == 2
    assert rows[0]["classification"] == "FIRST_TOUCH_READY"
    assert rows[0]["duplicate_flag"] == 0
    assert rows[1]["classification"] == "DONE"
    assert rows[1]["duplicate_flag"] == 1
    assert rows[1]["duplicate_type"] == "HARD"
    assert rows[1]["duplicate_of_lead_id"] == first_lead_id
    assert "same normalized email address" in str(rows[1]["duplicate_reason"]).lower()
    assert draft_count == 1
    assert len(gmail_candidates) == 1
    assert gmail_candidates[0].source_row_number == 2


def test_soft_duplicate_domain_is_flagged_but_still_draftable() -> None:
    conn = _make_conn()
    first_lead_id = _insert_lead_with_email(conn, row_number=2, email="alpha@example.com")
    _insert_lead_with_email(conn, row_number=3, email="beta@example.com")

    classify_and_generate(conn)

    rows = conn.execute(
        """
        SELECT l.source_row_number, o.classification, o.duplicate_flag, o.duplicate_type,
               o.duplicate_of_lead_id, o.duplicate_reason
        FROM outreach_items o
        JOIN leads l ON l.id = o.lead_id
        ORDER BY l.source_row_number
        """
    ).fetchall()
    draft_count = int(conn.execute("SELECT COUNT(*) AS c FROM drafts").fetchone()["c"])
    gmail_candidates = list_gmail_draft_candidates(conn, limit=10, only_selected=True, force=False)
    conn.close()

    assert rows[0]["classification"] == "FIRST_TOUCH_READY"
    assert rows[0]["duplicate_flag"] == 0
    assert rows[1]["classification"] == "FIRST_TOUCH_READY"
    assert rows[1]["duplicate_flag"] == 1
    assert rows[1]["duplicate_type"] == "SOFT"
    assert rows[1]["duplicate_of_lead_id"] == first_lead_id
    assert "same email domain" in str(rows[1]["duplicate_reason"]).lower()
    assert draft_count == 2
    assert len(gmail_candidates) == 2


def test_sync_candidates_include_duplicate_fields() -> None:
    conn = _make_conn()
    _insert_lead_with_email(conn, row_number=2, email="owner@example.com")
    _insert_lead_with_email(conn, row_number=3, email="owner@example.com")

    classify_and_generate(conn)
    candidates = list_sync_candidates(conn, only_selected=True, limit=10)
    conn.close()

    row_three = [item for item in candidates if item["source_row_number"] == 3][0]
    assert row_three["lead_type"] == "DONE"
    assert row_three["draft_type"] == ""
    assert row_three["subject"] == ""
    assert row_three["body"] == ""
    assert row_three["duplicate_flag"] == "YES"
    assert row_three["duplicate_type"] == "HARD"
    assert row_three["duplicate_of"] == "TEST:2"
    assert "same normalized email address" in row_three["duplicate_reason"].lower()
