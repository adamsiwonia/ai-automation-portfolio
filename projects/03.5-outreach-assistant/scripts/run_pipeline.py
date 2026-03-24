from __future__ import annotations

import argparse
import pprint
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.database.db import get_conn, init_db
from app.services.pipeline import run_full_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run full outreach pipeline: import -> classify -> draft -> sync."
    )
    parser.add_argument("--sheet-name", help="Override source/destination sheet tab name.")
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Run import + process only, without sync.",
    )
    parser.add_argument(
        "--sync-all",
        action="store_true",
        help="Sync all rows, including selected_for_sync = 0.",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database schema before running.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.init_db:
        init_db(settings.db_path)

    if not settings.google_ready:
        raise SystemExit(
            "Google Sheets is not configured. Check GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_SPREADSHEET_ID."
        )

    with get_conn(settings.db_path) as conn:
        stats = run_full_pipeline(
            conn,
            settings=settings,
            sheet_name=args.sheet_name,
            sync=not args.skip_sync,
            only_selected_sync=not args.sync_all,
        )

    pprint.pprint(stats)


if __name__ == "__main__":
    main()
