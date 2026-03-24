from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.database.db import get_conn, init_db
from app.services.pipeline import classify_and_generate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify imported leads and generate outreach drafts."
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database schema before processing.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.init_db:
        init_db(settings.db_path)

    with get_conn(settings.db_path) as conn:
        stats = classify_and_generate(conn)

    print("Processing complete.")
    print(f"Leads processed: {stats['processed']}")
    print(f"Drafts created: {stats['drafts_created']}")
    print(f"Drafts reused: {stats['drafts_reused']}")
    print("Classification counts:")
    for name, count in sorted(stats["classifications"].items()):
        print(f"- {name}: {count}")


if __name__ == "__main__":
    main()
