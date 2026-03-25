from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings, validate_gmail_config, validate_sheets_config
from app.database.db import get_conn, init_db
from app.repositories.leads import list_gmail_draft_candidates, mark_gmail_draft_created
from app.services.gmail import GmailDraftPayload, create_gmail_draft, get_gmail_service
from app.services.normalization import normalize_email
from app.services.sheets import GoogleSheetsClient, SheetRowUpdate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Gmail drafts from SQLite outreach-ready rows. Never sends emails."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of Gmail drafts to create.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include rows where selected_for_sync is false.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow new Gmail draft creation even when row already has a Gmail draft id.",
    )
    parser.add_argument(
        "--sync-marker",
        action="store_true",
        help="Write marker value back to Google Sheet for rows where Gmail draft was created.",
    )
    parser.add_argument(
        "--sheet-name",
        help="Target sheet name for marker sync (defaults to GOOGLE_SHEET_NAME).",
    )
    parser.add_argument(
        "--marker-value",
        default="GMAIL_DRAFT_CREATED",
        help="Marker value written when --sync-marker is enabled.",
    )
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.db_path)

    gmail_validation = validate_gmail_config(settings)
    if not gmail_validation.ok:
        raise SystemExit(
            "Gmail configuration is invalid:\n"
            f"{gmail_validation.format_errors()}"
        )
    for warning in gmail_validation.warnings:
        print(f"Warning: {warning}")

    sync_marker_enabled = bool(args.sync_marker)
    if sync_marker_enabled:
        sheets_validation = validate_sheets_config(settings)
        if not sheets_validation.ok:
            print(
                "Warning: Google Sheets marker sync requested, but Sheets config is invalid. "
                "Draft creation will continue without marker sync."
            )
            print(sheets_validation.format_errors())
            sync_marker_enabled = False

    with get_conn(settings.db_path) as conn:
        candidates = list_gmail_draft_candidates(
            conn,
            limit=args.limit,
            only_selected=not args.all,
            force=args.force,
        )

        if not candidates:
            print("No Gmail draft candidates found.")
            return

        gmail_service = get_gmail_service(settings)
        marker_updates: list[SheetRowUpdate] = []
        created = 0
        skipped_invalid_recipient = 0

        for candidate in candidates:
            recipient = normalize_email(candidate.recipient)
            if not recipient:
                skipped_invalid_recipient += 1
                continue

            payload = GmailDraftPayload(
                to_email=recipient,
                subject=candidate.subject,
                body=candidate.body,
            )
            gmail_draft_id = create_gmail_draft(gmail_service, payload)
            mark_gmail_draft_created(
                conn,
                outreach_item_id=candidate.outreach_item_id,
                gmail_draft_id=gmail_draft_id,
            )
            created += 1

            if sync_marker_enabled:
                marker_updates.append(
                    SheetRowUpdate(
                        row_number=candidate.source_row_number,
                        values={settings.sync_gmail_marker_column: args.marker_value},
                    )
                )

        conn.commit()

    marker_cells = 0
    if sync_marker_enabled and marker_updates:
        sheets_client = GoogleSheetsClient(settings)
        marker_cells = sheets_client.batch_update_rows(
            updates=marker_updates,
            sheet_name=args.sheet_name or settings.google_sheet_name,
        )

    print("Gmail draft push complete.")
    print(f"Candidates evaluated: {len(candidates)}")
    print(f"Drafts created: {created}")
    print(f"Skipped invalid recipients: {skipped_invalid_recipient}")
    if sync_marker_enabled:
        print(f"Sheet marker updates: {len(marker_updates)} rows, {marker_cells} cells")


if __name__ == "__main__":
    main()
