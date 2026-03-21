from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str = "gpt-4.1-mini"

def get_settings() -> Settings:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY (.env or env var).")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    return Settings(openai_api_key=key, openai_model=model)
