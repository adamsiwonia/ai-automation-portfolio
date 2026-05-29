from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def env_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def lead_source_mode() -> str:
    load_dotenv(BASE_DIR / ".env")
    value = os.getenv("LEAD_SOURCE_MODE") or load_config().get("lead_source_mode", "mock")
    value = str(value).strip().lower()
    return value if value in {"mock", "manual", "search"} else "mock"


def minimum_qualification_score() -> int:
    load_dotenv(BASE_DIR / ".env")
    raw = os.getenv("MINIMUM_QUALIFICATION_SCORE")
    if raw is None:
        raw = load_config().get("qualification", {}).get("minimum_score", 7)
    try:
        score = int(raw)
    except (TypeError, ValueError):
        score = 7
    return max(1, min(score, 10))


def search_settings() -> dict[str, Any]:
    load_dotenv(BASE_DIR / ".env")
    config = load_config().get("search", {}) or {}
    provider = os.getenv("SEARCH_PROVIDER") or config.get("provider", "seed_urls")
    location = os.getenv("SEARCH_LOCATION") or config.get("location", "")
    max_results = os.getenv("SEARCH_MAX_RESULTS") or config.get("max_results", 10)
    seed_urls_path = os.getenv("SEARCH_SEED_URLS_PATH") or config.get("seed_urls_path", "data/search_seed_urls.txt")

    try:
        parsed_max_results = int(max_results)
    except (TypeError, ValueError):
        parsed_max_results = 10

    return {
        "provider": str(provider).strip().lower(),
        "location": str(location).strip(),
        "max_results": max(1, min(parsed_max_results, 50)),
        "seed_urls_path": str(seed_urls_path).strip(),
    }
