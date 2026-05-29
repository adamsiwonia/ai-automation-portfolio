from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from services import database
from services.deduplication import (
    normalize_company_name,
    normalize_domain,
    normalize_email,
    normalize_website_url,
)
from services.settings import env_bool, load_config, minimum_qualification_score


BASE_DIR = Path(__file__).resolve().parents[1]


SHEET_COLUMNS = [
    "company_name",
    "website_url",
    "contact_email",
    "niche",
    "score",
    "status",
    "recommended_angle",
    "personal_note",
    "reason",
    "source_query",
    "source",
    "created_at",
]

_WARNED_KEYS: set[str] = set()


def _warn_once(key: str, message: str, details: dict[str, Any] | None = None) -> None:
    if key in _WARNED_KEYS:
        return
    database.add_log(
        "WARNING",
        message,
        task="sheets_writer",
        event="google_sheets_warning",
        details=details or {},
    )
    _WARNED_KEYS.add(key)


def _sheet_settings() -> dict[str, Any]:
    load_dotenv(BASE_DIR / ".env")
    config = load_config().get("google_sheets", {})
    return {
        "write_enabled": env_bool(os.getenv("GOOGLE_SHEETS_WRITE_ENABLED")) or bool(config.get("write_enabled")),
        "credentials": os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
        "spreadsheet_id": os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") or config.get("spreadsheet_id", ""),
        "worksheet_name": os.getenv("GOOGLE_SHEETS_WORKSHEET_NAME") or config.get("worksheet_name", "Leads"),
    }


def _is_configured_for_read(settings: dict[str, Any]) -> bool:
    return bool(settings.get("credentials") and settings.get("spreadsheet_id"))


def _get_sheets_service(settings: dict[str, Any]) -> Any | None:
    if not _is_configured_for_read(settings):
        _warn_once(
            "missing_google_config",
            "Google Sheets credentials or spreadsheet ID missing; continuing in local-only mode.",
            {"spreadsheet_id_present": bool(settings.get("spreadsheet_id"))},
        )
        return None

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        _warn_once(
            "missing_google_libraries",
            "Google Sheets libraries are not installed; continuing in local-only mode.",
        )
        return None

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(str(settings["credentials"]), scopes=scopes)
    return build("sheets", "v4", credentials=creds)


def prepare_row(lead: dict) -> list[Any]:
    return [lead.get(column, "") for column in SHEET_COLUMNS]


def prepare_rows(leads: list[dict]) -> list[list[Any]]:
    return [prepare_row(lead) for lead in leads]


def read_existing_sheet_leads() -> list[dict]:
    settings = _sheet_settings()
    service = _get_sheets_service(settings)
    if service is None:
        return []

    range_name = f"{settings['worksheet_name']}!A:L"
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=settings["spreadsheet_id"], range=range_name)
            .execute()
        )
    except Exception as exc:
        database.add_log(
            "WARNING",
            f"Could not read Google Sheet; continuing with local-only dedupe. {exc}",
            task="sheets_writer",
            event="google_sheets_read_failed",
        )
        return []

    values = result.get("values", [])
    if not values:
        return []

    header = [str(cell).strip() for cell in values[0]]
    first_header = header[0].lower().replace("_", " ").replace("-", " ").strip() if header else ""
    has_header = first_header in {"company name", "company"}
    columns = header if has_header else SHEET_COLUMNS
    data_rows = values[1:] if has_header else values

    leads: list[dict] = []
    for row in data_rows:
        item = {column: row[index] if index < len(row) else "" for index, column in enumerate(columns)}
        leads.append(item)
    return leads


def sheet_lead_exists(lead: dict) -> tuple[bool, str]:
    return lead_exists_in_rows(lead, read_existing_sheet_leads())


def lead_exists_in_rows(lead: dict, rows: list[dict]) -> tuple[bool, str]:
    target_domain = normalize_domain(lead.get("normalized_domain") or lead.get("website_url"))
    target_url = normalize_website_url(lead.get("website_url"))
    target_email = normalize_email(lead.get("contact_email"))
    target_company = normalize_company_name(lead.get("company_name"))

    for index, row in enumerate(rows, start=1):
        row_domain = normalize_domain(row.get("normalized_domain") or row.get("website_url"))
        row_url = normalize_website_url(row.get("website_url"))
        row_email = normalize_email(row.get("contact_email"))
        row_company = normalize_company_name(row.get("company_name"))

        if target_domain and row_domain and target_domain == row_domain:
            return True, f"Google Sheet row {index}: normalized_domain matched {target_domain}"
        if target_url and row_url and target_url == row_url:
            return True, f"Google Sheet row {index}: normalized website_url matched {target_url}"
        if target_email and row_email and target_email == row_email:
            return True, f"Google Sheet row {index}: normalized contact_email matched {target_email}"
        if target_company and row_company and not any([target_domain, target_email, row_domain, row_email]):
            if target_company == row_company:
                return True, f"Google Sheet row {index}: company_name matched {target_company}"

    return False, ""


def append_qualified_lead(lead: dict) -> bool:
    minimum_score = minimum_qualification_score()
    if str(lead.get("status", "")).upper() != "QUALIFIED":
        database.add_log(
            "SKIPPED",
            "Lead was not appended to Google Sheets because it is not QUALIFIED.",
            task="sheets_writer",
            event="sheet_append_skipped",
            company_name=lead.get("company_name"),
            details={"status": lead.get("status")},
        )
        return False

    try:
        score = int(lead.get("score") or 0)
    except (TypeError, ValueError):
        score = 0
    if score < minimum_score:
        database.add_log(
            "SKIPPED",
            f"Lead score {score} is below the minimum Google Sheets score {minimum_score}.",
            task="sheets_writer",
            event="sheet_append_skipped",
            company_name=lead.get("company_name"),
            details={"score": score, "minimum_score": minimum_score},
        )
        return False

    settings = _sheet_settings()
    if not settings.get("write_enabled"):
        _warn_once(
            "google_writes_disabled",
            "Google Sheets writing is disabled; qualified leads remain local-only.",
            {"minimum_score": minimum_score},
        )
        return False

    service = _get_sheets_service(settings)
    if service is None:
        return False

    row = prepare_row(lead)
    try:
        service.spreadsheets().values().append(
            spreadsheetId=settings["spreadsheet_id"],
            range=f"{settings['worksheet_name']}!A:L",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
    except Exception as exc:
        database.add_log(
            "ERROR",
            f"Could not append lead to Google Sheets: {exc}",
            task="sheets_writer",
            event="sheet_append_failed",
            company_name=lead.get("company_name"),
        )
        return False

    database.add_log(
        "SUCCESS",
        "Qualified lead appended to Google Sheets.",
        task="sheets_writer",
        event="sheet_append_success",
        company_name=lead.get("company_name"),
        details={"score": score, "minimum_score": minimum_score},
    )
    return True


def write_leads_to_google_sheets(leads: list[dict]) -> int:
    written = 0
    for lead in leads:
        if append_qualified_lead(lead):
            written += 1
    return written
