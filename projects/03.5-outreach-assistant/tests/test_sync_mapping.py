from __future__ import annotations

import sqlite3
from pathlib import Path

from app.repositories.leads import (
    list_gmail_draft_candidates,
    list_sync_candidates,
    mark_gmail_draft_created,
)


def test_sync_lead_type_uses_classification_not_segment() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = Path("app/database/schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)

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
            "TEST",
            2,
            "Shop",
            None,
            None,
            "outdoor_shop",
            None,
            "",
            None,
            "owner@example.com",
            None,
            None,
            now,
            now,
        ),
    )
    lead_id = int(conn.execute("SELECT id FROM leads").fetchone()["id"])

    conn.execute(
        """
        INSERT INTO outreach_items (
            lead_id, contact_id, classification, reason, pipeline_state, selected_for_sync,
            source_last_synced_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            None,
            "FOLLOW_UP_READY",
            "Follow-up Date is due.",
            "PENDING",
            1,
            None,
            now,
            now,
        ),
    )
    conn.commit()

    candidates = list_sync_candidates(conn, only_selected=True, limit=10)
    conn.close()

    assert len(candidates) == 1
    assert candidates[0]["lead_type"] == "FOLLOW_UP_READY"


def test_follow_up_skipped_does_not_sync_draft_content() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = Path("app/database/schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)

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
            "TEST",
            3,
            "Shop",
            None,
            None,
            "other",
            None,
            "",
            None,
            "owner@example.com",
            "2026-03-01",
            "2026-03-10",
            now,
            now,
        ),
    )
    lead_id = int(conn.execute("SELECT id FROM leads WHERE source_row_number = 3").fetchone()["id"])

    conn.execute(
        """
        INSERT INTO outreach_items (
            lead_id, contact_id, classification, reason, pipeline_state, selected_for_sync,
            source_last_synced_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            None,
            "FOLLOW_UP_SKIPPED",
            "Follow-up skipped because manual Follow-up Date is in the past.",
            "REVIEWED",
            1,
            None,
            now,
            now,
        ),
    )
    conn.commit()

    candidates = list_sync_candidates(conn, only_selected=True, limit=10)
    conn.close()

    assert len(candidates) == 1
    assert candidates[0]["lead_type"] == "FOLLOW_UP_SKIPPED"
    assert candidates[0]["draft_type"] == ""
    assert candidates[0]["subject"] == ""
    assert candidates[0]["body"] == ""


def test_gmail_candidates_include_ready_rows_without_existing_gmail_draft() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = Path("app/database/schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)

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
            "TEST",
            4,
            "Shop",
            None,
            None,
            "other",
            None,
            "",
            None,
            "owner@example.com",
            None,
            None,
            now,
            now,
        ),
    )
    lead_id = int(conn.execute("SELECT id FROM leads WHERE source_row_number = 4").fetchone()["id"])

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
            "owner@example.com",
            "owner@example.com",
            None,
            None,
            "EMAIL",
            now,
            now,
        ),
    )
    contact_id = int(conn.execute("SELECT id FROM contacts WHERE lead_id = ?", (lead_id,)).fetchone()["id"])

    conn.execute(
        """
        INSERT INTO outreach_items (
            lead_id, contact_id, classification, reason, pipeline_state, selected_for_sync,
            source_last_synced_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            contact_id,
            "FIRST_TOUCH_READY",
            "Date Sent is empty.",
            "DRAFTED",
            1,
            None,
            now,
            now,
        ),
    )
    outreach_item_id = int(conn.execute("SELECT id FROM outreach_items WHERE lead_id = ?", (lead_id,)).fetchone()["id"])

    conn.execute(
        """
        INSERT INTO drafts (
            outreach_item_id, version, subject, body, generator, selected_for_sync,
            synced_to_sheet, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            outreach_item_id,
            1,
            "Quick question about customer emails",
            "Hi there,\nBest,\nAdam",
            "template-v1",
            1,
            0,
            now,
        ),
    )
    conn.commit()

    candidates = list_gmail_draft_candidates(conn, limit=10, only_selected=True, force=False)
    conn.close()

    assert len(candidates) == 1
    assert candidates[0].recipient == "owner@example.com"
    assert candidates[0].classification == "FIRST_TOUCH_READY"


def test_gmail_candidates_skip_existing_unless_force() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = Path("app/database/schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)

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
            "TEST",
            5,
            "Shop",
            None,
            None,
            "other",
            None,
            "",
            None,
            "owner@example.com",
            None,
            None,
            now,
            now,
        ),
    )
    lead_id = int(conn.execute("SELECT id FROM leads WHERE source_row_number = 5").fetchone()["id"])

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
            "owner@example.com",
            "owner@example.com",
            None,
            None,
            "EMAIL",
            now,
            now,
        ),
    )
    contact_id = int(conn.execute("SELECT id FROM contacts WHERE lead_id = ?", (lead_id,)).fetchone()["id"])

    conn.execute(
        """
        INSERT INTO outreach_items (
            lead_id, contact_id, classification, reason, pipeline_state, selected_for_sync,
            gmail_draft_id, source_last_synced_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            contact_id,
            "FOLLOW_UP_READY",
            "Follow-up Date set to today.",
            "DRAFTED",
            1,
            "r_existing_draft",
            None,
            now,
            now,
        ),
    )
    outreach_item_id = int(conn.execute("SELECT id FROM outreach_items WHERE lead_id = ?", (lead_id,)).fetchone()["id"])

    conn.execute(
        """
        INSERT INTO drafts (
            outreach_item_id, version, subject, body, generator, selected_for_sync,
            synced_to_sheet, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            outreach_item_id,
            1,
            "Quick follow-up",
            "Hi there,\nBest,\nAdam",
            "template-v1",
            1,
            0,
            now,
        ),
    )
    conn.commit()

    skipped = list_gmail_draft_candidates(conn, limit=10, force=False)
    forced = list_gmail_draft_candidates(conn, limit=10, force=True)
    conn.close()

    assert skipped == []
    assert len(forced) == 1


def test_mark_gmail_draft_created_persists_id() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = Path("app/database/schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)

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
            "TEST",
            6,
            "Shop",
            None,
            None,
            "other",
            None,
            "",
            None,
            "owner@example.com",
            None,
            None,
            now,
            now,
        ),
    )
    lead_id = int(conn.execute("SELECT id FROM leads WHERE source_row_number = 6").fetchone()["id"])
    conn.execute(
        """
        INSERT INTO outreach_items (
            lead_id, contact_id, classification, reason, pipeline_state, selected_for_sync,
            source_last_synced_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            None,
            "FIRST_TOUCH_READY",
            "Date Sent is empty.",
            "PENDING",
            1,
            None,
            now,
            now,
        ),
    )
    outreach_item_id = int(conn.execute("SELECT id FROM outreach_items WHERE lead_id = ?", (lead_id,)).fetchone()["id"])

    mark_gmail_draft_created(
        conn,
        outreach_item_id=outreach_item_id,
        gmail_draft_id="r_new_draft",
    )
    conn.commit()
    row = conn.execute(
        "SELECT gmail_draft_id, gmail_draft_created_at FROM outreach_items WHERE id = ?",
        (outreach_item_id,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["gmail_draft_id"] == "r_new_draft"
    assert row["gmail_draft_created_at"] is not None
