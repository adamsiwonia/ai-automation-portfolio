from __future__ import annotations

from services.deduplication import normalize_domain, normalize_email


def research_lead(lead: dict) -> dict:
    """
    Add lightweight research fields.

    This is deliberately simple for the MVP. Later, this function can fetch
    website pages, snippets, or directory profiles before qualification.
    """
    researched = dict(lead)
    domain = normalize_domain(researched.get("website_url"))
    researched["normalized_domain"] = domain

    if not researched.get("contact_email") and domain:
        researched["contact_email"] = f"hello@{domain}"
    else:
        researched["contact_email"] = normalize_email(researched.get("contact_email"))

    return researched

