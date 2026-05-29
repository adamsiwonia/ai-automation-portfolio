from __future__ import annotations

import re
from typing import Any

from services.deduplication import is_blocked_domain, normalize_domain


GENERIC_COMPANY_NAMES = {
    "business",
    "company",
    "contact",
    "home",
    "homepage",
    "local business",
    "n/a",
    "unknown",
    "unknown company",
    "website",
}

DIRECTORY_WORDS = {
    "directory",
    "listing",
    "listings",
    "marketplace",
    "reviews",
    "search results",
}

ENTERPRISE_SIGNALS = {
    "enterprise",
    "fortune 500",
    "franchise opportunities",
    "global",
    "locations worldwide",
    "multinational",
    "publicly traded",
    "worldwide",
}

HUGE_CHAIN_NAMES = {
    "amazon",
    "costco",
    "mcdonald",
    "starbucks",
    "subway",
    "target",
    "tesco",
    "walmart",
}

SMB_SIGNALS = {
    "boutique",
    "family",
    "founder",
    "independent",
    "local",
    "owner",
    "privately owned",
    "small business",
    "small team",
    "studio",
    "team of",
}

AUTOMATION_FIT_SIGNALS = {
    "admin",
    "appointment",
    "booking",
    "client",
    "follow-up",
    "inquiry",
    "intake",
    "lead",
    "manual",
    "membership",
    "operations",
    "outreach",
    "quote",
    "scheduling",
    "workflow",
}

STOPWORDS = {
    "a",
    "and",
    "automation",
    "business",
    "businesses",
    "for",
    "in",
    "local",
    "needing",
    "of",
    "service",
    "services",
    "small",
    "the",
    "to",
    "with",
    "workflow",
}


def pre_filter_lead(lead: dict[str, Any], niche: str | None = None) -> dict[str, Any]:
    flags: list[str] = []
    company_name = str(lead.get("company_name") or "").strip()
    website_url = str(lead.get("website_url") or "").strip()
    source = str(lead.get("source") or "").lower()
    source_query = niche or str(lead.get("source_query") or lead.get("niche") or "")
    haystack = _lead_text(lead)

    if not website_url:
        flags.append("missing_website_url")

    domain = normalize_domain(website_url)
    if domain and is_blocked_domain(domain):
        flags.append("blocked_or_social_domain")

    if _looks_like_directory(website_url, source, haystack):
        flags.append("directory_listing_or_social_only")

    if _generic_company_name(company_name):
        flags.append("missing_or_generic_company_name")

    if not _matches_search_intent(source_query, haystack):
        flags.append("niche_mismatch")

    if not _has_smb_signal(haystack):
        flags.append("no_clear_smb_signal")

    if _looks_enterprise(company_name, haystack):
        flags.append("likely_large_chain_or_enterprise")

    if not _has_automation_fit(haystack):
        flags.append("irrelevant_to_outreach_automation")

    return {
        "passed": not flags,
        "reason": "Passed pre-filter." if not flags else _reason_from_flags(flags),
        "flags": flags,
    }


def _lead_text(lead: dict[str, Any]) -> str:
    values = [
        lead.get("company_name"),
        lead.get("website_url"),
        lead.get("niche"),
        lead.get("source_query"),
        lead.get("source"),
        lead.get("snippet"),
        lead.get("context"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def _generic_company_name(company_name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", company_name.lower()).strip()
    return not normalized or normalized in GENERIC_COMPANY_NAMES or len(normalized) < 3


def _looks_like_directory(website_url: str, source: str, haystack: str) -> bool:
    if source in {"directory", "listing", "social"}:
        return True
    if is_blocked_domain(website_url):
        return True
    return any(word in haystack for word in DIRECTORY_WORDS)


def _matches_search_intent(source_query: str, haystack: str) -> bool:
    terms = _important_terms(source_query)
    if not terms:
        return True
    matches = sum(1 for term in terms if term in haystack)
    return matches >= min(2, len(terms))


def _important_terms(text: str) -> set[str]:
    raw_terms = re.findall(r"[a-z0-9]+", text.lower())
    terms: set[str] = set()
    for term in raw_terms:
        if term in STOPWORDS or len(term) < 3:
            continue
        if term.endswith("ies") and len(term) > 4:
            term = f"{term[:-3]}y"
        elif term.endswith("s") and len(term) > 4:
            term = term[:-1]
        terms.add(term)
    return terms


def _has_smb_signal(haystack: str) -> bool:
    return any(signal in haystack for signal in SMB_SIGNALS)


def _looks_enterprise(company_name: str, haystack: str) -> bool:
    company = company_name.lower()
    if any(name in company for name in HUGE_CHAIN_NAMES):
        return True
    return any(signal in haystack for signal in ENTERPRISE_SIGNALS)


def _has_automation_fit(haystack: str) -> bool:
    return any(signal in haystack for signal in AUTOMATION_FIT_SIGNALS)


def _reason_from_flags(flags: list[str]) -> str:
    readable = {
        "blocked_or_social_domain": "domain is a blocked directory/social platform",
        "directory_listing_or_social_only": "lead appears to be a listing rather than a business website",
        "irrelevant_to_outreach_automation": "no clear automation/outreach fit",
        "likely_large_chain_or_enterprise": "lead appears too large or chain-like",
        "missing_or_generic_company_name": "company name is missing or generic",
        "missing_website_url": "website URL is missing",
        "niche_mismatch": "lead does not appear to match the search intent",
        "no_clear_smb_signal": "no clear small/medium business signal",
    }
    return "; ".join(readable.get(flag, flag) for flag in flags)

