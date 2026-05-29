from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import database
from services.deduplication import normalize_domain, normalize_email, normalize_website_url
from services.lead_safety import MOCK_SOURCE_MARKERS


DEFAULT_SOURCE = "MANUAL_CSV"
REQUIRED_COLUMNS = ["company", "email", "domain", "website_url", "niche", "source", "notes"]


def import_real_leads_csv(csv_path: Path | str) -> dict[str, Any]:
    path = Path(csv_path)
    database.init_db()

    imported_ids: list[int] = []
    skipped_duplicates: list[dict[str, str]] = []
    skipped_invalid: list[dict[str, str]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing_columns = _missing_columns(reader.fieldnames)
        if missing_columns:
            raise ValueError(f"Missing required CSV column(s): {', '.join(missing_columns)}")

        for row_number, row in enumerate(reader, start=2):
            lead = _row_to_lead(row, source_file=path.name)
            if not lead["company_name"]:
                skipped_invalid.append({"row": str(row_number), "reason": "missing company"})
                continue

            duplicate_reason = database.find_duplicate_lead(lead)
            if duplicate_reason:
                skipped_duplicates.append(
                    {
                        "row": str(row_number),
                        "company": lead["company_name"],
                        "reason": duplicate_reason,
                    }
                )
                continue

            imported_ids.append(database.insert_lead(lead))

    database.add_log(
        "SUCCESS" if imported_ids else "INFO",
        (
            f"Imported {len(imported_ids)} real lead(s) from CSV; "
            f"skipped {len(skipped_duplicates)} duplicate(s), {len(skipped_invalid)} invalid row(s)."
        ),
        task="manual_csv_import",
        event="manual_csv_import_completed",
        details={
            "path": str(path),
            "imported_ids": imported_ids,
            "skipped_duplicates": skipped_duplicates,
            "skipped_invalid": skipped_invalid,
        },
    )

    return {
        "path": str(path),
        "imported_count": len(imported_ids),
        "skipped_duplicate_count": len(skipped_duplicates),
        "skipped_invalid_count": len(skipped_invalid),
        "imported_ids": imported_ids,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid,
    }


def _row_to_lead(row: dict[str, str], source_file: str) -> dict[str, Any]:
    company = _cell(row, "company")
    email = normalize_email(_cell(row, "email"))
    website_url = _cell(row, "website_url")
    domain = normalize_domain(_cell(row, "domain") or website_url)
    if not website_url and domain:
        website_url = f"https://{domain}"
    normalized_domain = normalize_domain(domain or website_url)
    source = _safe_real_source(_cell(row, "source"))
    notes = _cell(row, "notes")

    return {
        "company_name": company,
        "website_url": normalize_website_url(website_url) or website_url,
        "normalized_domain": normalized_domain,
        "contact_email": email,
        "niche": _cell(row, "niche"),
        "status": "REVIEW",
        "reason": notes or "Imported from real lead CSV.",
        "source_query": f"manual_csv:{source_file}",
        "source": source,
        "lead_source_mode": "manual",
        "snippet": notes,
    }


def _cell(row: dict[str, str], column: str) -> str:
    return str(row.get(column) or "").strip()


def _safe_real_source(value: str) -> str:
    source = value.strip() or DEFAULT_SOURCE
    if source.lower() in MOCK_SOURCE_MARKERS:
        return DEFAULT_SOURCE
    return source


def _missing_columns(fieldnames: list[str] | None) -> list[str]:
    available = {str(field or "").strip().lower() for field in fieldnames or []}
    return [column for column in REQUIRED_COLUMNS if column not in available]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import real leads from CSV into Project 05 SQLite.")
    parser.add_argument("csv_path", help="CSV file with company,email,domain,website_url,niche,source,notes columns.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = import_real_leads_csv(args.csv_path)
    print(f"Imported {result['imported_count']} lead(s)")
    print(f"Skipped duplicates: {result['skipped_duplicate_count']}")
    print(f"Skipped invalid rows: {result['skipped_invalid_count']}")
    print(f"CSV: {result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
