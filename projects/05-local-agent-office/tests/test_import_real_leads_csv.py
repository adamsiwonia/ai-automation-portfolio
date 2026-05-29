import csv

from fastapi.testclient import TestClient

from app import app
from scripts.import_real_leads_csv import import_real_leads_csv
from services import database
from services.project035_csv_export import export_approved_leads
from tests.workspace_tmp import workspace_tmp_dir


def test_imports_real_lead_as_review(monkeypatch) -> None:
    with workspace_tmp_dir("real-import") as tmp_dir:
        _use_test_db(monkeypatch, tmp_dir)
        csv_path = _write_import_csv(
            tmp_dir,
            [
                {
                    "company": "Atlas Dental",
                    "email": "Hello@AtlasDental.example",
                    "domain": "www.atlasdental.example",
                    "website_url": "",
                    "niche": "local dentists",
                    "source": "Chamber Directory",
                    "notes": "Family-owned clinic with online booking.",
                }
            ],
        )

        result = import_real_leads_csv(csv_path)

        assert result["imported_count"] == 1
        lead = database.get_lead(result["imported_ids"][0])
        assert lead["company_name"] == "Atlas Dental"
        assert lead["contact_email"] == "hello@atlasdental.example"
        assert lead["normalized_domain"] == "atlasdental.example"
        assert lead["status"] == "REVIEW"
        assert lead["source"] == "Chamber Directory"
        assert lead["lead_source_mode"] == "manual"


def test_duplicate_real_lead_is_skipped(monkeypatch) -> None:
    with workspace_tmp_dir("real-import-dupe") as tmp_dir:
        _use_test_db(monkeypatch, tmp_dir)
        csv_path = _write_import_csv(
            tmp_dir,
            [
                {
                    "company": "Atlas Dental",
                    "email": "hello@atlasdental.example",
                    "domain": "atlasdental.example",
                    "website_url": "",
                    "niche": "local dentists",
                    "source": "",
                    "notes": "First row.",
                },
                {
                    "company": "Atlas Dental Duplicate",
                    "email": "HELLO@ATLASDENTAL.EXAMPLE",
                    "domain": "https://www.atlasdental.example/contact",
                    "website_url": "",
                    "niche": "local dentists",
                    "source": "Referral",
                    "notes": "Duplicate row.",
                },
            ],
        )

        result = import_real_leads_csv(csv_path)

        assert result["imported_count"] == 1
        assert result["skipped_duplicate_count"] == 1
        assert "matched lead" in result["skipped_duplicates"][0]["reason"]
        assert len(database.get_latest_leads(limit=10)) == 1


def test_imported_real_lead_can_be_approved(monkeypatch) -> None:
    with workspace_tmp_dir("real-import-approve") as tmp_dir:
        _use_test_db(monkeypatch, tmp_dir)
        csv_path = _write_import_csv(
            tmp_dir,
            [
                {
                    "company": "Harbor Accounting",
                    "email": "hello@harboraccounting.example",
                    "domain": "harboraccounting.example",
                    "website_url": "",
                    "niche": "local accountants",
                    "source": "",
                    "notes": "Independent accounting firm.",
                }
            ],
        )
        lead_id = import_real_leads_csv(csv_path)["imported_ids"][0]

        with TestClient(app) as client:
            response = client.post(f"/api/leads/{lead_id}/approve")

        assert response.status_code == 200
        lead = database.get_lead(lead_id)
        assert lead["status"] == "APPROVED_FOR_OUTREACH"
        assert lead["source"] == "MANUAL_CSV"
        assert lead["lead_source_mode"] == "manual"


def test_imported_real_lead_can_be_exported_to_project035(monkeypatch) -> None:
    with workspace_tmp_dir("real-import-export") as tmp_dir:
        _use_test_db(monkeypatch, tmp_dir)
        csv_path = _write_import_csv(
            tmp_dir,
            [
                {
                    "company": "Brightlane Therapy",
                    "email": "hello@brightlanetherapy.example",
                    "domain": "brightlanetherapy.example",
                    "website_url": "",
                    "niche": "local therapists",
                    "source": "Manual Research",
                    "notes": "Small practice with intake forms.",
                }
            ],
        )
        lead_id = import_real_leads_csv(csv_path)["imported_ids"][0]
        assert database.update_lead_status(lead_id, "APPROVED_FOR_OUTREACH") is True

        export_path = tmp_dir / "project035.csv"
        result = export_approved_leads(export_path)

        assert result["exported_count"] == 1
        assert result["skipped_mock_count"] == 0
        with export_path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        assert rows[0]["Company"] == "Brightlane Therapy"
        assert rows[0]["Email"] == "hello@brightlanetherapy.example"
        assert rows[0]["Segment"] == "local therapists"
        assert rows[0]["Lead Type"] == "Project 05"
        assert rows[0]["Assistant Status"] == "NEW"
        assert database.get_lead(lead_id)["exported_at"]


def _use_test_db(monkeypatch, tmp_dir) -> None:
    monkeypatch.setattr(database, "DATA_DIR", tmp_dir)
    monkeypatch.setattr(database, "DB_PATH", tmp_dir / "test.sqlite")
    database.init_db()


def _write_import_csv(tmp_dir, rows: list[dict[str, str]]):
    path = tmp_dir / "real_leads.csv"
    fieldnames = ["company", "email", "domain", "website_url", "niche", "source", "notes"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path
