from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Mapping
from urllib.parse import urlparse, urlunparse

from app.core.config import Settings
from app.core.enums import ContactChannel

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
HOST_RE = re.compile(r"^[a-z0-9.-]+$", re.IGNORECASE)
SEGMENT_WORD_RE = re.compile(r"[^a-z0-9]+")

SEGMENT_MAP: dict[str, str] = {
    "outdor": "outdoor_shop",
    "outdoor": "outdoor_shop",
    "outdoor_shop": "outdoor_shop",
    "car_parts": "car_parts",
    "car_part": "car_parts",
    "carparts": "car_parts",
    "workshop": "workshop",
}


@dataclass(frozen=True)
class ContactParseResult:
    email: str | None
    contact_form_url: str | None
    malformed_value: str | None
    channel: ContactChannel


@dataclass(frozen=True)
class NormalizedLeadRow:
    source_sheet: str
    source_row_number: int
    external_id: str | None
    company_name: str
    website: str | None
    notes: str | None
    segment: str | None
    human_response: str | None
    source_status: str | None
    contact_name: str | None
    raw_contact_value: str | None
    email: str | None
    contact_form_url: str | None
    malformed_contact_value: str | None
    contact_channel: str
    last_contacted_at: str | None
    follow_up_due_at: str | None


def normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_email(value: str | None) -> str | None:
    text = normalize_text(value)
    if not text:
        return None

    candidate = text.replace("mailto:", "").strip().lower()
    if EMAIL_RE.fullmatch(candidate):
        return candidate
    return None


def looks_like_url(value: str | None) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    return text.startswith(("http://", "https://", "www.")) or ("." in text and "/" in text)


def normalize_url(value: str | None) -> str | None:
    text = normalize_text(value)
    if not text:
        return None

    candidate = text
    if candidate.startswith("www."):
        candidate = f"https://{candidate}"
    elif not URL_SCHEME_RE.match(candidate) and "." in candidate and " " not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    host = parsed.hostname or ""
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or "@" in parsed.netloc
        or not host
        or ".." in host
        or host.startswith((".", "-"))
        or host.endswith((".", "-"))
        or "." not in host
        or not HOST_RE.fullmatch(host)
    ):
        return None

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def parse_contact_value(raw_value: str | None) -> ContactParseResult:
    text = normalize_text(raw_value)
    if not text:
        return ContactParseResult(
            email=None,
            contact_form_url=None,
            malformed_value=None,
            channel=ContactChannel.UNKNOWN,
        )

    email = normalize_email(text)
    if email:
        return ContactParseResult(
            email=email,
            contact_form_url=None,
            malformed_value=None,
            channel=ContactChannel.EMAIL,
        )

    url = normalize_url(text)
    if url:
        return ContactParseResult(
            email=None,
            contact_form_url=url,
            malformed_value=None,
            channel=ContactChannel.CONTACT_FORM,
        )

    return ContactParseResult(
        email=None,
        contact_form_url=None,
        malformed_value=text,
        channel=ContactChannel.MALFORMED,
    )


def normalize_datetime(raw_value: str | None) -> str | None:
    text = normalize_text(raw_value)
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo:
            return (
                dt.astimezone(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        return dt.replace(microsecond=0).isoformat()
    except ValueError:
        pass

    for fmt in ("%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            return datetime.combine(parsed, time.min).isoformat()
        except ValueError:
            continue

    try:
        parsed_date = date.fromisoformat(text)
        return datetime.combine(parsed_date, time.min).isoformat()
    except ValueError:
        return text


def normalize_segment(raw_value: str | None) -> str:
    text = normalize_text(raw_value)
    if not text:
        return "other"

    normalized = SEGMENT_WORD_RE.sub("_", text.strip().lower()).strip("_")
    if not normalized:
        return "other"
    return SEGMENT_MAP.get(normalized, "other")


def _get_row_value(
    row: Mapping[str, object],
    column_name: str,
    aliases: tuple[str, ...] = (),
) -> str | None:
    if not column_name:
        column_candidates: list[str] = [*aliases]
    else:
        column_candidates = [column_name, *aliases]

    for candidate in column_candidates:
        if candidate in row:
            return normalize_text(row[candidate])

    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for candidate in column_candidates:
        value = lowered.get(candidate.strip().lower())
        normalized = normalize_text(value)
        if normalized is not None:
            return normalized
    return None


def normalize_sheet_row(
    row: Mapping[str, object],
    *,
    settings: Settings,
    source_sheet: str,
    source_row_number: int,
) -> NormalizedLeadRow:
    contact_raw = _get_row_value(row, settings.contact_value_column)
    parsed_contact = parse_contact_value(contact_raw)

    company = _get_row_value(
        row,
        settings.company_column,
        aliases=("Company", "Firma"),
    ) or "Unknown Company"

    return NormalizedLeadRow(
        source_sheet=source_sheet,
        source_row_number=source_row_number,
        external_id=_get_row_value(row, settings.external_id_column),
        company_name=company,
        website=normalize_url(_get_row_value(row, settings.website_column)),
        notes=_get_row_value(row, settings.notes_column),
        segment=normalize_segment(_get_row_value(row, settings.segment_column)),
        human_response=_get_row_value(row, settings.response_column),
        source_status=_get_row_value(row, settings.assistant_status_column),
        contact_name=_get_row_value(row, settings.contact_name_column),
        raw_contact_value=contact_raw,
        email=parsed_contact.email,
        contact_form_url=parsed_contact.contact_form_url,
        malformed_contact_value=parsed_contact.malformed_value,
        contact_channel=parsed_contact.channel.value,
        last_contacted_at=normalize_datetime(
            _get_row_value(row, settings.last_contacted_column)
        ),
        follow_up_due_at=normalize_datetime(
            _get_row_value(
                row,
                settings.follow_up_due_column,
                aliases=("Follow Up Date", "Follow-up Date"),
            )
        ),
    )
