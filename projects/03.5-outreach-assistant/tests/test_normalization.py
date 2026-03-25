from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.core.enums import ContactChannel
from app.services.normalization import (
    normalize_segment,
    normalize_sheet_row,
    parse_contact_value,
)


def _settings() -> Settings:
    return Settings(
        db_path=Path("test.sqlite"),
        google_credentials_path=None,
        google_spreadsheet_id=None,
        google_sheet_name="Leads",
        gmail_oauth_client_secrets_path=None,
        gmail_token_path=Path("token_gmail_test.json"),
        external_id_column="Lead ID",
        company_column="Company",
        website_column="Website",
        contact_name_column="",
        contact_value_column="Email",
        assistant_status_column="Assistant Status",
        response_column="Response",
        notes_column="Notes",
        segment_column="Segment",
        last_contacted_column="Date Sent",
        follow_up_due_column="Follow Up Date",
        sync_lead_type_column="Lead Type",
        sync_assistant_status_column="Assistant Status",
        sync_selected_contact_column="Selected Contact",
        sync_draft_type_column="Draft Type",
        sync_draft_subject_column="Draft Subject",
        sync_draft_body_column="Draft Body",
        sync_personalization_note_column="Personalization Note",
        sync_last_processed_at_column="Last Processed At",
        sync_error_flag_column="Error Flag",
        sync_gmail_marker_column="Gmail Draft Status",
        sync_duplicate_flag_column="Duplicate Flag",
        sync_duplicate_type_column="Duplicate Type",
        sync_duplicate_of_column="Duplicate Of",
        sync_duplicate_reason_column="Duplicate Reason",
    )


def test_parse_contact_value_valid_email() -> None:
    result = parse_contact_value("  Jane.Doe@Example.com ")
    assert result.email == "jane.doe@example.com"
    assert result.contact_form_url is None
    assert result.malformed_value is None
    assert result.channel == ContactChannel.EMAIL


def test_parse_contact_value_contact_form_url() -> None:
    result = parse_contact_value("www.example.com/contact")
    assert result.email is None
    assert result.contact_form_url == "https://www.example.com/contact"
    assert result.malformed_value is None
    assert result.channel == ContactChannel.CONTACT_FORM


def test_parse_contact_value_malformed_email() -> None:
    result = parse_contact_value("john@@example..com")
    assert result.email is None
    assert result.contact_form_url is None
    assert result.malformed_value == "john@@example..com"
    assert result.channel == ContactChannel.MALFORMED


def test_normalize_sheet_row_uses_column_mapping() -> None:
    row = {
        "Lead ID": "L-100",
        "Company": "Northwind",
        "Website": "northwind.com",
        "Email": "alex@northwind.com",
        "Assistant Status": "new",
        "Response": "",
        "Notes": "Interested in outbound automation",
        "Segment": "Ecommerce",
        "Date Sent": "",
        "Follow Up Date": "",
    }
    normalized = normalize_sheet_row(
        row,
        settings=_settings(),
        source_sheet="Leads",
        source_row_number=2,
    )
    assert normalized.external_id == "L-100"
    assert normalized.company_name == "Northwind"
    assert normalized.website == "https://northwind.com"
    assert normalized.contact_name is None
    assert normalized.email == "alex@northwind.com"
    assert normalized.segment == "other"
    assert normalized.contact_channel == ContactChannel.EMAIL.value


def test_normalize_segment_common_dirty_values() -> None:
    assert normalize_segment("Outdor") == "outdoor_shop"
    assert normalize_segment("outdoor") == "outdoor_shop"
    assert normalize_segment("car parts") == "car_parts"
    assert normalize_segment("workshop") == "workshop"


def test_normalize_segment_unknown_to_other() -> None:
    assert normalize_segment("Ecommerce") == "other"
    assert normalize_segment("   ") == "other"


def test_normalize_sheet_row_company_falls_back_to_firma() -> None:
    row = {
        "Firma": "Legacy Company Header",
        "Email": "alex@legacy.example",
        "Assistant Status": "",
        "Response": "",
        "Notes": "",
        "Segment": "",
        "Date Sent": "",
        "Follow-up Date": "",
    }
    normalized = normalize_sheet_row(
        row,
        settings=_settings(),
        source_sheet="Leads",
        source_row_number=2,
    )
    assert normalized.company_name == "Legacy Company Header"
