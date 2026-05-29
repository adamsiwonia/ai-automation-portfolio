from __future__ import annotations

from services.google_sheets_client import append_qualified_lead


def write_prepared_leads(leads: list[dict]) -> int:
    """Append only high-scoring qualified leads to the Project 03.5 Sheet."""
    written = 0
    for lead in leads:
        if append_qualified_lead(lead):
            written += 1
    return written
