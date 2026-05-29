from __future__ import annotations

from typing import Any


MOCK_SOURCE_MARKERS = {"mock", "mock_search", "demo", "sample", "fake"}


def is_mock_or_demo_lead(lead: dict[str, Any]) -> bool:
    source = str(lead.get("source") or "").strip().lower()
    source_mode = str(lead.get("lead_source_mode") or "").strip().lower()
    snippet = str(lead.get("snippet") or "").strip().lower()

    return (
        source in MOCK_SOURCE_MARKERS
        or source_mode in MOCK_SOURCE_MARKERS
        or snippet.startswith("mock result:")
    )
