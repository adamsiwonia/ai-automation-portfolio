from __future__ import annotations

from app.core.enums import LeadClassification
from app.services.drafting import (
    FIRST_TOUCH_OPENERS,
    FIRST_TOUCH_STYLES,
    build_display_name,
    build_outreach_draft,
)


def test_build_display_name_rejects_dirty_values() -> None:
    assert build_display_name("Unknown Company") is None
    assert build_display_name("info@example.com") is None
    assert build_display_name("https://example.com/contact") is None
    assert build_display_name("221B Baker Street, London, NW1 6XE") is None


def test_first_touch_subject_is_neutral() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FIRST_TOUCH_READY,
        company_name="info@example.com",
        contact_name="",
        segment="Retail",
        notes="",
        angle=None,
    )
    assert draft is not None
    assert draft.subject in {
        "Quick question about customer emails",
        "Quick question about repetitive customer enquiries",
    }


def test_follow_up_subject_is_neutral() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FOLLOW_UP_READY,
        company_name="https://example.com",
        contact_name="",
        segment="Retail",
        notes="",
        angle=None,
        follow_up_stage=1,
    )
    assert draft is not None
    assert draft.subject in {
        "Following up on my previous email",
        "Quick follow-up",
    }


def test_follow_up_reuses_original_subject_when_provided() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FOLLOW_UP_READY,
        company_name="Some Store",
        contact_name="",
        segment="Retail",
        notes="",
        angle=None,
        follow_up_stage=1,
        original_subject="Quick question about customer emails",
    )
    assert draft is not None
    assert draft.subject == "Quick question about customer emails"


def test_follow_up_uses_fallback_subject_when_original_is_missing() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FOLLOW_UP_READY,
        company_name="Some Store",
        contact_name="",
        segment="Retail",
        notes="",
        angle=None,
        follow_up_stage=1,
        original_subject="   ",
        seed_text="fallback-seed",
    )
    assert draft is not None
    assert draft.subject in {
        "Following up on my previous email",
        "Quick follow-up",
    }


def test_first_touch_variants_rotate_across_seed_values() -> None:
    variants: set[str] = set()
    for seed in ("seed-a", "seed-b", "seed-c", "seed-d", "seed-e", "seed-f"):
        draft = build_outreach_draft(
            classification=LeadClassification.FIRST_TOUCH_READY,
            company_name="Some Store",
            contact_name="Alex",
            segment="outdoor_shop",
            notes="",
            angle=None,
            seed_text=seed,
        )
        assert draft is not None
        assert draft.template_variant in FIRST_TOUCH_STYLES
        variants.add(draft.template_variant or "")

    assert len(variants) >= 2


def test_first_touch_personalization_added_when_angle_present() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FIRST_TOUCH_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
        angle="BMW performance parts",
        seed_text="seed-with-angle",
    )
    assert draft is not None
    assert draft.personalization_used is True
    assert "Saw your focus on BMW performance parts" in draft.body
    assert draft.body.count("Saw your focus on BMW performance parts") == 1


def test_first_touch_personalization_not_added_when_angle_missing() -> None:
    draft = build_outreach_draft(
        classification=LeadClassification.FIRST_TOUCH_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
        angle=None,
        seed_text="seed-no-angle",
    )
    assert draft is not None
    assert draft.personalization_used is False
    assert "Saw your focus on" not in draft.body


def test_first_touch_opener_selection_is_deterministic_and_varied() -> None:
    openers: set[str] = set()
    for seed in ("alpha", "beta", "gamma", "delta", "epsilon"):
        draft = build_outreach_draft(
            classification=LeadClassification.FIRST_TOUCH_READY,
            company_name="Some Store",
            contact_name="Alex",
            segment="outdoor_shop",
            notes="",
            angle=None,
            seed_text=seed,
        )
        assert draft is not None
        assert draft.opener_variant in FIRST_TOUCH_OPENERS
        openers.add(draft.opener_variant or "")

    deterministic = build_outreach_draft(
        classification=LeadClassification.FIRST_TOUCH_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
        angle=None,
        seed_text="alpha",
    )
    deterministic_again = build_outreach_draft(
        classification=LeadClassification.FIRST_TOUCH_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
        angle=None,
        seed_text="alpha",
    )
    assert deterministic is not None
    assert deterministic_again is not None
    assert deterministic.opener_variant == deterministic_again.opener_variant
    assert len(openers) >= 2


def test_follow_up_stage_one_and_two_are_supported() -> None:
    follow_up_one = build_outreach_draft(
        classification=LeadClassification.FOLLOW_UP_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
        angle=None,
        follow_up_stage=1,
        seed_text="follow-up-seed",
    )
    follow_up_two = build_outreach_draft(
        classification=LeadClassification.FOLLOW_UP_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
        angle=None,
        follow_up_stage=2,
        seed_text="follow-up-seed",
    )

    assert follow_up_one is not None
    assert follow_up_one.template_variant == "follow_up_1"
    assert "Just checking in on my note from earlier." in follow_up_one.body

    assert follow_up_two is not None
    assert follow_up_two.template_variant == "follow_up_2"
    assert "Final quick follow-up from me." in follow_up_two.body


def test_follow_up_stage_above_two_does_not_generate_draft() -> None:
    follow_up = build_outreach_draft(
        classification=LeadClassification.FOLLOW_UP_READY,
        company_name="Some Store",
        contact_name="Alex",
        segment="outdoor_shop",
        notes="",
        angle=None,
        follow_up_stage=3,
        seed_text="follow-up-seed",
    )
    assert follow_up is None

