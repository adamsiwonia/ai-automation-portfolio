from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.project035_csv_export import DEFAULT_EXPORT_PATH, export_approved_leads


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export approved Project 05 leads to a Project 03.5-compatible CSV.")
    parser.add_argument("export_path", nargs="?", help="Optional CSV output path.")
    parser.add_argument(
        "--include-mock",
        action="store_true",
        help="Include mock/demo leads. Use only for tests, never real outreach.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    export_path = Path(args.export_path) if args.export_path else DEFAULT_EXPORT_PATH
    result = export_approved_leads(export_path, include_mock=args.include_mock)
    print(f"Exported {result['exported_count']} lead(s)")
    if result.get("skipped_mock_count"):
        print(
            f"Skipped {result['skipped_mock_count']} mock/demo lead(s). "
            "Use --include-mock only for tests."
        )
    if args.include_mock and result.get("included_mock_count"):
        print(f"Included {result['included_mock_count']} mock/demo lead(s) because --include-mock was set.")
    print(f"CSV: {result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
