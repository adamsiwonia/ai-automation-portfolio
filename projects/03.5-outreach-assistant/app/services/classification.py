from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import LeadClassification

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo:
            return dt.astimezone(timezone.utc)
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            date_only = datetime.strptime(value, "%Y-%m-%d")
            return date_only.replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def classify_lead(
    *,
    source_status: str | None,
    human_response: str | None,
    email: str | None,
    contact_form_url: str | None,
    malformed_contact_value: str | None,
    last_contacted_at: str | None,
    follow_up_due_at: str | None,
    now: datetime | None = None,
) -> tuple[LeadClassification, str]:
    current_time = now or datetime.now(timezone.utc)

    if human_response and human_response.strip():
        return LeadClassification.DONE, "Lead has a response."

    if contact_form_url:
        return (
            LeadClassification.CONTACT_FORM_REVIEW,
            "Email field contains a URL/contact form.",
        )

    if malformed_contact_value:
        return LeadClassification.EMAIL_NEEDS_REVIEW, "Email value is malformed."

    if not email:
        return LeadClassification.EMAIL_NEEDS_REVIEW, "No valid email found."

    last_contacted = _parse_dt(last_contacted_at)
    if not last_contacted:
        return LeadClassification.FIRST_TOUCH_READY, "Date Sent is empty."

    follow_up_raw = (follow_up_due_at or "").strip()
    if not follow_up_raw:
        return (
            LeadClassification.FOLLOW_UP_READY,
            "Follow-up triggered by empty manual Follow-up Date.",
        )

    follow_up_due = _parse_dt(follow_up_due_at)
    if not follow_up_due:
        return (
            LeadClassification.DONE,
            "Manual Follow-up Date is invalid or unrecognized.",
        )

    if follow_up_due.date() == current_time.date():
        return (
            LeadClassification.FOLLOW_UP_READY,
            "Follow-up triggered by manual Follow-up Date set to today.",
        )
    if follow_up_due.date() < current_time.date():
        return (
            LeadClassification.FOLLOW_UP_SKIPPED,
            "Follow-up skipped because manual Follow-up Date is in the past.",
        )
    return LeadClassification.DONE, "Waiting for manual Follow-up Date."
