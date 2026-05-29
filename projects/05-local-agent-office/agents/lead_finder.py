from __future__ import annotations

from pathlib import Path

from agents.lead_discovery_agent import LeadDiscoveryAgent, MockLeadProvider, SeedUrlProvider, create_search_provider
from services.settings import search_settings


def find_leads(
    niche: str,
    limit: int,
    lead_source_mode: str = "mock",
    seed_file: Path | None = None,
) -> list[dict]:
    """
    Return structured lead candidates from the configured discovery path.

    Mock mode is explicitly test/demo data. Search mode uses real seed URLs and
    extracts observed page data only.
    """
    mode = lead_source_mode.lower().strip()
    if mode == "mock":
        return LeadDiscoveryAgent(MockLeadProvider()).discover(query=niche, limit=limit)
    if mode == "search":
        settings = search_settings()
        provider_name = settings["provider"]
        if provider_name == "mock":
            raise RuntimeError("Search mode cannot use mock provider")
        if seed_file is not None:
            provider = SeedUrlProvider(seed_file)
        else:
            provider = create_search_provider(provider_name, settings)
        return LeadDiscoveryAgent(provider).discover(query=niche, limit=min(limit, settings["max_results"]))
    if mode == "manual":
        return []
    raise RuntimeError(f"Unsupported lead_source_mode: {lead_source_mode}")
