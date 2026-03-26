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

FIRST_TOUCH_STYLES = ("soft", "direct", "bold")
FIRST_TOUCH_OPENERS = (
    "Quick question -",
    "Quick one -",
    "Just a quick question -",
    "Out of curiosity -",
    "Thought I'd ask -",
)

EMAIL_LIKE_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", re.IGNORECASE)
URL_LIKE_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)

CORE_OFFER_SENTENCE = (
    "I built a simple tool that helps online stores save time on repetitive customer "
    "emails by preparing ready-to-review draft replies for things like delivery, "
    "returns, compatibility, and product questions."
)


@dataclass(frozen=True)
class DraftContent:
    subject: str
    body: str
    generator: str = "template-v2"
    template_variant: str | None = None
    opener_variant: str | None = None
    personalization_used: bool = False
    follow_up_stage: int = 0


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


def _pick_variant(options: tuple[str, ...], *, seed_text: str | None, salt: str) -> str:
    if not options:
        return ""
    seed = (seed_text or "") + "|" + salt
    if not seed.strip():
        return options[0]
    return options[sum(ord(ch) for ch in seed) % len(options)]


def _personalization_sentence(angle: str | None) -> str | None:
    text = " ".join((angle or "").strip().split())
    if not text:
        return None
    return f"Saw your focus on {text}, so I thought this might be relevant."


def _render_first_touch(
    *,
    style: str,
    opener: str,
    personalization_sentence: str | None,
) -> str:
    style_intro = {
        "soft": "Thought this might be useful for your support flow.",
        "direct": "I wanted to share something practical that could save support time.",
        "bold": "I think this could remove a lot of repetitive support workload quickly.",
    }.get(style, "Thought this might be useful for your support flow.")

    paragraphs: list[str] = [
        "Hi,",
        f"{opener} {style_intro}",
    ]
    if personalization_sentence:
        paragraphs.append(personalization_sentence)
    paragraphs.extend(
        [
            CORE_OFFER_SENTENCE,
            "Everything stays human-reviewed - it just reduces the time spent on the same messages over and over.",
            "If you'd like, I can send a short web demo so you can see how it works.",
            "Best,\nAdam",
        ]
    )
    return "\n\n".join(paragraphs)


def _render_follow_up_one() -> str:
    return (
        "Hi,\n\n"
        "Just checking in on my note from earlier.\n\n"
        "The tool prepares ready-to-review draft replies for repetitive customer questions, so your team can answer faster without losing human control.\n\n"
        "If helpful, I can send a short demo link.\n\n"
        "Best,\n"
        "Adam"
    )


def _render_follow_up_two() -> str:
    return (
        "Hi,\n\n"
        "Final quick follow-up from me.\n\n"
        "If reducing repetitive delivery/returns/product-email workload is useful, I'm happy to share a short demo and then leave you to decide.\n\n"
        "Best,\n"
        "Adam"
    )


def build_outreach_draft(
    *,
    classification: LeadClassification,
    company_name: str,
    contact_name: str | None,
    segment: str | None,
    notes: str | None,
    angle: str | None = None,
    follow_up_stage: int = 0,
    original_subject: str | None = None,
    seed_text: str | None = None,
) -> DraftContent | None:
    display_name = build_display_name(company_name)
    _ = contact_name
    _ = notes

    subject_seed = seed_text or display_name or segment or angle

    if classification == LeadClassification.FIRST_TOUCH_READY:
        style = _pick_variant(FIRST_TOUCH_STYLES, seed_text=subject_seed, salt="style")
        opener = _pick_variant(FIRST_TOUCH_OPENERS, seed_text=subject_seed, salt="opener")
        personalization_sentence = _personalization_sentence(angle)
        subject = _subject_for(classification, subject_seed)
        body = _render_first_touch(
            style=style,
            opener=opener,
            personalization_sentence=personalization_sentence,
        )
        return DraftContent(
            subject=subject,
            body=body,
            template_variant=style,
            opener_variant=opener,
            personalization_used=personalization_sentence is not None,
            follow_up_stage=0,
        )

    if classification == LeadClassification.FOLLOW_UP_READY:
        if follow_up_stage == 1:
            body = _render_follow_up_one()
            variant = "follow_up_1"
        elif follow_up_stage == 2:
            body = _render_follow_up_two()
            variant = "follow_up_2"
        else:
            return None

        preferred_subject = " ".join((original_subject or "").split())
        subject = preferred_subject or _subject_for(classification, subject_seed)
        return DraftContent(
            subject=subject,
            body=body,
            template_variant=variant,
            opener_variant=None,
            personalization_used=False,
            follow_up_stage=follow_up_stage,
        )

    return None
