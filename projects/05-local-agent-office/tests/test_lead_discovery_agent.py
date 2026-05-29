import pytest

from agents import lead_discovery_agent
from agents.lead_discovery_agent import (
    BraveProvider,
    GooglePlacesProvider,
    LeadCandidate,
    LeadDiscoveryAgent,
    SeedUrlProvider,
    create_search_provider,
)
from agents.lead_finder import find_leads
from agents.lead_researcher import research_lead
from tests.workspace_tmp import workspace_tmp_dir


REAL_PAGE_HTML = """
<html>
  <head>
    <title>Oak Sparrow Dental | Independent local clinic</title>
    <meta property="og:site_name" content="Oak Sparrow Dental">
  </head>
  <body>
    <h1>Oak Sparrow Dental</h1>
    <p>Independent local dental clinic with a small team.</p>
    <p>We help patients with appointment booking, intake, and follow-up.</p>
    <p>Email hello@oaksparrowdental.example to contact our reception team.</p>
  </body>
</html>
"""


def test_seed_url_provider_extracts_real_lead_from_page() -> None:
    provider = SeedUrlProvider(
        seed_file=_seed_file_stub(["https://www.oaksparrowdental.example/about"]),
        fetcher=lambda _url: REAL_PAGE_HTML,
    )

    leads = LeadDiscoveryAgent(provider).discover("local dental clinics needing booking automation", limit=5)

    assert len(leads) == 1
    lead = leads[0]
    assert lead["company_name"] == "Oak Sparrow Dental"
    assert lead["website_url"] == "https://www.oaksparrowdental.example/about"
    assert lead["normalized_domain"] == "oaksparrowdental.example"
    assert lead["contact_email"] == "hello@oaksparrowdental.example"
    assert lead["source"] == "SEARCH"
    assert lead["lead_source_mode"] == "search"
    assert "MOCK result" not in lead["snippet"]


def test_search_mode_does_not_use_mock_templates(monkeypatch) -> None:
    with workspace_tmp_dir("seed-search") as tmp_dir:
        seed_file = tmp_dir / "search_seed_urls.txt"
        seed_file.write_text("https://www.oaksparrowdental.example/about\n", encoding="utf-8")
        monkeypatch.setattr(
            "agents.lead_finder.search_settings",
            lambda: {
                "provider": "seed_urls",
                "location": "Inverness, Scotland",
                "max_results": 10,
                "seed_urls_path": str(seed_file),
            },
        )
        monkeypatch.setattr(lead_discovery_agent, "fetch_page", lambda _url: REAL_PAGE_HTML)

        leads = find_leads("local dental clinics needing booking automation", limit=3, lead_source_mode="search")

        assert len(leads) == 1
        lead = leads[0]
        assert lead["source"] == "SEARCH"
        assert lead["lead_source_mode"] == "search"
        assert lead["company_name"] == "Oak Sparrow Dental"
        assert not any(name in lead["company_name"] for name in ["Northstar", "Brightlane", "Harbor Field"])
        assert "MOCK result" not in lead["snippet"]


def test_search_mode_fails_clearly_without_seed_urls() -> None:
    with workspace_tmp_dir("empty-seed-search") as tmp_dir:
        empty_seed_file = tmp_dir / "search_seed_urls.txt"
        empty_seed_file.write_text("# no urls yet\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match="Seed URL provider not configured"):
            find_leads("local accountants", limit=5, lead_source_mode="search", seed_file=empty_seed_file)


def test_research_lead_does_not_invent_email_for_search_lead() -> None:
    lead = research_lead(
        {
            "company_name": "Oak Sparrow Dental",
            "website_url": "https://oaksparrowdental.example",
            "source": "SEARCH",
            "lead_source_mode": "search",
        }
    )

    assert lead["normalized_domain"] == "oaksparrowdental.example"
    assert lead["contact_email"] == ""


def test_provider_factory_selects_seed_urls() -> None:
    provider = create_search_provider("seed_urls", {"seed_urls_path": "data/search_seed_urls.txt"})

    assert isinstance(provider, SeedUrlProvider)


def test_provider_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown lead discovery provider"):
        create_search_provider("mystery_provider")


def test_brave_provider_fails_clearly_without_key() -> None:
    with pytest.raises(RuntimeError, match="Brave Search provider not configured"):
        BraveProvider(api_key="").search("local dentists", limit=5)


def test_google_places_provider_fails_clearly_without_key() -> None:
    with pytest.raises(RuntimeError, match="Google Places provider not configured"):
        GooglePlacesProvider(api_key="").search("local dentists", limit=5)


def test_mock_provider_remains_separate_from_search_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "agents.lead_finder.search_settings",
        lambda: {
            "provider": "mock",
            "location": "",
            "max_results": 10,
            "seed_urls_path": "data/search_seed_urls.txt",
        },
    )

    with pytest.raises(RuntimeError, match="Search mode cannot use mock provider"):
        find_leads("local dentists", limit=5, lead_source_mode="search")


def test_search_mode_never_falls_back_to_mock_silently() -> None:
    with workspace_tmp_dir("empty-seed-no-fallback") as tmp_dir:
        seed_file = tmp_dir / "search_seed_urls.txt"
        seed_file.write_text("# no urls\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match="Seed URL provider not configured"):
            find_leads("local dentists", limit=5, lead_source_mode="search", seed_file=seed_file)


def test_provider_search_returns_lead_candidates() -> None:
    provider = SeedUrlProvider(
        seed_file=_seed_file_stub(["https://www.oaksparrowdental.example/about"]),
        fetcher=lambda _url: REAL_PAGE_HTML,
    )

    candidates = provider.search("local dentists", limit=5)

    assert isinstance(candidates[0], LeadCandidate)
    assert candidates[0].source == "SEARCH"


class _seed_file_stub:
    def __init__(self, urls: list[str]) -> None:
        self.urls = urls

    def exists(self) -> bool:
        return True

    def open(self, *args, **kwargs):
        from io import StringIO

        return StringIO("\n".join(self.urls))
