from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"


def fetch_text(path_or_url: str) -> str:
    url = path_or_url if path_or_url.startswith("http") else urllib.parse.urljoin(BASE_URL, path_or_url)
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8")


def fetch_json(path: str) -> dict:
    return json.loads(fetch_text(path))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    try:
        html = fetch_text("/")
    except urllib.error.URLError as exc:
        print(f"Could not reach {BASE_URL}. Start the app first with uvicorn app:app --host 127.0.0.1 --port 8765")
        print(exc)
        return 2

    script_match = re.search(r'<script src="([^"]+)"></script>', html)
    assert_true(script_match is not None, "No script tag found in homepage")
    script_src = script_match.group(1)
    js = fetch_text(script_src)

    status = fetch_json("/api/status")
    dashboard_logs = fetch_json("/api/logs?limit=30")
    full_logs = fetch_json("/api/logs?limit=500")
    leads = fetch_json("/api/leads")

    assert_true("id=\"debugPanel\"" in html, "Debug panel missing")
    assert_true("id=\"debugOutput\"" in html, "Debug output missing")
    assert_true("v=20260529-tabs-debug" in script_src, "Versioned JS cache-buster missing")
    assert_true('data-tab-target="tab-dashboard"' in html, "Dashboard tab button missing")
    assert_true('data-tab-target="tab-lead-control"' in html, "Lead Control tab button missing")
    assert_true('data-tab-target="tab-logs"' in html, "Logs tab button missing")
    assert_true('data-tab-panel="tab-dashboard"' in html, "Dashboard tab panel missing")
    assert_true('data-tab-panel="tab-lead-control"' in html, "Lead Control tab panel missing")
    assert_true('data-tab-panel="tab-logs"' in html, "Logs tab panel missing")
    assert_true("function initTabs()" in js, "initTabs missing from JS")
    assert_true("debugLog(\"initTabs running\")" in js, "initTabs debug log missing")
    assert_true("panel.hidden = !isActive" in js, "Tab hidden toggle missing")
    assert_true("refreshStatus/data loading started" in js, "Data loading debug log missing")
    assert_true("/api/status" in js, "Frontend does not call /api/status")
    assert_true("DASHBOARD_LOG_LIMIT = 30" in js, "Dashboard log limit is not 30")
    assert_true(len(dashboard_logs.get("logs", [])) <= 30, "Dashboard logs endpoint returned more than 30 logs")
    assert_true(isinstance(full_logs.get("logs", []), list), "Full logs endpoint did not return logs list")
    assert_true(isinstance(leads.get("leads", []), list), "Leads endpoint did not return leads list")
    assert_true("counts" in status, "Status endpoint missing counts")

    actionable = [
        lead for lead in leads.get("leads", [])
        if str(lead.get("status", "")).upper() in {"QUALIFIED", "REVIEW"}
    ]

    print("Frontend runtime verification passed")
    print(f"Base URL: {BASE_URL}")
    print(f"Script: {script_src}")
    print(f"Status mode: {status.get('current_mode')}")
    print(f"Dashboard logs: {len(dashboard_logs.get('logs', []))}")
    print(f"Full logs: {len(full_logs.get('logs', []))}")
    print(f"Leads: {len(leads.get('leads', []))}")
    print(f"Actionable leads visible to UI: {len(actionable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

