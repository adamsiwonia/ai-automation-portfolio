from __future__ import annotations

import html
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.database.db import fetch_logs, fetch_recent_support_metrics, fetch_runtime_status
from app.services.mailboxes import (
    DEFAULT_PROCESSED_LABEL,
    DEFAULT_SKIPPED_LABEL,
    GmailMailboxRecord,
    fetch_gmail_mailbox_counts,
    list_gmail_mailboxes,
    set_gmail_mailbox_active,
)

router = APIRouter(prefix="/admin", include_in_schema=False)

ADMIN_COOKIE_NAME = "admin_api_key"
ADMIN_SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
RECENT_LOG_WINDOW_HOURS = 24
MAILBOX_LIST_LIMIT = 250
ADMIN_LOGS_LIMIT_DEFAULT = 100
WORKER_COMPONENT_NAME = "worker"
WORKER_RUNNING_AFTER_SECONDS = 90
WORKER_STALE_AFTER_SECONDS = 300
PROCESSING_ACTIVE_WINDOW_SECONDS = 60 * 60
PROCESSING_LOW_ACTIVITY_WINDOW_SECONDS = 24 * 60 * 60
DASHBOARD_ACTIVITY_LIMIT = 10
DASHBOARD_ACTIVITY_HOURS = 24

ADMIN_CSS = """
:root {
  --bg: #eef2f9;
  --panel: #ffffff;
  --panel-soft: #f7f9fc;
  --line: #d7dfeb;
  --ink: #162236;
  --muted: #5e6b81;
  --brand: #1d4ed8;
  --brand-soft: #e6efff;
  --success: #15803d;
  --danger: #b91c1c;
  --warning: #b45309;
  --radius-lg: 14px;
  --radius-md: 10px;
  --shadow: 0 10px 30px rgba(17, 24, 39, 0.08);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: "Manrope", "Segoe UI", "Helvetica Neue", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(circle at 0% 0%, #dde9ff 0%, transparent 38%),
    radial-gradient(circle at 95% 100%, #d8f3e9 0%, transparent 40%),
    var(--bg);
}

a { color: inherit; text-decoration: none; }

.app-shell {
  max-width: 1180px;
  margin: 26px auto 40px;
  padding: 0 16px;
}

.topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}

.topbar h1 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.02em;
}

.topbar .meta {
  color: var(--muted);
  font-size: 13px;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.nav-link {
  padding: 9px 12px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.8);
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

.nav-link.is-active {
  background: var(--brand-soft);
  color: #183b90;
  border-color: #bdd3ff;
}

.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
}

.card-header {
  padding: 16px 18px 0;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  letter-spacing: -0.01em;
}

.card-header p {
  margin: 6px 0 0;
  color: var(--muted);
  font-size: 13px;
}

.content {
  padding: 16px 18px 18px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.kpi {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-soft);
  padding: 12px;
}

.kpi-label {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.kpi-value {
  margin: 8px 0 0;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

thead th {
  text-align: left;
  font-size: 12px;
  color: var(--muted);
  font-weight: 700;
  border-bottom: 1px solid var(--line);
  padding: 11px 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

tbody td {
  border-bottom: 1px solid var(--line);
  padding: 11px 10px;
  font-size: 14px;
  vertical-align: middle;
}

tbody tr:last-child td { border-bottom: none; }

.text-muted {
  color: var(--muted);
}

.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  padding: 5px 9px;
  border: 1px solid var(--line);
  background: #f8fafc;
}

.badge-active {
  color: #166534;
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.badge-inactive {
  color: #9a3412;
  border-color: #fed7aa;
  background: #fff7ed;
}

.badge-ok {
  color: #166534;
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.badge-warn {
  color: #9a3412;
  border-color: #fed7aa;
  background: #fff7ed;
}

.btn {
  appearance: none;
  border: 1px solid var(--line);
  background: #ffffff;
  color: var(--ink);
  border-radius: 9px;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  padding: 9px 12px;
  cursor: pointer;
}

.btn-primary {
  border-color: #b8ceff;
  background: var(--brand-soft);
  color: #183b90;
}

.btn-success {
  border-color: #86efac;
  color: #166534;
  background: #f0fdf4;
}

.btn-danger {
  border-color: #fecaca;
  color: #991b1b;
  background: #fef2f2;
}

.btn-inline {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.flash {
  margin-bottom: 12px;
  border: 1px solid #bfdbfe;
  color: #1e3a8a;
  background: #eff6ff;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 700;
}

.flash.error {
  border-color: #fecaca;
  color: #991b1b;
  background: #fef2f2;
}

.empty {
  border: 1px dashed var(--line);
  border-radius: var(--radius-md);
  padding: 16px;
  color: var(--muted);
  background: #fcfdff;
}

.stack {
  display: grid;
  gap: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.input-group label {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 6px;
  font-weight: 700;
}

.input-group input,
.input-group select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 9px;
  padding: 10px 11px;
  font-size: 14px;
  background: #fff;
}

.input-group input:focus,
.input-group select:focus {
  outline: none;
  border-color: #7aa2ff;
  box-shadow: 0 0 0 4px rgba(29, 78, 216, 0.12);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: end;
  margin-bottom: 10px;
}

.toolbar .input-group {
  min-width: 170px;
}

.mono {
  font-family: Consolas, "Courier New", monospace;
  font-size: 12px;
  color: var(--muted);
}

.status-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.status-item {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-soft);
  padding: 12px;
}

.status-item h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.status-item p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.split {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

.login-shell {
  max-width: 560px;
  margin: 70px auto;
  padding: 0 16px;
}

.login-card {
  padding: 22px;
}

.login-card h1 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.02em;
}

.login-card p {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 14px;
}

.field {
  margin-top: 14px;
}

.field label {
  display: block;
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 7px;
}

.field input {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 9px;
  padding: 11px 12px;
  font-size: 14px;
  color: var(--ink);
  background: #ffffff;
}

.field input:focus {
  outline: none;
  border-color: #7aa2ff;
  box-shadow: 0 0 0 4px rgba(29, 78, 216, 0.12);
}

.login-actions {
  display: flex;
  gap: 9px;
  margin-top: 14px;
  align-items: center;
}

.footnote {
  margin-top: 12px;
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 980px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
  .status-grid {
    grid-template-columns: 1fr;
  }
}
"""


def _format_timestamp(raw_iso: str) -> str:
    raw = (raw_iso or "").strip()
    if not raw:
        return "-"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw


def _parse_iso_utc(raw_iso: str | None) -> datetime | None:
    raw = (raw_iso or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _format_relative_age_from_seconds(age_seconds: float | None) -> str:
    if age_seconds is None:
        return "-"
    if age_seconds < 0:
        age_seconds = 0

    total_seconds = int(age_seconds)
    if total_seconds < 60:
        return f"{total_seconds} seconds ago"
    if total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes} minutes ago"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours} hours ago"
    days = total_seconds // 86400
    return f"{days} days ago"


def _get_google_oauth_config_status() -> dict[str, bool]:
    has_client_id = bool((os.getenv("GOOGLE_CLIENT_ID") or "").strip())
    has_client_secret = bool((os.getenv("GOOGLE_CLIENT_SECRET") or "").strip())
    has_redirect_uri = bool((os.getenv("GOOGLE_REDIRECT_URI") or "").strip())
    configured = has_client_id and has_client_secret and has_redirect_uri
    return {
        "configured": configured,
        "has_client_id": has_client_id,
        "has_client_secret": has_client_secret,
        "has_redirect_uri": has_redirect_uri,
    }


def _build_worker_runtime_view(runtime_row: dict[str, Any] | None) -> dict[str, str]:
    if not runtime_row:
        return {
            "state": "unknown",
            "label": "Unknown",
            "last_heartbeat": "-",
            "last_heartbeat_relative": "-",
            "detail": "No worker heartbeat recorded yet.",
        }

    heartbeat_raw = str(runtime_row.get("last_heartbeat_at") or "").strip()
    heartbeat_dt = _parse_iso_utc(heartbeat_raw)
    status_detail = str(runtime_row.get("details") or "").strip()

    if not heartbeat_dt:
        return {
            "state": "unknown",
            "label": "Unknown",
            "last_heartbeat": heartbeat_raw or "-",
            "last_heartbeat_relative": "-",
            "detail": status_detail,
        }

    age_seconds = (datetime.now(timezone.utc) - heartbeat_dt).total_seconds()
    relative = _format_relative_age_from_seconds(age_seconds)
    if age_seconds <= WORKER_RUNNING_AFTER_SECONDS:
        return {
            "state": "running",
            "label": "Running",
            "last_heartbeat": _format_timestamp(heartbeat_dt.isoformat()),
            "last_heartbeat_relative": relative,
            "detail": (
                f"Heartbeat is recent ({relative})."
                if not status_detail
                else f"Heartbeat is recent ({relative}). {status_detail}."
            ),
        }

    if age_seconds <= WORKER_STALE_AFTER_SECONDS:
        return {
            "state": "slow",
            "label": "Slow",
            "last_heartbeat": _format_timestamp(heartbeat_dt.isoformat()),
            "last_heartbeat_relative": relative,
            "detail": (
                f"Heartbeat is delayed ({relative})."
                if not status_detail
                else f"Heartbeat is delayed ({relative}). {status_detail}."
            ),
        }

    return {
        "state": "stale",
        "label": "Stale",
        "last_heartbeat": _format_timestamp(heartbeat_dt.isoformat()),
        "last_heartbeat_relative": relative,
        "detail": (
            f"Worker has not reported recently ({relative})."
            if not status_detail
            else f"Worker has not reported recently ({relative}). {status_detail}."
        ),
    }


def _render_worker_status_badge(worker_view: dict[str, str]) -> str:
    state = worker_view.get("state")
    label = html.escape(worker_view.get("label") or "Unknown")
    if state == "running":
        return f'<span class="badge badge-ok">{label}</span>'
    if state == "slow":
        return f'<span class="badge badge-warn">{label}</span>'
    if state == "stale":
        return f'<span class="badge badge-warn">{label}</span>'
    return f'<span class="badge badge-inactive">{label}</span>'


def _build_processing_status_view(
    *,
    worker_view: dict[str, str],
    oauth_configured: bool,
    last_success_activity: dict[str, Any] | None,
) -> dict[str, str]:
    worker_state = worker_view.get("state") or "unknown"
    if worker_state == "stale":
        stale_age = worker_view.get("last_heartbeat_relative") or "a while"
        return {
            "state": "STALE",
            "label": "Stale",
            "headline": f"Stale — worker has not reported in {stale_age}.",
            "detail": worker_view.get("detail") or "Worker heartbeat is stale.",
            "last_processed": "-",
        }

    if not oauth_configured:
        return {
            "state": "BLOCKED_BY_CONFIG",
            "label": "Blocked by Config",
            "headline": "Blocked — Google OAuth is not configured.",
            "detail": "Complete GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI.",
            "last_processed": "-",
        }

    last_success_dt = _parse_iso_utc(str((last_success_activity or {}).get("created_at") or ""))
    if last_success_dt:
        age_seconds = (datetime.now(timezone.utc) - last_success_dt).total_seconds()
        last_processed_display = (
            f"{_format_timestamp(last_success_dt.isoformat())} ({_format_relative_age_from_seconds(age_seconds)})"
        )
        if age_seconds <= PROCESSING_ACTIVE_WINDOW_SECONDS:
            return {
                "state": "ACTIVE",
                "label": "Active",
                "headline": f"Active — last processed {_format_relative_age_from_seconds(age_seconds)}.",
                "detail": "System is processing emails normally.",
                "last_processed": last_processed_display,
            }
        if age_seconds <= PROCESSING_LOW_ACTIVITY_WINDOW_SECONDS:
            return {
                "state": "LOW_ACTIVITY",
                "label": "Low Activity",
                "headline": f"Low activity — last processed {_format_relative_age_from_seconds(age_seconds)}.",
                "detail": "Processing happened recently, but not in the last hour.",
                "last_processed": last_processed_display,
            }

    return {
        "state": "NO_ACTIVITY",
        "label": "No Activity",
        "headline": "No recent activity — no emails processed in the last 24 hours.",
        "detail": "The system appears configured; inbox volume may be low.",
        "last_processed": "-",
    }


def _render_processing_status_badge(processing_view: dict[str, str]) -> str:
    state = processing_view.get("state")
    label = html.escape(processing_view.get("label") or "Unknown")
    if state in ("ACTIVE", "LOW_ACTIVITY"):
        return f'<span class="badge badge-ok">{label}</span>'
    if state in ("NO_ACTIVITY", "BLOCKED_BY_CONFIG", "STALE"):
        return f'<span class="badge badge-warn">{label}</span>'
    return f'<span class="badge badge-inactive">{label}</span>'


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    parts = authorization.strip().split()
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _resolve_admin_api_key(
    request: Request,
    *,
    x_api_key: str | None,
    authorization: str | None,
    explicit_api_key: str | None = None,
) -> str | None:
    values = [
        explicit_api_key,
        x_api_key,
        _extract_bearer_token(authorization),
        request.cookies.get(ADMIN_COOKIE_NAME),
    ]
    for value in values:
        normalized = (value or "").strip()
        if normalized:
            return normalized
    return None


def _get_expected_admin_api_key() -> str:
    configured = (os.getenv("ADMIN_API_KEY") or "").strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin panel is disabled because ADMIN_API_KEY is not configured.",
        )
    return configured


def _authenticate_admin_api_key(*, api_key: str) -> dict[str, Any]:
    expected = _get_expected_admin_api_key()
    if not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin API key")

    return {"name": "admin-panel", "mode": "admin-env"}


def _set_admin_cookie(response: RedirectResponse, request: Request, *, api_key: str) -> None:
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=api_key,
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def _clear_admin_cookie(response: HTMLResponse | RedirectResponse) -> None:
    response.delete_cookie(ADMIN_COOKIE_NAME, path="/")
    response.delete_cookie(ADMIN_COOKIE_NAME, path="/admin")


def _safe_client_name(client: dict[str, Any]) -> str:
    return str(client.get("name") or "unknown-client")


def require_admin_auth(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    api_key = _resolve_admin_api_key(
        request,
        x_api_key=x_api_key,
        authorization=authorization,
    )
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing admin API key")

    return _authenticate_admin_api_key(api_key=api_key)


def _render_status_badge(active: bool) -> str:
    if active:
        return '<span class="badge badge-active">Active</span>'
    return '<span class="badge badge-inactive">Inactive</span>'


def _render_layout(
    *,
    title: str,
    heading: str,
    subtitle: str,
    active_nav: str,
    client_name: str,
    body_html: str,
    notice: str | None = None,
    notice_error: bool = False,
) -> str:
    dashboard_class = "nav-link is-active" if active_nav == "dashboard" else "nav-link"
    mailboxes_class = "nav-link is-active" if active_nav == "mailboxes" else "nav-link"
    logs_class = "nav-link is-active" if active_nav == "logs" else "nav-link"
    health_class = "nav-link is-active" if active_nav == "health" else "nav-link"
    notice_html = ""
    if notice:
        escaped_notice = html.escape(notice)
        notice_class = "flash error" if notice_error else "flash"
        notice_html = f'<div class="{notice_class}">{escaped_notice}</div>'

    escaped_title = html.escape(title)
    escaped_heading = html.escape(heading)
    escaped_subtitle = html.escape(subtitle)
    escaped_client_name = html.escape(client_name)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escaped_title}</title>
  <style>{ADMIN_CSS}</style>
</head>
<body>
  <div class="app-shell">
    <div class="topbar">
      <div>
        <h1>{escaped_heading}</h1>
        <div class="meta">{escaped_subtitle}</div>
      </div>
      <div class="top-actions">
        <div class="meta">Signed in as <strong>{escaped_client_name}</strong></div>
        <form method="post" action="/admin/logout">
          <button class="btn btn-inline" type="submit">Log out</button>
        </form>
      </div>
    </div>

    <nav class="nav" aria-label="Admin navigation">
      <a class="{dashboard_class}" href="/admin/dashboard">Dashboard</a>
      <a class="{mailboxes_class}" href="/admin/mailboxes">Mailboxes</a>
      <a class="{logs_class}" href="/admin/logs">Logs</a>
      <a class="{health_class}" href="/admin/health">Health</a>
    </nav>

    {notice_html}
    {body_html}
  </div>
</body>
</html>
"""


def _render_login_page(error: str | None = None) -> str:
    error_html = ""
    if error:
        error_html = f'<div class="flash error">{html.escape(error)}</div>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Admin Login</title>
  <style>{ADMIN_CSS}</style>
</head>
<body>
  <div class="login-shell">
    <section class="card login-card">
      <h1>Support Agent Admin</h1>
      <p>Sign in with <code>ADMIN_API_KEY</code> to access mailbox management pages.</p>
      {error_html}

      <form method="post" action="/admin/login">
        <div class="field">
          <label for="api_key">API key</label>
          <input id="api_key" name="api_key" type="password" autocomplete="current-password" required />
        </div>
        <div class="login-actions">
          <button class="btn btn-primary" type="submit">Open Admin Panel</button>
        </div>
      </form>

      <p class="footnote">Admin panel access is intentionally separated from normal API endpoint keys.</p>
    </section>
  </div>
</body>
</html>
"""


def _render_dashboard_body(
    *,
    mailbox_counts: dict[str, int],
    recent_metrics: dict[str, int],
    latest_activity: list[dict[str, Any]],
    worker_view: dict[str, str],
    processing_view: dict[str, str],
) -> str:
    rows: list[str] = []
    for item in latest_activity:
        parse_badge = (
            '<span class="badge badge-ok">OK</span>'
            if int(item.get("parse_ok") or 0) == 1
            else '<span class="badge badge-warn">Fail</span>'
        )
        raw_subject = (item.get("subject") or "").strip()
        subject = raw_subject if raw_subject else "-"
        if len(subject) > 80:
            subject = f"{subject[:77]}..."

        rows.append(
            "<tr>"
            f"<td>{html.escape(_format_timestamp(str(item.get('created_at') or '')))}</td>"
            f"<td>{html.escape(str(item.get('source') or '-'))}</td>"
            f"<td>{html.escape(str(item.get('category') or '-'))}</td>"
            f"<td>{parse_badge}</td>"
            f"<td>{html.escape(subject)}</td>"
            "</tr>"
        )

    latest_rows_html = "".join(rows)
    if not latest_rows_html:
        latest_rows_html = (
            f'<tr><td colspan="5"><div class="empty">No processing activity in the last {DASHBOARD_ACTIVITY_HOURS} hours.</div></td></tr>'
        )

    total_mailboxes = int(mailbox_counts.get("total", 0))
    active_mailboxes = int(mailbox_counts.get("active", 0))
    inactive_mailboxes = int(mailbox_counts.get("inactive", 0))
    recent_logs = int(recent_metrics.get("recent_total", 0))
    recent_errors = int(recent_metrics.get("recent_errors", 0))

    return f"""
<section class="card split">
  <div class="card-header">
    <h2>Overview</h2>
    <p>Snapshot of mailbox connectivity and support activity in the last {RECENT_LOG_WINDOW_HOURS} hours.</p>
  </div>
  <div class="content">
    <div class="kpi-grid">
      <div class="kpi">
        <p class="kpi-label">Total Mailboxes</p>
        <p class="kpi-value">{total_mailboxes}</p>
      </div>
      <div class="kpi">
        <p class="kpi-label">Active Mailboxes</p>
        <p class="kpi-value">{active_mailboxes}</p>
      </div>
      <div class="kpi">
        <p class="kpi-label">Inactive Mailboxes</p>
        <p class="kpi-value">{inactive_mailboxes}</p>
      </div>
      <div class="kpi">
        <p class="kpi-label">Recent Support Logs</p>
        <p class="kpi-value">{recent_logs}</p>
      </div>
      <div class="kpi">
        <p class="kpi-label">Recent Errors</p>
        <p class="kpi-value">{recent_errors}</p>
      </div>
    </div>

    <div class="card" style="box-shadow:none; margin-bottom:12px;">
      <div class="card-header">
        <h2>Worker Liveness</h2>
        <p>Latest worker heartbeat from the polling loop.</p>
      </div>
      <div class="content">
        <p style="margin:0 0 8px;">
          {_render_worker_status_badge(worker_view)}
          <span class="text-muted" style="margin-left:8px;">Last heartbeat: {html.escape(worker_view.get("last_heartbeat") or "-")} ({html.escape(worker_view.get("last_heartbeat_relative") or "-")})</span>
        </p>
        <p class="text-muted" style="margin:0;">{html.escape(worker_view.get("detail") or "-")}</p>
        <p class="text-muted" style="margin:8px 0 0;">
          {_render_processing_status_badge(processing_view)}
          <span style="margin-left:8px;">{html.escape(processing_view.get("headline") or "-")}</span>
        </p>
      </div>
    </div>

    <div class="card" style="box-shadow:none;">
      <div class="card-header">
        <h2>Latest Processing Activity</h2>
        <p>Most recent support processing events.</p>
      </div>
      <div class="content table-wrap">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Source</th>
              <th>Category</th>
              <th>Parse</th>
              <th>Subject</th>
            </tr>
          </thead>
          <tbody>
            {latest_rows_html}
          </tbody>
        </table>
      </div>
    </div>

    <div style="margin-top:12px; display:flex; flex-wrap:wrap; gap:8px;">
      <a class="btn btn-primary btn-inline" href="/admin/mailboxes">Manage Mailboxes</a>
      <a class="btn btn-inline" href="/admin/logs">View Logs</a>
      <a class="btn btn-inline" href="/admin/health">System Health</a>
    </div>
  </div>
</section>
"""


def _render_mailboxes_body(mailboxes: list[GmailMailboxRecord], *, default_client_name: str) -> str:
    rows: list[str] = []
    for mailbox in mailboxes:
        action_path = (
            f"/admin/mailboxes/{mailbox.id}/deactivate"
            if mailbox.active
            else f"/admin/mailboxes/{mailbox.id}/activate"
        )
        action_label = "Deactivate" if mailbox.active else "Activate"
        action_class = "btn btn-danger btn-inline" if mailbox.active else "btn btn-success btn-inline"

        rows.append(
            "<tr>"
            f"<td>{html.escape(mailbox.mailbox_email)}</td>"
            f"<td>{html.escape(mailbox.client_name or '-')}</td>"
            f"<td>{_render_status_badge(mailbox.active)}</td>"
            f"<td><code>{html.escape(mailbox.processed_label)}</code></td>"
            f"<td><code>{html.escape(mailbox.skipped_label)}</code></td>"
            f"<td class=\"text-muted\">{html.escape(_format_timestamp(mailbox.updated_at))}</td>"
            "<td>"
            f"<form method=\"post\" action=\"{html.escape(action_path)}\">"
            f"<button class=\"{action_class}\" type=\"submit\">{action_label}</button>"
            "</form>"
            "</td>"
            "</tr>"
        )

    table_body = "".join(rows)
    if not table_body:
        table_body = '<tr><td colspan="7"><div class="empty">No mailbox connections found yet.</div></td></tr>'

    return f"""
<div class="stack">
  <section class="card">
    <div class="card-header">
      <h2>Connect Gmail</h2>
      <p>Start OAuth consent and connect a mailbox directly from the admin panel.</p>
    </div>
    <div class="content">
      <form method="get" action="/auth/google/start">
        <input type="hidden" name="redirect_to_google" value="1" />
        <input type="hidden" name="post_connect_redirect" value="/admin/mailboxes" />
        <div class="form-grid">
          <div class="input-group">
            <label for="connect-client-name">Client Name</label>
            <input id="connect-client-name" name="client_name" value="{html.escape(default_client_name)}" maxlength="200" />
          </div>
          <div class="input-group">
            <label for="connect-processed-label">Processed Label</label>
            <input id="connect-processed-label" name="processed_label" value="{html.escape(DEFAULT_PROCESSED_LABEL)}" maxlength="100" required />
          </div>
          <div class="input-group">
            <label for="connect-skipped-label">Skipped Label</label>
            <input id="connect-skipped-label" name="skipped_label" value="{html.escape(DEFAULT_SKIPPED_LABEL)}" maxlength="100" required />
          </div>
        </div>
        <button class="btn btn-primary btn-inline" type="submit">Connect Gmail</button>
      </form>
    </div>
  </section>

  <section class="card">
    <div class="card-header">
      <h2>Mailbox Connections</h2>
      <p>Manage active and paused mailbox processing. Mailboxes are never deleted from this view.</p>
    </div>
    <div class="content table-wrap">
      <table>
        <thead>
          <tr>
            <th>Mailbox Email</th>
            <th>Client Name</th>
            <th>Status</th>
            <th>Processed Label</th>
            <th>Skipped Label</th>
            <th>Updated</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {table_body}
        </tbody>
      </table>
    </div>
  </section>
</div>
"""


def _render_generic_status_badge(ok: bool, *, ok_text: str, warn_text: str) -> str:
    if ok:
        return f'<span class="badge badge-ok">{html.escape(ok_text)}</span>'
    return f'<span class="badge badge-warn">{html.escape(warn_text)}</span>'


def _build_logs_filter_created_after(hours: int) -> str:
    safe_hours = max(1, min(hours, 24 * 30))
    return (datetime.now(timezone.utc) - timedelta(hours=safe_hours)).isoformat()


def _derive_client_from_source(raw_source: str) -> str:
    source = (raw_source or "").strip()
    if not source:
        return "-"
    if source.startswith("gmail:") and len(source) > len("gmail:"):
        return source.split("gmail:", 1)[1]
    return "-"


def _render_logs_body(
    *,
    items: list[dict[str, Any]],
    limit: int,
    category: str | None,
    parse_ok: int | None,
    hours: int,
    window_has_any_logs: bool,
    filters_active: bool,
) -> str:
    selected_parse_ok = "" if parse_ok is None else str(parse_ok)
    selected_category = category or ""

    rows: list[str] = []
    for row in items:
        parse_flag = int(row.get("parse_ok") or 0)
        parse_badge = (
            '<span class="badge badge-ok">OK</span>'
            if parse_flag == 1
            else '<span class="badge badge-warn">Fail</span>'
        )
        error_message = (row.get("error_message") or "").strip()
        error_display = html.escape(error_message) if error_message else "-"
        rows.append(
            "<tr>"
            f"<td>{html.escape(_format_timestamp(str(row.get('created_at') or '')))}</td>"
            f"<td><span class=\"mono\">{html.escape(str(row.get('request_id') or '-'))}</span></td>"
            f"<td>{html.escape(str(row.get('source') or '-'))}</td>"
            f"<td>{html.escape(_derive_client_from_source(str(row.get('source') or '')))}</td>"
            f"<td>{html.escape(str(row.get('category') or '-'))}</td>"
            f"<td>{parse_badge}</td>"
            f"<td>{error_display}</td>"
            "</tr>"
        )

    table_body = "".join(rows)
    if not table_body:
        if not window_has_any_logs:
            empty_message = (
                f"No support logs were recorded in the last {hours} hours. "
                "This may mean the worker is idle or not running."
            )
        elif filters_active:
            empty_message = "No logs match the current category/parse filters. Try clearing one or both filters."
        else:
            empty_message = "No logs are available for this time window yet."
        table_body = f'<tr><td colspan="7"><div class="empty">{html.escape(empty_message)}</div></td></tr>'

    return f"""
<section class="card">
  <div class="card-header">
    <h2>Support Logs</h2>
    <p>Operational logs from support generation requests.</p>
  </div>
  <div class="content">
    <form class="toolbar" method="get" action="/admin/logs">
      <div class="input-group">
        <label for="logs-category">Category</label>
        <input id="logs-category" name="category" value="{html.escape(selected_category)}" placeholder="Optional" />
      </div>
      <div class="input-group">
        <label for="logs-parse-ok">Parse</label>
        <select id="logs-parse-ok" name="parse_ok">
          <option value=""{" selected" if selected_parse_ok == "" else ""}>All</option>
          <option value="1"{" selected" if selected_parse_ok == "1" else ""}>OK</option>
          <option value="0"{" selected" if selected_parse_ok == "0" else ""}>Fail</option>
        </select>
      </div>
      <div class="input-group">
        <label for="logs-hours">Hours</label>
        <input id="logs-hours" name="hours" type="number" min="1" max="720" value="{hours}" />
      </div>
      <div class="input-group">
        <label for="logs-limit">Limit</label>
        <input id="logs-limit" name="limit" type="number" min="1" max="500" value="{limit}" />
      </div>
      <button class="btn btn-primary btn-inline" type="submit">Apply Filters</button>
    </form>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Request ID</th>
            <th>Source</th>
            <th>Client</th>
            <th>Category</th>
            <th>Parse</th>
            <th>Error Message</th>
          </tr>
        </thead>
        <tbody>
          {table_body}
        </tbody>
      </table>
    </div>
  </div>
</section>
"""


def _render_health_body(
    *,
    mailbox_counts: dict[str, int],
    worker_view: dict[str, str],
    recent_metrics: dict[str, int],
    last_success_activity: dict[str, Any] | None,
) -> str:
    oauth_status = _get_google_oauth_config_status()
    oauth_configured = bool(oauth_status.get("configured"))
    oauth_client_id = bool(oauth_status.get("has_client_id"))
    oauth_client_secret = bool(oauth_status.get("has_client_secret"))
    oauth_redirect = bool(oauth_status.get("has_redirect_uri"))
    oauth_state_secret = bool((os.getenv("GOOGLE_OAUTH_STATE_SECRET") or "").strip())
    openai_key = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    auth_key_present = bool((os.getenv("DEMO_API_KEY") or os.getenv("API_KEY") or "").strip())
    auth_hmac_secret = bool((os.getenv("API_KEY_HMAC_SECRET") or "").strip())
    has_mailboxes = int(mailbox_counts.get("total", 0)) > 0

    recent_total = int(recent_metrics.get("recent_total", 0))
    recent_errors = int(recent_metrics.get("recent_errors", 0))
    processing_view = _build_processing_status_view(
        worker_view=worker_view,
        oauth_configured=oauth_configured,
        last_success_activity=last_success_activity,
    )

    if not oauth_configured:
        logs_badge = '<span class="badge badge-warn">Blocked by Config</span>'
        logs_message = "No activity — Gmail processing is not configured (OAuth incomplete)."
    elif recent_total > 0:
        logs_badge = '<span class="badge badge-ok">Active</span>'
        logs_message = "Processed requests were recorded in the last 24 hours."
    else:
        logs_badge = '<span class="badge badge-warn">No Activity</span>'
        logs_message = "No emails processed in the last 24 hours."

    return f"""
<div class="stack">
  <section class="card">
    <div class="card-header">
      <h2>Runtime Visibility</h2>
      <p>Quick signals that show whether the system is actively processing.</p>
    </div>
    <div class="content status-grid">
      <article class="status-item">
        <h3>Worker Status</h3>
        {_render_worker_status_badge(worker_view)}
        <p>Last heartbeat: {html.escape(worker_view.get("last_heartbeat") or "-")} ({html.escape(worker_view.get("last_heartbeat_relative") or "-")})</p>
        <p style="margin-top:8px;">{html.escape(worker_view.get("detail") or "-")}</p>
      </article>
      <article class="status-item">
        <h3>Last Successful Processing</h3>
        {_render_processing_status_badge(processing_view)}
        <p>{html.escape(processing_view.get("headline") or "-")}</p>
        <p style="margin-top:8px;">State: <strong>{html.escape(processing_view.get("state") or "UNKNOWN")}</strong></p>
        <p style="margin-top:8px;">Last processed: <strong>{html.escape(processing_view.get("last_processed") or "-")}</strong></p>
        <p style="margin-top:8px;">{html.escape(processing_view.get("detail") or "-")}</p>
      </article>
      <article class="status-item">
        <h3>Recent Support Logs (24h)</h3>
        {logs_badge}
        <p>Count: <strong>{recent_total}</strong></p>
        <p style="margin-top:8px;">{html.escape(logs_message)}</p>
      </article>
      <article class="status-item">
        <h3>Recent Errors (24h)</h3>
        {_render_generic_status_badge(recent_errors == 0, ok_text="No Errors", warn_text="Errors Present")}
        <p>Count: <strong>{recent_errors}</strong></p>
      </article>
    </div>
  </section>

  <section class="card">
    <div class="card-header">
      <h2>Configuration Checks</h2>
      <p>Lightweight operational checks. Secret values are never displayed.</p>
    </div>
    <div class="content status-grid">
      <article class="status-item">
        <h3>API Health</h3>
        {_render_generic_status_badge(True, ok_text="Healthy", warn_text="Unavailable")}
        <p>FastAPI process is running and rendering admin pages.</p>
      </article>
      <article class="status-item">
        <h3>Gmail Mailboxes</h3>
        {_render_generic_status_badge(has_mailboxes, ok_text="Available", warn_text="None Connected")}
        <p>Total connected mailboxes: <strong>{int(mailbox_counts.get("total", 0))}</strong></p>
      </article>
      <article class="status-item">
        <h3>Google OAuth Config</h3>
        {_render_generic_status_badge(oauth_configured, ok_text="Configured", warn_text="Incomplete")}
        <p>Requires client id, client secret, and redirect URI.</p>
      </article>
      <article class="status-item">
        <h3>OAuth State Secret</h3>
        {_render_generic_status_badge(oauth_state_secret, ok_text="Configured", warn_text="Using Client Secret Fallback")}
        <p>Optional explicit state-signing secret for callback validation.</p>
      </article>
      <article class="status-item">
        <h3>Support Model Config</h3>
        {_render_generic_status_badge(openai_key, ok_text="Configured", warn_text="Missing OPENAI_API_KEY")}
        <p>OpenAI key required for support reply generation.</p>
      </article>
      <article class="status-item">
        <h3>API Key Auth Config</h3>
        {_render_generic_status_badge(auth_key_present or auth_hmac_secret, ok_text="Configured", warn_text="Missing Auth Config")}
        <p>Supports env demo keys and DB/HMAC auth mode.</p>
      </article>
    </div>
  </section>
</div>
"""


@router.get("", response_class=HTMLResponse)
def admin_entry(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    try:
        _get_expected_admin_api_key()
    except HTTPException as exc:
        return HTMLResponse(_render_login_page(str(exc.detail)), status_code=exc.status_code)

    api_key = _resolve_admin_api_key(request, x_api_key=x_api_key, authorization=authorization)
    if not api_key:
        return HTMLResponse(_render_login_page())

    try:
        _authenticate_admin_api_key(api_key=api_key)
    except HTTPException as exc:
        response = HTMLResponse(_render_login_page(str(exc.detail)), status_code=exc.status_code)
        _clear_admin_cookie(response)
        return response

    response = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    _set_admin_cookie(response, request, api_key=api_key)
    return response


@router.get("/", response_class=HTMLResponse)
def admin_entry_slash(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    return admin_entry(request=request, x_api_key=x_api_key, authorization=authorization)


@router.post("/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    body_raw = await request.body()
    form_data = parse_qs(body_raw.decode("utf-8"), keep_blank_values=True)
    normalized_api_key = str((form_data.get("api_key") or [""])[0]).strip()
    if not normalized_api_key:
        return HTMLResponse(_render_login_page("API key is required."), status_code=400)

    try:
        _authenticate_admin_api_key(api_key=normalized_api_key)
    except HTTPException as exc:
        return HTMLResponse(_render_login_page(str(exc.detail)), status_code=exc.status_code)

    response = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    _set_admin_cookie(response, request, api_key=normalized_api_key)
    return response


@router.post("/logout")
def admin_logout():
    response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    _clear_admin_cookie(response)
    return response


@router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, client=Depends(require_admin_auth)):
    mailbox_counts = fetch_gmail_mailbox_counts()
    recent_metrics = fetch_recent_support_metrics(hours=RECENT_LOG_WINDOW_HOURS)
    latest_activity = fetch_logs(
        limit=DASHBOARD_ACTIVITY_LIMIT,
        created_after=_build_logs_filter_created_after(DASHBOARD_ACTIVITY_HOURS),
    )
    worker_runtime = fetch_runtime_status(WORKER_COMPONENT_NAME)
    worker_view = _build_worker_runtime_view(worker_runtime)
    oauth_status = _get_google_oauth_config_status()
    last_success_logs = fetch_logs(limit=1, parse_ok=1)
    last_success_activity = last_success_logs[0] if last_success_logs else None
    processing_view = _build_processing_status_view(
        worker_view=worker_view,
        oauth_configured=bool(oauth_status.get("configured")),
        last_success_activity=last_success_activity,
    )

    body_html = _render_dashboard_body(
        mailbox_counts=mailbox_counts,
        recent_metrics=recent_metrics,
        latest_activity=latest_activity,
        worker_view=worker_view,
        processing_view=processing_view,
    )

    page = _render_layout(
        title="Admin Dashboard",
        heading="Admin Dashboard",
        subtitle="Operational overview for mailbox processing",
        active_nav="dashboard",
        client_name=_safe_client_name(client),
        body_html=body_html,
    )
    return HTMLResponse(page)


@router.get("/mailboxes", response_class=HTMLResponse)
def admin_mailboxes(
    request: Request,
    notice: str | None = None,
    error: int = 0,
    client=Depends(require_admin_auth),
):
    mailboxes = list_gmail_mailboxes(limit=MAILBOX_LIST_LIMIT)
    body_html = _render_mailboxes_body(mailboxes, default_client_name=_safe_client_name(client))

    page = _render_layout(
        title="Admin Mailboxes",
        heading="Mailbox Management",
        subtitle="Activate or pause mailbox processing without deleting records",
        active_nav="mailboxes",
        client_name=_safe_client_name(client),
        body_html=body_html,
        notice=notice,
        notice_error=bool(error),
    )
    return HTMLResponse(page)


@router.get("/logs", response_class=HTMLResponse)
def admin_logs(
    request: Request,
    limit: int = ADMIN_LOGS_LIMIT_DEFAULT,
    parse_ok: str | None = None,
    category: str | None = None,
    hours: int = 24,
    client=Depends(require_admin_auth),
):
    normalized_limit = max(1, min(limit, 500))
    normalized_hours = max(1, min(hours, 24 * 30))
    normalized_parse_ok = int(parse_ok) if parse_ok in ("0", "1") else None
    normalized_category = (category or "").strip() or None
    created_after = _build_logs_filter_created_after(normalized_hours)

    logs = fetch_logs(
        limit=normalized_limit,
        parse_ok=normalized_parse_ok,
        category=normalized_category,
        created_after=created_after,
    )
    window_has_any_logs = bool(fetch_logs(limit=1, created_after=created_after))
    filters_active = normalized_parse_ok is not None or normalized_category is not None

    body_html = _render_logs_body(
        items=logs,
        limit=normalized_limit,
        category=normalized_category,
        parse_ok=normalized_parse_ok,
        hours=normalized_hours,
        window_has_any_logs=window_has_any_logs,
        filters_active=filters_active,
    )

    page = _render_layout(
        title="Admin Logs",
        heading="Logs",
        subtitle="Inspect recent support request outcomes",
        active_nav="logs",
        client_name=_safe_client_name(client),
        body_html=body_html,
    )
    return HTMLResponse(page)


@router.get("/health", response_class=HTMLResponse)
def admin_health(request: Request, client=Depends(require_admin_auth)):
    mailbox_counts = fetch_gmail_mailbox_counts()
    recent_metrics = fetch_recent_support_metrics(hours=RECENT_LOG_WINDOW_HOURS)
    worker_runtime = fetch_runtime_status(WORKER_COMPONENT_NAME)
    worker_view = _build_worker_runtime_view(worker_runtime)
    last_success_logs = fetch_logs(limit=1, parse_ok=1)
    last_success_activity = last_success_logs[0] if last_success_logs else None
    body_html = _render_health_body(
        mailbox_counts=mailbox_counts,
        worker_view=worker_view,
        recent_metrics=recent_metrics,
        last_success_activity=last_success_activity,
    )

    page = _render_layout(
        title="Admin Health",
        heading="System Health",
        subtitle="Lightweight configuration and runtime checks",
        active_nav="health",
        client_name=_safe_client_name(client),
        body_html=body_html,
    )
    return HTMLResponse(page)


@router.post("/mailboxes/{mailbox_id}/activate")
def admin_activate_mailbox(mailbox_id: int, request: Request, client=Depends(require_admin_auth)):
    try:
        updated = set_gmail_mailbox_active(mailbox_id=mailbox_id, active=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not updated:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    notice = quote_plus(f"Mailbox {mailbox_id} activated.")
    return RedirectResponse(
        url=f"/admin/mailboxes?notice={notice}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/mailboxes/{mailbox_id}/deactivate")
def admin_deactivate_mailbox(mailbox_id: int, request: Request, client=Depends(require_admin_auth)):
    try:
        updated = set_gmail_mailbox_active(mailbox_id=mailbox_id, active=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not updated:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    notice = quote_plus(f"Mailbox {mailbox_id} deactivated.")
    return RedirectResponse(
        url=f"/admin/mailboxes?notice={notice}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
