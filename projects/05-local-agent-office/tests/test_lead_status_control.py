from fastapi.testclient import TestClient

from app import app
from services import database
from tests.workspace_tmp import workspace_tmp_dir


def test_update_lead_status_approves_and_rejects_locally(monkeypatch) -> None:
    with workspace_tmp_dir("lead-status") as tmp_dir:
        monkeypatch.setattr(database, "DATA_DIR", tmp_dir)
        monkeypatch.setattr(database, "DB_PATH", tmp_dir / "test.sqlite")
        database.init_db()

        lead_id = database.insert_lead(
            {
                "company_name": "Atlas Dental",
                "website_url": "https://atlasdental.example",
                "contact_email": "hello@atlasdental.example",
                "niche": "local dentists",
                "score": 8,
                "status": "QUALIFIED",
                "reason": "Good local fit.",
                "recommended_angle": "Reduce admin around bookings.",
                "personal_note": "Mentions appointment follow-up.",
                "source": "SEARCH",
            }
        )

        assert database.update_lead_status(lead_id, "APPROVED_FOR_OUTREACH") is True
        assert database.get_lead(lead_id)["status"] == "APPROVED_FOR_OUTREACH"

        assert database.update_lead_status(lead_id, "REJECTED", reason="Not a fit.") is True
        rejected = database.get_lead(lead_id)
        assert rejected["status"] == "REJECTED"
        assert rejected["reason"] == "Not a fit."


def test_api_blocks_mock_lead_approval(monkeypatch) -> None:
    with workspace_tmp_dir("mock-approval") as tmp_dir:
        monkeypatch.setattr(database, "DATA_DIR", tmp_dir)
        monkeypatch.setattr(database, "DB_PATH", tmp_dir / "test.sqlite")
        database.init_db()

        lead_id = database.insert_lead(
            {
                "company_name": "Northstar Demo Studio",
                "website_url": "https://northstar-demo.example/about",
                "contact_email": "hello@northstar-demo.example",
                "niche": "demo niche",
                "score": 9,
                "status": "QUALIFIED",
                "source": "MOCK",
                "lead_source_mode": "mock",
            }
        )

        with TestClient(app) as client:
            response = client.post(f"/api/leads/{lead_id}/approve")

        assert response.status_code == 400
        assert "Mock/demo leads cannot be approved" in response.json()["detail"]
        assert database.get_lead(lead_id)["status"] == "QUALIFIED"
        assert any(log["event"] == "mock_lead_approval_blocked" for log in database.get_recent_logs(limit=10))
