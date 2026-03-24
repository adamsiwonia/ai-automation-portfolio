from __future__ import annotations

from app.core.enums import LeadClassification
from app.services.drafting import build_display_name, build_outreach_draft

FIRST_TOUCH_EXPECTED_BODY = (
    "Hi,\n\n"
    "Thought this might be relevant.\n\n"
    "I built a simple tool that helps online stores save time on repetitive customer emails by preparing ready-to-review draft replies for things like delivery, returns, compatibility, and product questions.\n\n"
    "Everything stays human-reviewed — it just reduces the time spent on the same messages over and over.\n\n"
    "If you’d like, I can send a short web demo so you can see how it works.\n\n"
    "Best,\n"
    "Adam"
)
FOLLOW_UP_EXPECTED_BODY = (
    "Hi,\n\n"
    "Just following up in case my previous email got buried.\n\n"
    "I built a simple tool that helps online stores save time on repetitive customer emails by preparing ready-to-review draft replies for things like delivery, returns, compatibility, and product questions.\n\n"
    "If you’d like, I can send a short web demo so you can see how it works.\n\n"
    "Best,\n"
    "Adam"
)


def test_build_display_name_rejects_dirty_values() -> None:
    assert build_display_name("Unknown Company") is None
    assert build_display_name("info@example.com") is None
    assert build_display_name("https://example.com/contact") is None
    assert build_display_name("221B Baker Street, London, NW1 6XE") is None


def test_first_touch_subject_is_neutral() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FIRST_TOUCH_READY,
        company_name="info@example.com",
        contact_name="",
        segment="Retail",
        notes="",
    )
    assert draft is not None
    assert draft.subject in {
        "Quick question about customer emails",
        "Quick question about repetitive customer enquiries",
    }


def test_follow_up_subject_is_neutral() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FOLLOW_UP_READY,
        company_name="https://example.com",
        contact_name="",
        segment="Retail",
        notes="",
    )
    assert draft is not None
    assert draft.subject in {
        "Following up on my previous email",
        "Quick follow-up",
    }


def test_first_touch_body_matches_exact_template() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FIRST_TOUCH_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
    )
    assert draft is not None
    assert draft.body == FIRST_TOUCH_EXPECTED_BODY


def test_follow_up_body_matches_exact_template() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FOLLOW_UP_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
    )
    assert draft is not None
    assert draft.body == FOLLOW_UP_EXPECTED_BODY
