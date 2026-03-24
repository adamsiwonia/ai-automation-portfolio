from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.database.db import get_conn
from app.repositories.leads import list_sync_candidates
from app.services.pipeline import sync_outputs_to_sheet


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync assistant outputs from SQLite back to Google Sheets."
    )
    parser.add_argument("--sheet-name", help="Override destination sheet tab name.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sync rows even if selected_for_sync is false.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of rows to sync in one run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be synced without writing to Sheets.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.google_ready and not args.dry_run:
        raise SystemExit(
            "Google Sheets is not configured. Check GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_SPREADSHEET_ID."
        )

    only_selected = not args.all

    with get_conn(settings.db_path) as conn:
        if args.dry_run:
            candidates = list_sync_candidates(
                conn,
                only_selected=only_selected,
                limit=args.limit,
            )
            print(f"Dry run: {len(candidates)} row(s) would be synced.")
            for candidate in candidates[:10]:
                print(
                    f"Row {candidate['source_row_number']}: "
                    f"{candidate['classification']} | {candidate['subject']}"
                )
            return

        stats = sync_outputs_to_sheet(
            conn,
            settings=settings,
            sheet_name=args.sheet_name,
            only_selected=only_selected,
            limit=args.limit,
        )

    print("Sync complete.")
    print(f"Rows synced: {stats['rows']}")
    print(f"Cells written: {stats['cells']}")
    print(f"Draft records synced: {stats['drafts']}")


if __name__ == "__main__":
    main()
