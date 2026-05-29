from __future__ import annotations

import re
from urllib.parse import urlparse


BLOCKED_DOMAINS = {
    "amazon.com",
    "ebay.com",
    "etsy.com",
    "facebook.com",
    "google.com",
    "instagram.com",
    "linkedin.com",
    "maps.google.com",
    "tiktok.com",
    "tripadvisor.com",
    "yelp.com",
    "youtube.com",
}


def normalize_email(email: str | None) -> str:
    """Normalize an email address for exact dedupe checks."""
    if not email:
        return ""

    cleaned = email.strip().lower()
    if cleaned.startswith("mailto:"):
        cleaned = cleaned.removeprefix("mailto:")
    return cleaned.strip()


def _parse_url(value: str) -> tuple[str, str]:
    cleaned = value.strip().lower()
    if not cleaned:
        return "", ""

    if "://" not in cleaned:
        cleaned = f"http://{cleaned}"

    parsed = urlparse(cleaned)
    host = parsed.hostname or ""
    path = parsed.path or ""
    return host, path


def normalize_domain(url_or_domain: str | None) -> str:
    """Return the root-ish host used for domain-level deduplication."""
    if not url_or_domain:
        return ""

    host, _ = _parse_url(url_or_domain)
    if host.startswith("www."):
        host = host[4:]
    return host.strip(".")


def normalize_website_url(url: str | None) -> str:
    """
    Normalize a website URL for dedupe.

    For this MVP we intentionally collapse paths to the domain because a lead
    website, contact page, and about page should all represent the same company.
    """
    domain = normalize_domain(url)
    if not domain:
        return ""
    return f"https://{domain}"


def normalize_company_name(company_name: str | None) -> str:
    if not company_name:
        return ""

    cleaned = company_name.strip().lower()
    cleaned = cleaned.replace("&", " and ")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    cleaned = re.sub(
        r"\b(ltd|llc|inc|co|company|corp|corporation|limited|plc|group)\b",
        " ",
        cleaned,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def is_blocked_domain(url_or_domain: str | None) -> bool:
    domain = normalize_domain(url_or_domain)
    if not domain:
        return False

    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_DOMAINS)


def leads_match(left: dict, right: dict) -> tuple[bool, str]:
    """Compare two lead dicts using the MVP dedupe rules."""
    left_domain = normalize_domain(left.get("normalized_domain") or left.get("website_url"))
    right_domain = normalize_domain(right.get("normalized_domain") or right.get("website_url"))
    if left_domain and right_domain and left_domain == right_domain:
        return True, f"normalized_domain matched: {left_domain}"

    left_url = normalize_website_url(left.get("website_url"))
    right_url = normalize_website_url(right.get("website_url"))
    if left_url and right_url and left_url == right_url:
        return True, f"normalized website_url matched: {left_url}"

    left_email = normalize_email(left.get("contact_email"))
    right_email = normalize_email(right.get("contact_email"))
    if left_email and right_email and left_email == right_email:
        return True, f"normalized contact_email matched: {left_email}"

    return False, ""
