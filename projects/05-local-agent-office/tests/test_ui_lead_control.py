from fastapi.testclient import TestClient

from app import app


def test_homepage_exposes_lead_control_panel_and_actions() -> None:
    with TestClient(app) as client:
        html = client.get("/").text
        js = client.get("/static/app.js").text

    assert 'data-tab-target="tab-dashboard"' in html
    assert 'data-tab-target="tab-lead-control"' in html
    assert 'data-tab-target="tab-logs"' in html
    assert 'aria-controls="tab-dashboard"' in html
    assert 'aria-selected="true"' in html
    assert html.count('aria-selected="false"') == 2
    assert 'id="tab-dashboard"' in html
    assert 'id="tab-lead-control"' in html
    assert 'id="tab-logs"' in html
    assert 'data-tab-panel="tab-dashboard"' in html
    assert 'data-tab-panel="tab-lead-control"' in html
    assert 'data-tab-panel="tab-logs"' in html
    assert html.count('class="tab-panel active"') == 1
    assert html.count('class="tab-panel"') == 2
    assert html.count(" hidden") == 2
    assert "<h2>Lead Control</h2>" in html
    assert "<h2>Logs</h2>" in html
    assert 'id="dashboardLogs"' in html
    assert 'id="logs"' in html
    assert "<th>Company</th>" in html
    assert "<th>Reason / Recommended Angle</th>" in html
    assert "<th>Actions</th>" in html
    assert "DASHBOARD_LOG_LIMIT = 30" in js
    assert "api(`/api/logs?limit=${DASHBOARD_LOG_LIMIT}`)" in js
    assert "function initTabs()" in js
    assert 'button.addEventListener("click"' in js
    assert "activateTab(target)" in js
    assert "panel.hidden = !isActive" in js
    assert 'data-lead-action="approve"' in js
    assert 'data-lead-action="reject"' in js
    assert "function isMockLead" in js
    assert "MOCK_SOURCE_MARKERS" in js
    assert 'source-badge mock' in js
    assert "Mock only" in js
    assert "Mock leads cannot be approved for real outreach." in js
    assert "/api/leads/${leadId}/${action}" in js
    assert 'ACTIONABLE_LEAD_STATUSES = ["QUALIFIED", "REVIEW"]' in js
    assert "APPROVED_FOR_OUTREACH" in js
    assert "DRAFT_CREATED" in js
    assert "DONE" in js
    assert "lead.pre_filter_reason" not in js
