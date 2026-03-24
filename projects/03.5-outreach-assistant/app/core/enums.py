from __future__ import annotations

from enum import Enum


class LeadClassification(str, Enum):
    FIRST_TOUCH_READY = "FIRST_TOUCH_READY"
    FOLLOW_UP_READY = "FOLLOW_UP_READY"
    FOLLOW_UP_SKIPPED = "FOLLOW_UP_SKIPPED"
    CONTACT_FORM_REVIEW = "CONTACT_FORM_REVIEW"
    EMAIL_NEEDS_REVIEW = "EMAIL_NEEDS_REVIEW"
    DONE = "DONE"


class ContactChannel(str, Enum):
    EMAIL = "EMAIL"
    CONTACT_FORM = "CONTACT_FORM"
    MALFORMED = "MALFORMED"
    UNKNOWN = "UNKNOWN"
