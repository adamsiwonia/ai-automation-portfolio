from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from services.deduplication import normalize_domain, normalize_email


BASE_DIR = Path(__file__).resolve().parents[1]

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


@dataclass
class LeadCandidate:
    company_name: str
    website_url: str
    normalized_domain: str
    contact_email: str = ""
    source: str = "SEARCH"
    lead_source_mode: str = "search"
    snippet: str = ""

    def to_lead_dict(self, query: str) -> dict[str, Any]:
        return {
            "company_name": self.company_name,
            "website_url": self.website_url,
            "normalized_domain": self.normalized_domain,
            "contact_email": self.contact_email,
            "niche": query,
            "source_query": query,
            "source": self.source,
            "lead_source_mode": self.lead_source_mode,
            "snippet": self.snippet,
        }


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[LeadCandidate]:
        ...


class LeadDiscoveryAgent:
    def __init__(self, provider: SearchProvider) -> None:
        self.provider = provider

    def search(self, query: str, limit: int) -> list[LeadCandidate]:
        candidates = self.provider.search(query=query, limit=limit)
        seen_domains: set[str] = set()
        unique_candidates: list[LeadCandidate] = []
        safe_limit = max(1, min(int(limit), 50))

        for candidate in candidates:
            domain = normalize_domain(candidate.normalized_domain or candidate.website_url)
            if domain and domain in seen_domains:
                continue
            if domain:
                seen_domains.add(domain)
            unique_candidates.append(candidate)
            if len(unique_candidates) >= safe_limit:
                break

        return unique_candidates

    def discover(self, query: str, limit: int) -> list[dict[str, Any]]:
        return [candidate.to_lead_dict(query) for candidate in self.search(query=query, limit=limit)]


class MockLeadProvider:
    name = "mock"

    def search(self, query: str, limit: int) -> list[LeadCandidate]:
        safe_limit = max(1, min(int(limit), 50))
        slug = _slugify(query)
        segment = _segment_from_query(query)
        candidates: list[LeadCandidate] = []

        for index in range(safe_limit):
            name_template, domain_template, smb_signal = MOCK_TEMPLATES[index % len(MOCK_TEMPLATES)]
            domain = domain_template.format(slug=slug)
            company_name = name_template.format(segment=segment)
            candidates.append(
                LeadCandidate(
                    company_name=company_name,
                    website_url=f"https://{domain}/about",
                    normalized_domain=domain,
                    contact_email="" if index % 3 == 0 else f"hello@{domain}",
                    source="MOCK",
                    lead_source_mode="mock",
                    snippet=(
                        f"MOCK result: {company_name} is a {smb_signal} matching '{query}'. "
                        "Their site mentions appointment handling, client follow-up, scheduling, "
                        "and manual admin workflows."
                    ),
                )
            )

        return candidates


class SeedUrlProvider:
    name = "seed_urls"

    def __init__(self, seed_file: Path, fetcher: Callable[[str], str] | None = None) -> None:
        self.seed_file = seed_file
        self.fetcher = fetcher

    def search(self, query: str, limit: int) -> list[LeadCandidate]:
        urls = self._read_urls()
        if not urls:
            raise RuntimeError("Seed URL provider not configured: add URLs to data/search_seed_urls.txt")

        candidates: list[LeadCandidate] = []
        safe_limit = max(1, int(limit))
        for url in urls:
            html = self._fetch(url)
            if not html:
                continue
            candidate = lead_candidate_from_page(url=url, html=html)
            if candidate:
                candidates.append(candidate)
                if len(candidates) >= safe_limit:
                    break
        return candidates

    def _read_urls(self) -> list[str]:
        if not self.seed_file.exists():
            return []
        urls: list[str] = []
        with self.seed_file.open("r", encoding="utf-8") as file:
            for line in file:
                cleaned = line.strip()
                if cleaned and not cleaned.startswith("#"):
                    urls.append(cleaned)
        return urls

    def _fetch(self, url: str) -> str:
        fetcher = self.fetcher or fetch_page
        try:
            return fetcher(url)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return ""


class BraveProvider:
    name = "brave"

    def __init__(self, api_key: str | None = None, api_calls_enabled: bool | None = None) -> None:
        load_dotenv(BASE_DIR / ".env")
        self.api_key = api_key if api_key is not None else os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.api_calls_enabled = (
            api_calls_enabled if api_calls_enabled is not None else _env_bool(os.getenv("BRAVE_SEARCH_API_ENABLED"))
        )

    def search(self, query: str, limit: int) -> list[LeadCandidate]:
        if not self.api_key:
            raise RuntimeError("Brave Search provider not configured")
        if not self.api_calls_enabled:
            raise RuntimeError("Brave Search provider API calls are disabled")
        raise NotImplementedError("Brave Search API integration is not implemented yet")


class GooglePlacesProvider:
    name = "google_places"

    def __init__(self, api_key: str | None = None, api_calls_enabled: bool | None = None) -> None:
        load_dotenv(BASE_DIR / ".env")
        self.api_key = api_key if api_key is not None else os.getenv("GOOGLE_PLACES_API_KEY", "")
        self.api_calls_enabled = (
            api_calls_enabled if api_calls_enabled is not None else _env_bool(os.getenv("GOOGLE_PLACES_API_ENABLED"))
        )

    def search(self, query: str, limit: int) -> list[LeadCandidate]:
        if not self.api_key:
            raise RuntimeError("Google Places provider not configured")
        if not self.api_calls_enabled:
            raise RuntimeError("Google Places provider API calls are disabled")
        raise NotImplementedError("Google Places API integration is not implemented yet")


def create_search_provider(provider_name: str, config: dict[str, Any] | None = None) -> SearchProvider:
    config = config or {}
    provider = provider_name.strip().lower()

    if provider == "mock":
        return MockLeadProvider()
    if provider == "seed_urls":
        seed_path = _resolve_seed_path(str(config.get("seed_urls_path") or "data/search_seed_urls.txt"))
        return SeedUrlProvider(seed_path)
    if provider == "brave":
        api_key = config.get("brave_api_key")
        return BraveProvider(api_key=str(api_key) if api_key else None)
    if provider == "google_places":
        api_key = config.get("google_places_api_key")
        return GooglePlacesProvider(api_key=str(api_key) if api_key else None)

    raise ValueError(f"Unknown lead discovery provider: {provider_name}")


def provider_registry() -> dict[str, type]:
    return {
        "mock": MockLeadProvider,
        "seed_urls": SeedUrlProvider,
        "brave": BraveProvider,
        "google_places": GooglePlacesProvider,
    }


def fetch_page(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Project05LeadDiscovery/0.1"})
    with urlopen(request, timeout=10) as response:
        raw = response.read(1_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def lead_candidate_from_page(url: str, html: str) -> LeadCandidate | None:
    domain = normalize_domain(url)
    if not domain:
        return None

    parser = VisiblePageParser()
    parser.feed(html)
    visible_text = " ".join(parser.visible_text())
    company_name = _company_from_page(parser.site_name(), parser.title(), domain)
    email = _first_visible_email(visible_text)
    snippet = _compact_text(visible_text)

    return LeadCandidate(
        company_name=company_name,
        website_url=url,
        normalized_domain=domain,
        contact_email=email,
        source="SEARCH",
        lead_source_mode="search",
        snippet=snippet,
    )


class VisiblePageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._title_parts: list[str] = []
        self._site_name = ""
        self._visible_parts: list[str] = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            attr_map = {name.lower(): value or "" for name, value in attrs}
            if attr_map.get("property", "").lower() == "og:site_name" and attr_map.get("content"):
                self._site_name = attr_map["content"].strip()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        cleaned = _compact_text(unescape(data))
        if not cleaned:
            return
        if self._in_title:
            self._title_parts.append(cleaned)
        elif not self._ignored_depth:
            self._visible_parts.append(cleaned)

    def title(self) -> str:
        return _compact_text(" ".join(self._title_parts))

    def site_name(self) -> str:
        return _compact_text(self._site_name)

    def visible_text(self) -> list[str]:
        return self._visible_parts


def _resolve_seed_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def _env_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _first_visible_email(text: str) -> str:
    match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, flags=re.IGNORECASE)
    return normalize_email(match.group(0)) if match else ""


def _company_from_page(site_name: str, title: str, domain: str) -> str:
    for candidate in [site_name, _clean_title(title), _company_from_domain(domain)]:
        cleaned = _compact_text(candidate)
        if cleaned:
            return cleaned
    return domain


def _clean_title(title: str) -> str:
    if not title:
        return ""
    return re.split(r"\s+[|\u2013\u2014-]\s+|[:\u00bb]", title, maxsplit=1)[0].strip()


def _company_from_domain(domain: str) -> str:
    parsed = urlparse(f"https://{domain}")
    host = parsed.hostname or domain
    base = host.split(".")[0]
    words = re.sub(r"[^a-z0-9]+", " ", base.lower()).strip()
    return words.title()


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


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
