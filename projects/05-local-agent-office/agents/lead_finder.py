from __future__ import annotations

import re


MOCK_TEMPLATES = [
    ("Northstar {segment} Studio", "northstar-{slug}.co.uk", "independent studio"),
    ("Brightlane {segment}", "brightlane-{slug}.com", "small local team"),
    ("Harbor Field {segment}", "harborfield-{slug}.com", "family-owned business"),
    ("Copper Finch {segment}", "copperfinch-{slug}.co", "owner-led company"),
    ("Juniper Desk {segment}", "juniperdesk-{slug}.com", "boutique service provider"),
    ("Stonebridge {segment}", "stonebridge-{slug}.co.uk", "privately owned local firm"),
    ("Little Atlas {segment}", "littleatlas-{slug}.com", "small business"),
    ("Oakroom {segment}", "oakroom-{slug}.co", "independent local team"),
]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "business"


def _title_niche(niche: str) -> str:
    cleaned = niche.strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Business"


def _segment_from_query(niche: str) -> str:
    cleaned = re.sub(
        r"\b(needing|need|needs|workflow|automation|outreach|local|small|business|businesses|for|with)\b",
        " ",
        niche.lower(),
    )
    words = [word for word in re.findall(r"[a-z0-9]+", cleaned) if len(word) > 2]
    if not words:
        return "Business"
    return _title_niche(" ".join(words[:3]))


def find_leads(niche: str, limit: int, lead_source_mode: str = "mock") -> list[dict]:
    """
    Return structured lead candidates.

    The function boundary is intentionally search-engine shaped so real search
    can replace this without changing the rest of the workflow.
    """
    mode = lead_source_mode.lower().strip()
    if mode in {"manual", "search"}:
        return []

    safe_limit = max(1, min(int(limit), 50))
    slug = _slugify(niche)
    segment = _segment_from_query(niche)
    leads: list[dict] = []

    for index in range(safe_limit):
        name_template, domain_template, smb_signal = MOCK_TEMPLATES[index % len(MOCK_TEMPLATES)]
        domain = domain_template.format(slug=slug)
        company_name = name_template.format(segment=segment)
        leads.append(
            {
                "company_name": company_name,
                "website_url": f"https://{domain}/about",
                "contact_email": "" if index % 3 == 0 else f"hello@{domain}",
                "niche": niche,
                "source_query": niche,
                "source": "MOCK",
                "lead_source_mode": "mock",
                "snippet": (
                    f"MOCK result: {company_name} is a {smb_signal} matching '{niche}'. "
                    "Their site mentions appointment handling, client follow-up, scheduling, "
                    "and manual admin workflows."
                ),
            }
        )

    return leads
