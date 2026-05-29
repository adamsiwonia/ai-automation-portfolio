from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from services import database
from services.lead_safety import is_mock_or_demo_lead


BASE_DIR = Path(__file__).resolve().parents[1]
EXPORTS_DIR = BASE_DIR / "exports"
DEFAULT_EXPORT_PATH = EXPORTS_DIR / "project035_approved_leads.csv"

PROJECT035_HEADERS = [
    "Company",
    "Email",
    "Date Sent",
    "Follow up Date",
    "Response",
    "Notes",
    "Segment",
    "Lead Type",
    "Assistant Status",
    "Selected Contact",
    "Draft Type",
    "Draft Subject",
    "Draft Body",
    "Personalization Note",
    "Last Processed At",
    "Error Flag",
    "Duplicate Type",
    "Duplicate Reason",
    "Duplicate Of",
    "Duplicate Flag",
    "Gmail Draft Status",
]


def approved_leads_for_export() -> list[dict[str, Any]]:
    database.init_db()
    with database.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM leads
            WHERE status = 'APPROVED_FOR_OUTREACH'
              AND (exported_at IS NULL OR exported_at = '')
            ORDER BY id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def lead_to_project035_row(lead: dict[str, Any]) -> dict[str, str]:
    email = str(lead.get("contact_email") or "").strip()
    return {
        "Company": str(lead.get("company_name") or "").strip(),
        "Email": email,
        "Date Sent": "",
        "Follow up Date": "",
        "Response": "",
        "Notes": _notes(lead),
        "Segment": str(lead.get("niche") or "").strip(),
        "Lead Type": "Project 05",
        "Assistant Status": "NEW",
        "Selected Contact": email,
        "Draft Type": "",
        "Draft Subject": "",
        "Draft Body": "",
        "Personalization Note": _personalization_note(lead),
        "Last Processed At": "",
        "Error Flag": "",
        "Duplicate Type": "",
        "Duplicate Reason": "",
        "Duplicate Of": "",
        "Duplicate Flag": "FALSE",
        "Gmail Draft Status": "NOT_CREATED",
    }


def export_approved_leads(
    export_path: Path | str = DEFAULT_EXPORT_PATH,
    include_mock: bool = False,
) -> dict[str, Any]:
    approved_leads = approved_leads_for_export()
    skipped_mock_leads = [] if include_mock else [lead for lead in approved_leads if is_mock_or_demo_lead(lead)]
    leads = approved_leads if include_mock else [lead for lead in approved_leads if not is_mock_or_demo_lead(lead)]
    path = Path(export_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=PROJECT035_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead_to_project035_row(lead))

    if skipped_mock_leads:
        database.add_log(
            "WARNING",
            f"Skipped {len(skipped_mock_leads)} mock/demo approved lead(s) during Project 03.5 CSV export.",
            task="project035_csv_export",
            event="project035_csv_mock_skipped",
            details={
                "path": str(path),
                "lead_ids": [int(lead["id"]) for lead in skipped_mock_leads],
                "hint": "Use --include-mock only for tests.",
            },
        )

    if leads:
        exported_at = database.utc_now()
        lead_ids = [int(lead["id"]) for lead in leads]
        placeholders = ", ".join(["?"] * len(lead_ids))
        with database.get_connection() as conn:
            conn.execute(
                f"""
                UPDATE leads
                SET exported_at = ?,
                    updated_at = ?
                WHERE id IN ({placeholders})
                """,
                [exported_at, exported_at, *lead_ids],
            )
        database.add_log(
            "SUCCESS",
            f"Exported {len(leads)} approved lead(s) to Project 03.5 CSV.",
            task="project035_csv_export",
            event="project035_csv_exported",
            details={"path": str(path), "lead_ids": lead_ids},
        )
    else:
        database.add_log(
            "INFO",
            "No approved unexported leads found for Project 03.5 CSV export.",
            task="project035_csv_export",
            event="project035_csv_noop",
            details={"path": str(path)},
        )

    return {
        "path": str(path),
        "exported_count": len(leads),
        "skipped_mock_count": len(skipped_mock_leads),
        "included_mock_count": 0 if not include_mock else sum(1 for lead in approved_leads if is_mock_or_demo_lead(lead)),
    }


def _personalization_note(lead: dict[str, Any]) -> str:
    parts = [
        str(lead.get("recommended_angle") or "").strip(),
        str(lead.get("personal_note") or "").strip(),
    ]
    return " | ".join(part for part in parts if part)


def _notes(lead: dict[str, Any]) -> str:
    score = lead.get("score")
    reason = str(lead.get("reason") or "").strip()
    parts: list[str] = []
    if score not in {None, ""}:
        parts.append(f"Score: {score}")
    if reason:
        parts.append(f"Reason: {reason}")
    return " | ".join(parts)
