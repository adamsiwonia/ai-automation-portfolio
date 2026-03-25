from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings, validate_sheets_config
from app.database.db import get_conn, init_db
from app.services.pipeline import import_sheet_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import leads from Google Sheets into local SQLite."
    )
    parser.add_argument("--sheet-name", help="Override source sheet tab name.")
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database schema before importing.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.init_db:
        init_db(settings.db_path)

    sheets_validation = validate_sheets_config(settings)
    if not sheets_validation.ok:
        raise SystemExit(
            "Google Sheets is not configured:\n"
            f"{sheets_validation.format_errors()}"
        )

    with get_conn(settings.db_path) as conn:
        stats = import_sheet_rows(
            conn,
            settings=settings,
            sheet_name=args.sheet_name,
        )

    print("Import complete.")
    print(f"Imported rows: {stats['imported']}")
    print(f"Valid emails: {stats['valid_email']}")
    print(f"Contact forms: {stats['contact_form']}")
    print(f"Malformed contacts: {stats['malformed']}")


if __name__ == "__main__":
    main()
