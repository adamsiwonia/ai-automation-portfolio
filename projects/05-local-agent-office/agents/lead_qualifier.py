from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from services import database
from services.ollama_client import OllamaClient


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config.yaml"
VALID_STATUSES = {"QUALIFIED", "REVIEW", "REJECTED"}


def _default_model() -> str:
    load_dotenv(BASE_DIR / ".env")
    if os.getenv("OLLAMA_MODEL"):
        return os.getenv("OLLAMA_MODEL", "qwen3:8b")
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
        return config.get("ollama", {}).get("default_model", "qwen3:8b")
    return "qwen3:8b"


def build_prompt(lead: dict) -> str:
    return f"""
You are qualifying business leads for an outreach preparation workflow.
Return only strict JSON. Do not include markdown, commentary, or extra keys.

Lead:
- company_name: {lead.get("company_name", "")}
- website_url: {lead.get("website_url", "")}
- contact_email: {lead.get("contact_email", "")}
- niche/search query: {lead.get("niche", "")}
- source: {lead.get("source", "")}
- snippet/context: {lead.get("snippet", lead.get("context", ""))}

JSON schema:
{{
  "score": 1-10,
  "status": "QUALIFIED" | "REVIEW" | "REJECTED",
  "reason": "...",
  "recommended_angle": "...",
  "personal_note": "..."
}}
""".strip()


def _extract_json_object(raw: str) -> str | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_qualification(raw: str) -> dict[str, Any] | None:
    json_text = _extract_json_object(raw)
    if not json_text:
        return None

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    try:
        score = int(parsed.get("score", 5))
    except (TypeError, ValueError):
        score = 5
    parsed["score"] = max(1, min(score, 10))

    status = str(parsed.get("status", "REVIEW")).upper()
    parsed["status"] = status if status in VALID_STATUSES else "REVIEW"
    parsed["reason"] = str(parsed.get("reason", "")).strip() or "No reason returned by model."
    parsed["recommended_angle"] = str(parsed.get("recommended_angle", "")).strip()
    parsed["personal_note"] = str(parsed.get("personal_note", "")).strip()
    return parsed


def _fallback(reason: str, raw: str = "") -> dict[str, Any]:
    parsed = {
        "score": 5,
        "status": "REVIEW",
        "reason": reason,
        "recommended_angle": "Manual review recommended before outreach preparation.",
        "personal_note": "Could not complete reliable local model qualification.",
    }
    return {
        **parsed,
        "raw_model_output": raw,
        "parsed_json": json.dumps(parsed, ensure_ascii=True),
    }


def qualify_lead(lead: dict, model_name: str | None = None) -> dict[str, Any]:
    model = model_name or _default_model()
    prompt = build_prompt(lead)
    raw = ""

    try:
        raw = OllamaClient.from_config().generate(model=model, prompt=prompt)
    except Exception as exc:
        message = f"Ollama unavailable; lead marked REVIEW. {exc}"
        database.add_log("WARNING", message, task="lead_qualifier", metadata={"company": lead.get("company_name")})
        return _fallback(message, raw=f"OLLAMA_ERROR: {exc}")

    parsed = parse_qualification(raw)
    if not parsed:
        message = "Model returned invalid JSON; lead marked REVIEW."
        database.add_log("WARNING", message, task="lead_qualifier", metadata={"company": lead.get("company_name")})
        return _fallback(message, raw=raw)

    return {
        "score": parsed["score"],
        "status": parsed["status"],
        "reason": parsed["reason"],
        "recommended_angle": parsed["recommended_angle"],
        "personal_note": parsed["personal_note"],
        "raw_model_output": raw,
        "parsed_json": json.dumps(parsed, ensure_ascii=True),
    }
