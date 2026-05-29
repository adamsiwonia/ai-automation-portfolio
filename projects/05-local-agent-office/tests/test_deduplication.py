from services.deduplication import (
    is_blocked_domain,
    leads_match,
    normalize_domain,
    normalize_email,
    normalize_website_url,
)


def test_normalize_domain_treats_common_variants_as_same() -> None:
    variants = [
        "https://example.com",
        "http://www.example.com/",
        "https://example.com/contact",
        "https://example.com/about",
    ]

    assert {normalize_domain(value) for value in variants} == {"example.com"}


def test_normalize_website_url_collapses_paths_to_site_root() -> None:
    assert normalize_website_url("https://www.example.com/contact") == "https://example.com"
    assert normalize_website_url("example.com/about") == "https://example.com"


def test_normalize_email_lowercases_and_strips_mailto() -> None:
    assert normalize_email(" MAILTO:Hello@Example.COM ") == "hello@example.com"


def test_leads_match_by_domain_or_email() -> None:
    left = {"website_url": "https://www.example.com/contact", "contact_email": "sales@example.com"}
    right = {"website_url": "http://example.com/about", "contact_email": "other@example.com"}
    assert leads_match(left, right)[0] is True

    email_left = {"website_url": "https://alpha.example.com", "contact_email": "HELLO@ACME.COM"}
    email_right = {"website_url": "https://beta.example.com", "contact_email": "hello@acme.com"}
    assert leads_match(email_left, email_right)[0] is True


def test_blocked_social_and_marketplace_domains() -> None:
    assert is_blocked_domain("https://www.facebook.com/some-page") is True
    assert is_blocked_domain("https://maps.google.com/place/example") is True
    assert is_blocked_domain("https://example-local-studio.com") is False
