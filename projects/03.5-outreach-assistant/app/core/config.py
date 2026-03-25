from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH)
_DOTENV_VALUES = dotenv_values(ENV_PATH)


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
        spreadsheet_id = (self.google_spreadsheet_id or "").strip()
        return bool(
            spreadsheet_id
            and self.google_credentials_path
            and self.google_credentials_path.exists()
        )


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]

    def format_errors(self) -> str:
        return "\n".join(f"- {error}" for error in self.errors)


def _env_raw(name: str) -> tuple[str | None, str | None, Literal["missing", "empty", "set"]]:
    if name in os.environ:
        raw = os.environ.get(name)
        value = str(raw) if raw is not None else ""
        trimmed = value.strip()
        return "environment", trimmed, "set" if trimmed else "empty"

    if name in _DOTENV_VALUES:
        raw = _DOTENV_VALUES.get(name)
        value = str(raw) if raw is not None else ""
        trimmed = value.strip()
        return ".env", trimmed, "set" if trimmed else "empty"

    return None, None, "missing"


def _read_env(name: str, default: str | None = None) -> str | None:
    _, value, state = _env_raw(name)
    if state == "set":
        return value

    if default is None:
        return None
    return str(default).strip()


def _resolve_path(raw_value: str | None) -> Path | None:
    if not raw_value:
        return None

    value = raw_value.strip().strip('"').strip("'")
    if not value:
        return None

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate


def validate_sheets_config(settings: Settings | None = None) -> ValidationResult:
    resolved = settings or get_settings()
    errors: list[str] = []
    warnings: list[str] = []

    _, sheet_id_value, sheet_id_state = _env_raw("GOOGLE_SPREADSHEET_ID")
    if sheet_id_state == "missing":
        errors.append("GOOGLE_SPREADSHEET_ID is missing.")
    elif sheet_id_state == "empty":
        errors.append("GOOGLE_SPREADSHEET_ID is empty.")
    elif not sheet_id_value:
        errors.append("GOOGLE_SPREADSHEET_ID could not be resolved.")

    creds_source, creds_raw_value, creds_state = _env_raw("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_state == "missing":
        errors.append("GOOGLE_APPLICATION_CREDENTIALS is missing.")
    elif creds_state == "empty":
        errors.append("GOOGLE_APPLICATION_CREDENTIALS is empty.")
    else:
        creds_path = resolved.google_credentials_path
        if not creds_path:
            errors.append("GOOGLE_APPLICATION_CREDENTIALS could not be resolved to a file path.")
        elif not creds_path.exists():
            source_label = creds_source or "environment"
            errors.append(
                "GOOGLE_APPLICATION_CREDENTIALS points to a file that does not exist: "
                f"{creds_path} (from {source_label}: {creds_raw_value})"
            )
        elif not creds_path.is_file():
            errors.append(
                f"GOOGLE_APPLICATION_CREDENTIALS is not a file path: {creds_path}"
            )

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def validate_gmail_config(settings: Settings | None = None) -> ValidationResult:
    resolved = settings or get_settings()
    errors: list[str] = []
    warnings: list[str] = []

    secrets_source, secrets_raw_value, secrets_state = _env_raw("GMAIL_OAUTH_CLIENT_SECRETS")
    if secrets_state == "missing":
        errors.append("GMAIL_OAUTH_CLIENT_SECRETS is missing.")
    elif secrets_state == "empty":
        errors.append("GMAIL_OAUTH_CLIENT_SECRETS is empty.")
    else:
        secrets_path = resolved.gmail_oauth_client_secrets_path
        if not secrets_path:
            errors.append("GMAIL_OAUTH_CLIENT_SECRETS could not be resolved to a file path.")
        elif not secrets_path.exists():
            source_label = secrets_source or "environment"
            errors.append(
                "GMAIL_OAUTH_CLIENT_SECRETS points to a file that does not exist: "
                f"{secrets_path} (from {source_label}: {secrets_raw_value})"
            )
        elif not secrets_path.is_file():
            errors.append(f"GMAIL_OAUTH_CLIENT_SECRETS is not a file path: {secrets_path}")

    _, token_value, token_state = _env_raw("GMAIL_TOKEN_PATH")
    if token_state == "missing":
        warnings.append(
            "GMAIL_TOKEN_PATH is missing; default token path under project root will be used."
        )
    elif token_state == "empty":
        warnings.append(
            "GMAIL_TOKEN_PATH is empty; default token path under project root will be used."
        )
    elif not token_value:
        warnings.append("GMAIL_TOKEN_PATH could not be resolved; default token path will be used.")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def get_settings() -> Settings:
    db_default = PROJECT_ROOT / "app" / "database" / "outreach_assistant.sqlite"
    db_path = _resolve_path(_read_env("DB_PATH", str(db_default))) or db_default

    creds_path = _resolve_path(_read_env("GOOGLE_APPLICATION_CREDENTIALS"))
    gmail_secrets_path = _resolve_path(_read_env("GMAIL_OAUTH_CLIENT_SECRETS"))
    gmail_token_default = PROJECT_ROOT / "token_gmail.json"
    gmail_token_path = (
        _resolve_path(_read_env("GMAIL_TOKEN_PATH", str(gmail_token_default)))
        or gmail_token_default
    )

    return Settings(
        db_path=db_path,
        google_credentials_path=creds_path,
        google_spreadsheet_id=_read_env("GOOGLE_SPREADSHEET_ID"),
        google_sheet_name=_read_env("GOOGLE_SHEET_NAME", "Leads") or "Leads",
        gmail_oauth_client_secrets_path=gmail_secrets_path,
        gmail_token_path=gmail_token_path,
        external_id_column=_read_env("SHEET_EXTERNAL_ID_COLUMN", "") or "",
        company_column=_read_env("SHEET_COMPANY_COLUMN", "Company") or "Company",
        website_column=_read_env("SHEET_WEBSITE_COLUMN", "") or "",
        contact_name_column=_read_env("SHEET_CONTACT_NAME_COLUMN", "") or "",
        contact_value_column=_read_env("SHEET_CONTACT_VALUE_COLUMN", "Email") or "Email",
        assistant_status_column=_read_env("SHEET_ASSISTANT_STATUS_COLUMN", "Assistant Status")
        or "Assistant Status",
        response_column=_read_env("SHEET_RESPONSE_COLUMN", "Response") or "Response",
        notes_column=_read_env("SHEET_NOTES_COLUMN", "Notes") or "Notes",
        segment_column=_read_env("SHEET_SEGMENT_COLUMN", "Segment") or "Segment",
        last_contacted_column=_read_env("SHEET_LAST_CONTACTED_COLUMN", "Date Sent")
        or "Date Sent",
        follow_up_due_column=_read_env("SHEET_FOLLOW_UP_DUE_COLUMN", "Follow Up Date")
        or "Follow Up Date",
        sync_lead_type_column=_read_env("SHEET_SYNC_LEAD_TYPE_COLUMN", "Lead Type")
        or "Lead Type",
        sync_assistant_status_column=_read_env(
            "SHEET_SYNC_ASSISTANT_STATUS_COLUMN", "Assistant Status"
        )
        or "Assistant Status",
        sync_selected_contact_column=_read_env(
            "SHEET_SYNC_SELECTED_CONTACT_COLUMN", "Selected Contact"
        )
        or "Selected Contact",
        sync_draft_type_column=_read_env("SHEET_SYNC_DRAFT_TYPE_COLUMN", "Draft Type")
        or "Draft Type",
        sync_draft_subject_column=_read_env(
            "SHEET_SYNC_DRAFT_SUBJECT_COLUMN", "Draft Subject"
        )
        or "Draft Subject",
        sync_draft_body_column=_read_env("SHEET_SYNC_DRAFT_BODY_COLUMN", "Draft Body")
        or "Draft Body",
        sync_personalization_note_column=_read_env(
            "SHEET_SYNC_PERSONALIZATION_NOTE_COLUMN", "Personalization Note"
        )
        or "Personalization Note",
        sync_last_processed_at_column=_read_env(
            "SHEET_SYNC_LAST_PROCESSED_AT_COLUMN", "Last Processed At"
        )
        or "Last Processed At",
        sync_error_flag_column=_read_env("SHEET_SYNC_ERROR_FLAG_COLUMN", "Error Flag")
        or "Error Flag",
        sync_gmail_marker_column=_read_env(
            "SHEET_SYNC_GMAIL_MARKER_COLUMN", "Gmail Draft Status"
        )
        or "Gmail Draft Status",
        sync_duplicate_flag_column=_read_env(
            "SHEET_SYNC_DUPLICATE_FLAG_COLUMN", "Duplicate Flag"
        )
        or "Duplicate Flag",
        sync_duplicate_type_column=_read_env(
            "SHEET_SYNC_DUPLICATE_TYPE_COLUMN", "Duplicate Type"
        )
        or "Duplicate Type",
        sync_duplicate_of_column=_read_env(
            "SHEET_SYNC_DUPLICATE_OF_COLUMN", "Duplicate Of"
        )
        or "Duplicate Of",
        sync_duplicate_reason_column=_read_env(
            "SHEET_SYNC_DUPLICATE_REASON_COLUMN", "Duplicate Reason"
        )
        or "Duplicate Reason",
    )
