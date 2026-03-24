from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    db_path: Path
    google_credentials_path: Path | None
    google_spreadsheet_id: str | None
    google_sheet_name: str
    gmail_oauth_client_secrets_path: Path | None
    gmail_token_path: Path
    external_id_column: str
    company_column: str
    website_column: str
    contact_name_column: str
    contact_value_column: str
    assistant_status_column: str
    response_column: str
    notes_column: str
    segment_column: str
    last_contacted_column: str
    follow_up_due_column: str
    sync_lead_type_column: str
    sync_assistant_status_column: str
    sync_selected_contact_column: str
    sync_draft_type_column: str
    sync_draft_subject_column: str
    sync_draft_body_column: str
    sync_personalization_note_column: str
    sync_last_processed_at_column: str
    sync_error_flag_column: str
    sync_gmail_marker_column: str
    sync_duplicate_flag_column: str
    sync_duplicate_type_column: str
    sync_duplicate_of_column: str
    sync_duplicate_reason_column: str

    @property
    def google_ready(self) -> bool:
        return bool(
            self.google_spreadsheet_id
            and self.google_credentials_path
            and self.google_credentials_path.exists()
        )


def get_settings() -> Settings:
    db_default = PROJECT_ROOT / "app" / "database" / "outreach_assistant.sqlite"
    db_path = Path(os.getenv("DB_PATH", str(db_default))).expanduser()

    creds_raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    creds_path = Path(creds_raw).expanduser() if creds_raw else None
    gmail_secrets_raw = os.getenv("GMAIL_OAUTH_CLIENT_SECRETS")
    gmail_secrets_path = Path(gmail_secrets_raw).expanduser() if gmail_secrets_raw else None
    gmail_token_default = PROJECT_ROOT / "token_gmail.json"
    gmail_token_path = Path(
        os.getenv("GMAIL_TOKEN_PATH", str(gmail_token_default))
    ).expanduser()

    return Settings(
        db_path=db_path,
        google_credentials_path=creds_path,
        google_spreadsheet_id=os.getenv("GOOGLE_SPREADSHEET_ID"),
        google_sheet_name=os.getenv("GOOGLE_SHEET_NAME", "Leads"),
        gmail_oauth_client_secrets_path=gmail_secrets_path,
        gmail_token_path=gmail_token_path,
        external_id_column=os.getenv("SHEET_EXTERNAL_ID_COLUMN", ""),
        company_column=os.getenv("SHEET_COMPANY_COLUMN", "Firma"),
        website_column=os.getenv("SHEET_WEBSITE_COLUMN", ""),
        contact_name_column=os.getenv("SHEET_CONTACT_NAME_COLUMN", ""),
        contact_value_column=os.getenv("SHEET_CONTACT_VALUE_COLUMN", "Email"),
        assistant_status_column=os.getenv("SHEET_ASSISTANT_STATUS_COLUMN", "Assistant Status"),
        response_column=os.getenv("SHEET_RESPONSE_COLUMN", "Response"),
        notes_column=os.getenv("SHEET_NOTES_COLUMN", "Notes"),
        segment_column=os.getenv("SHEET_SEGMENT_COLUMN", "Segment"),
        last_contacted_column=os.getenv("SHEET_LAST_CONTACTED_COLUMN", "Date Sent"),
        follow_up_due_column=os.getenv("SHEET_FOLLOW_UP_DUE_COLUMN", "Follow-up Date"),
        sync_lead_type_column=os.getenv("SHEET_SYNC_LEAD_TYPE_COLUMN", "Lead Type"),
        sync_assistant_status_column=os.getenv(
            "SHEET_SYNC_ASSISTANT_STATUS_COLUMN", "Assistant Status"
        ),
        sync_selected_contact_column=os.getenv(
            "SHEET_SYNC_SELECTED_CONTACT_COLUMN", "Selected Contact"
        ),
        sync_draft_type_column=os.getenv("SHEET_SYNC_DRAFT_TYPE_COLUMN", "Draft Type"),
        sync_draft_subject_column=os.getenv("SHEET_SYNC_DRAFT_SUBJECT_COLUMN", "Draft Subject"),
        sync_draft_body_column=os.getenv("SHEET_SYNC_DRAFT_BODY_COLUMN", "Draft Body"),
        sync_personalization_note_column=os.getenv(
            "SHEET_SYNC_PERSONALIZATION_NOTE_COLUMN", "Personalization Note"
        ),
        sync_last_processed_at_column=os.getenv(
            "SHEET_SYNC_LAST_PROCESSED_AT_COLUMN", "Last Processed At"
        ),
        sync_error_flag_column=os.getenv("SHEET_SYNC_ERROR_FLAG_COLUMN", "Error Flag"),
        sync_gmail_marker_column=os.getenv(
            "SHEET_SYNC_GMAIL_MARKER_COLUMN", "Gmail Draft Status"
        ),
        sync_duplicate_flag_column=os.getenv(
            "SHEET_SYNC_DUPLICATE_FLAG_COLUMN", "Duplicate Flag"
        ),
        sync_duplicate_type_column=os.getenv(
            "SHEET_SYNC_DUPLICATE_TYPE_COLUMN", "Duplicate Type"
        ),
        sync_duplicate_of_column=os.getenv(
            "SHEET_SYNC_DUPLICATE_OF_COLUMN", "Duplicate Of"
        ),
        sync_duplicate_reason_column=os.getenv(
            "SHEET_SYNC_DUPLICATE_REASON_COLUMN", "Duplicate Reason"
        ),
    )
