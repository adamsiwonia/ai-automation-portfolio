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

