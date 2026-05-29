from agents.lead_pre_filter import pre_filter_lead


def test_pre_filter_rejects_bad_social_listing() -> None:
    result = pre_filter_lead(
        {
            "company_name": "Business",
            "website_url": "https://facebook.com/some-page",
            "source_query": "local dentists needing booking automation",
            "source": "listing",
            "snippet": "Facebook reviews and directory listing.",
        }
    )

    assert result["passed"] is False
    assert "blocked_or_social_domain" in result["flags"]
    assert "missing_or_generic_company_name" in result["flags"]


def test_pre_filter_accepts_plausible_small_business() -> None:
    result = pre_filter_lead(
        {
            "company_name": "Oak Sparrow Dental",
            "website_url": "https://oaksparrowdental.com",
            "source_query": "local dental clinics needing booking automation",
            "source": "MOCK",
            "snippet": (
                "Independent local dental clinic with a small team. The site mentions "
                "appointment booking, patient intake, and manual follow-up workflows."
            ),
        }
    )

    assert result["passed"] is True
    assert result["flags"] == []

