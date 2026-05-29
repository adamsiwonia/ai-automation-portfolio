import csv

from services import database
from services.project035_csv_export import PROJECT035_HEADERS, export_approved_leads
from scripts.export_project035_csv import main as export_cli_main
from tests.workspace_tmp import workspace_tmp_dir


def test_project035_csv_export_headers_mapping_and_exported_at(monkeypatch) -> None:
    with workspace_tmp_dir("project035-export") as tmp_dir:
        monkeypatch.setattr(database, "DATA_DIR", tmp_dir)
        monkeypatch.setattr(database, "DB_PATH", tmp_dir / "test.sqlite")
        database.init_db()

        approved_id = database.insert_lead(
            {
                "company_name": "Atlas Dental",
                "website_url": "https://atlasdental.example",
                "contact_email": "hello@atlasdental.example",
                "niche": "local dentists",
                "score": 9,
                "status": "APPROVED_FOR_OUTREACH",
                "reason": "Strong fit for booking automation.",
                "recommended_angle": "Reduce missed booking follow-ups.",
                "personal_note": "Mentions patient intake forms.",
                "source": "SEARCH",
            }
        )
        database.insert_lead(
            {
                "company_name": "Not Approved",
                "contact_email": "hello@notapproved.example",
                "niche": "local dentists",
                "score": 8,
                "status": "QUALIFIED",
            }
        )

        export_path = tmp_dir / "project035_approved_leads.csv"
        result = export_approved_leads(export_path)

        assert result["exported_count"] == 1
        with export_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            rows = list(reader)

        assert reader.fieldnames == PROJECT035_HEADERS
        assert len(rows) == 1
        row = rows[0]
        assert row["Company"] == "Atlas Dental"
        assert row["Email"] == "hello@atlasdental.example"
        assert row["Segment"] == "local dentists"
        assert row["Lead Type"] == "Project 05"
        assert row["Assistant Status"] == "NEW"
        assert row["Selected Contact"] == "hello@atlasdental.example"
        assert row["Personalization Note"] == "Reduce missed booking follow-ups. | Mentions patient intake forms."
        assert row["Notes"] == "Score: 9 | Reason: Strong fit for booking automation."
        assert row["Duplicate Flag"] == "FALSE"
        assert row["Gmail Draft Status"] == "NOT_CREATED"

        for blank_column in [
            "Date Sent",
            "Follow up Date",
            "Response",
            "Draft Type",
            "Draft Subject",
            "Draft Body",
            "Last Processed At",
            "Error Flag",
            "Duplicate Type",
            "Duplicate Reason",
            "Duplicate Of",
        ]:
            assert row[blank_column] == ""

        exported_lead = database.get_lead(approved_id)
        assert exported_lead["exported_at"]
        assert exported_lead["status"] == "APPROVED_FOR_OUTREACH"

        second_result = export_approved_leads(tmp_dir / "second.csv")
        assert second_result["exported_count"] == 0


def test_project035_csv_export_skips_mock_leads_by_default(monkeypatch) -> None:
    with workspace_tmp_dir("project035-mock-skip") as tmp_dir:
        monkeypatch.setattr(database, "DATA_DIR", tmp_dir)
        monkeypatch.setattr(database, "DB_PATH", tmp_dir / "test.sqlite")
        database.init_db()

        mock_id = database.insert_lead(
            {
                "company_name": "Northstar Demo Studio",
                "website_url": "https://northstar-demo.example/about",
                "contact_email": "hello@northstar-demo.example",
                "niche": "demo niche",
                "score": 9,
                "status": "APPROVED_FOR_OUTREACH",
                "source": "MOCK",
                "lead_source_mode": "mock",
            }
        )

        export_path = tmp_dir / "default.csv"
        result = export_approved_leads(export_path)

        assert result["exported_count"] == 0
        assert result["skipped_mock_count"] == 1
        with export_path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        assert rows == []
        assert database.get_lead(mock_id)["exported_at"] in {None, ""}
        assert any(log["event"] == "project035_csv_mock_skipped" for log in database.get_recent_logs(limit=10))


def test_project035_csv_export_include_mock_flag_allows_mock_export(monkeypatch, capsys) -> None:
    with workspace_tmp_dir("project035-include-mock") as tmp_dir:
        monkeypatch.setattr(database, "DATA_DIR", tmp_dir)
        monkeypatch.setattr(database, "DB_PATH", tmp_dir / "test.sqlite")
        database.init_db()

        mock_id = database.insert_lead(
            {
                "company_name": "Brightlane Demo",
                "website_url": "https://brightlane-demo.example/about",
                "contact_email": "hello@brightlane-demo.example",
                "niche": "demo niche",
                "score": 8,
                "status": "APPROVED_FOR_OUTREACH",
                "source": "MOCK",
                "lead_source_mode": "mock",
            }
        )

        export_path = tmp_dir / "include_mock.csv"
        exit_code = export_cli_main([str(export_path), "--include-mock"])
        output = capsys.readouterr().out

        assert exit_code == 0
        assert "Exported 1 lead(s)" in output
        assert "Included 1 mock/demo lead(s) because --include-mock was set." in output
        with export_path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        assert len(rows) == 1
        assert rows[0]["Company"] == "Brightlane Demo"
        assert database.get_lead(mock_id)["exported_at"]
