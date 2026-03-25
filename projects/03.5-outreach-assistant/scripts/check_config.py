from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings, validate_gmail_config, validate_sheets_config


def _print_result(name: str, ok: bool, errors: list[str], warnings: list[str]) -> None:
    status = "OK" if ok else "INVALID"
    print(f"{name}: {status}")
    for warning in warnings:
        print(f"  Warning: {warning}")
    for error in errors:
        print(f"  Error: {error}")


def main() -> None:
    settings = get_settings()
    sheets_validation = validate_sheets_config(settings)
    gmail_validation = validate_gmail_config(settings)

    print(f"Loaded .env from: {PROJECT_ROOT / '.env'}")
    print(f"DB path: {settings.db_path}")
    print(f"Google sheet name: {settings.google_sheet_name}")
    print()

    _print_result(
        "Google Sheets config",
        sheets_validation.ok,
        sheets_validation.errors,
        sheets_validation.warnings,
    )
    _print_result(
        "Gmail config",
        gmail_validation.ok,
        gmail_validation.errors,
        gmail_validation.warnings,
    )

    if sheets_validation.ok and gmail_validation.ok:
        print("\nConfiguration check passed.")
        return

    print("\nConfiguration check failed.")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
