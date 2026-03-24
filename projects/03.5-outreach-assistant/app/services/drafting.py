from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.enums import LeadClassification

FIRST_TOUCH_SUBJECTS = (
    "Quick question about customer emails",
    "Quick question about repetitive customer enquiries",
)
FOLLOW_UP_SUBJECTS = (
    "Following up on my previous email",
    "Quick follow-up",
)
EMAIL_LIKE_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", re.IGNORECASE)
URL_LIKE_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
FIRST_TOUCH_BODY_TEMPLATE = (
    "Hi,\n\n"
    "Thought this might be relevant.\n\n"
    "I built a simple tool that helps online stores save time on repetitive customer emails by preparing ready-to-review draft replies for things like delivery, returns, compatibility, and product questions.\n\n"
    "Everything stays human-reviewed — it just reduces the time spent on the same messages over and over.\n\n"
    "If you’d like, I can send a short web demo so you can see how it works.\n\n"
    "Best,\n"
    "Adam"
)
FOLLOW_UP_BODY_TEMPLATE = (
    "Hi,\n\n"
    "Just following up in case my previous email got buried.\n\n"
    "I built a simple tool that helps online stores save time on repetitive customer emails by preparing ready-to-review draft replies for things like delivery, returns, compatibility, and product questions.\n\n"
    "If you’d like, I can send a short web demo so you can see how it works.\n\n"
    "Best,\n"
    "Adam"
)


@dataclass(frozen=True)
class DraftContent:
    subject: str
    body: str
    generator: str = "template-v1"


def build_display_name(company_name: str | None) -> str | None:
    raw = (company_name or "").strip()
    if not raw:
        return None

    cleaned = " ".join(raw.replace("\r", "\n").split())
    lowered = cleaned.lower()
    if not cleaned or lowered == "unknown company":
        return None

    if EMAIL_LIKE_RE.fullmatch(cleaned):
        return None
    if URL_LIKE_RE.search(cleaned):
        return None

    if ("\n" in raw and any(ch.isdigit() for ch in raw)) or (
        cleaned.count(",") >= 2 and any(ch.isdigit() for ch in cleaned)
    ):
        return None

    return cleaned


def _subject_for(classification: LeadClassification, seed_text: str | None) -> str:
    options = (
        FIRST_TOUCH_SUBJECTS
        if classification == LeadClassification.FIRST_TOUCH_READY
        else FOLLOW_UP_SUBJECTS
    )
    if not seed_text:
        return options[0]
    return options[sum(ord(ch) for ch in seed_text) % len(options)]


def build_outreach_draft(
    *,
    classification: LeadClassification,
    company_name: str,
    contact_name: str | None,
    segment: str | None,
    notes: str | None,
) -> DraftContent | None:
    display_name = build_display_name(company_name)
    _ = contact_name
    _ = notes

    if classification == LeadClassification.FIRST_TOUCH_READY:
        subject = _subject_for(classification, display_name or segment)
        return DraftContent(subject=subject, body=FIRST_TOUCH_BODY_TEMPLATE)

    if classification == LeadClassification.FOLLOW_UP_READY:
        subject = _subject_for(classification, display_name or segment)
        return DraftContent(subject=subject, body=FOLLOW_UP_BODY_TEMPLATE)

    return None
