from __future__ import annotations

import sqlite3
from pathlib import Path

from app.repositories.leads import upsert_lead_and_contact
from app.services.normalization import NormalizedLeadRow


def _row(*, notes: str | None, response: str | None, segment: str) -> NormalizedLeadRow:
    return NormalizedLeadRow(
        source_sheet="Leads",
        source_row_number=2,
        external_id=None,
        company_name="Northwind",
        website=None,
        notes=notes,
        segment=segment,
        angle=None,
        human_response=response,
        source_status="new",
        contact_name=None,
        raw_contact_value="alex@example.com",
        email="alex@example.com",
        contact_form_url=None,
        malformed_contact_value=None,
        contact_channel="EMAIL",
        last_contacted_at=None,
        follow_up_due_at=None,
    )


def test_upsert_preserves_existing_notes_and_response() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    schema = Path("app/database/schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)

    upsert_lead_and_contact(
        conn,
        _row(notes="Original notes", response="Initial response", segment="SaaS"),
    )
    upsert_lead_and_contact(
        conn,
        _row(
            notes="Imported note should not overwrite",
            response="Imported response should not overwrite",
            segment="Fintech",
        ),
    )
    conn.commit()

    lead = conn.execute(
        "SELECT notes, human_response, segment FROM leads WHERE source_sheet = ? AND source_row_number = ?",
        ("Leads", 2),
    ).fetchone()
    conn.close()

    assert lead is not None
    assert lead["notes"] == "Original notes"
    assert lead["human_response"] == "Initial response"
    assert lead["segment"] == "Fintech"
