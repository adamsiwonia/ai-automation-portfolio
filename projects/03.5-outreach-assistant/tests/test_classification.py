from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import LeadClassification
from app.services.classification import classify_lead


def test_done_when_response_exists() -> None:
    classification, _ = classify_lead(
        source_status="",
        human_response="Thanks, we already handled this",
        email="hello@example.com",
        contact_form_url=None,
        malformed_contact_value=None,
        last_contacted_at="2026-03-10",
        follow_up_due_at="2026-03-20",
    )
    assert classification == LeadClassification.DONE


def test_contact_form_review_when_email_field_contains_url() -> None:
    classification, _ = classify_lead(
        source_status="",
        human_response="",
        email=None,
        contact_form_url="https://example.com/contact",
        malformed_contact_value=None,
        last_contacted_at=None,
        follow_up_due_at=None,
    )
    assert classification == LeadClassification.CONTACT_FORM_REVIEW


def test_email_needs_review_when_malformed() -> None:
    classification, _ = classify_lead(
        source_status="",
        human_response="",
        email=None,
        contact_form_url=None,
        malformed_contact_value="john@@example..com",
        last_contacted_at=None,
        follow_up_due_at=None,
    )
    assert classification == LeadClassification.EMAIL_NEEDS_REVIEW


def test_first_touch_ready_when_date_sent_empty() -> None:
    classification, _ = classify_lead(
        source_status="",
        human_response="",
        email="hello@example.com",
        contact_form_url=None,
        malformed_contact_value=None,
        last_contacted_at=None,
        follow_up_due_at=None,
    )
    assert classification == LeadClassification.FIRST_TOUCH_READY


def test_follow_up_ready_when_follow_up_date_empty() -> None:
    classification, reason = classify_lead(
        source_status="",
        human_response="",
        email="hello@example.com",
        contact_form_url=None,
        malformed_contact_value=None,
        last_contacted_at="2026-03-10T09:00:00Z",
        follow_up_due_at="",
    )
    assert classification == LeadClassification.FOLLOW_UP_READY
    assert "empty manual Follow-up Date" in reason


def test_follow_up_ready_when_follow_up_date_is_today() -> None:
    now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    classification, reason = classify_lead(
        source_status="",
        human_response="",
        email="hello@example.com",
        contact_form_url=None,
        malformed_contact_value=None,
        last_contacted_at="2026-03-10T09:00:00Z",
        follow_up_due_at="2026-03-24",
        now=now,
    )
    assert classification == LeadClassification.FOLLOW_UP_READY
    assert "set to today" in reason


def test_follow_up_skipped_when_follow_up_date_in_past() -> None:
    now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    classification, reason = classify_lead(
        source_status="",
        human_response="",
        email="hello@example.com",
        contact_form_url=None,
        malformed_contact_value=None,
        last_contacted_at="2026-03-10T09:00:00Z",
        follow_up_due_at="2026-03-20",
        now=now,
    )
    assert classification == LeadClassification.FOLLOW_UP_SKIPPED
    assert "in the past" in reason


def test_done_when_follow_up_date_in_future() -> None:
    now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    classification, reason = classify_lead(
        source_status="",
        human_response="",
        email="hello@example.com",
        contact_form_url=None,
        malformed_contact_value=None,
        last_contacted_at="2026-03-10T09:00:00Z",
        follow_up_due_at="2026-03-30",
        now=now,
    )
    assert classification == LeadClassification.DONE
    assert "Waiting for manual Follow-up Date" in reason
