from services.google_sheets_client import lead_exists_in_rows, sheet_lead_exists


def test_google_sheet_duplicate_matches_domain() -> None:
    exists, reason = lead_exists_in_rows(
        {"company_name": "Fresh Finch Gym", "website_url": "https://freshfinchgym.com/contact"},
        [{"company_name": "Fresh Finch Gym", "website_url": "http://www.freshfinchgym.com/"}],
    )

    assert exists is True
    assert "normalized_domain" in reason


def test_google_sheet_duplicate_matches_email() -> None:
    exists, reason = lead_exists_in_rows(
        {"company_name": "Different Name", "contact_email": "HELLO@ACME-STUDIO.COM"},
        [{"company_name": "Acme Studio", "contact_email": "hello@acme-studio.com"}],
    )

    assert exists is True
    assert "contact_email" in reason


def test_google_sheet_duplicate_matches_company_when_domain_and_email_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.google_sheets_client.read_existing_sheet_leads",
        lambda: [{"company_name": "Oak Sparrow Dental", "website_url": "", "contact_email": ""}],
    )

    exists, reason = sheet_lead_exists({"company_name": "Oak Sparrow Dental"})

    assert exists is True
    assert "company_name" in reason

