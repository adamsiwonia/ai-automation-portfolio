from __future__ import annotations

import json
from typing import Any, Dict
from openai import OpenAI

from app.core.config import Settings

DEFAULT_SYSTEM = """You are a professional e-commerce customer support agent.

Rules:
- Be polite and concise
- Do not invent facts
- If missing info (like order number), ask for it
- Use natural, human tone
- Do not mention AI

Return JSON with:
category, reply, next_step
"""

DEFAULT_PROMPT_TEMPLATE = """Analyze this customer email and produce a JSON response with:
- category
- reply
- next_step

Customer email:
{{EMAIL}}
"""


def strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    return t


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def generate_text(
        self,
        *,
        email: str,
        system: str | None,
        prompt_template: str | None,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        sys = system or DEFAULT_SYSTEM
        tmpl = prompt_template or DEFAULT_PROMPT_TEMPLATE
        prompt = tmpl.replace("{{EMAIL}}", email)

        print("OPENAI MODEL:", self.model)
        print("PROMPT SENT TO MODEL:", prompt)

        resp = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": sys},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        raw_text = resp.output_text or ""
        clean = strip_code_fences(raw_text)

        print("RAW MODEL TEXT:", raw_text)
        print("CLEAN MODEL TEXT:", clean)

        parsed = json.loads(clean)

        usage: Dict[str, Any] = {}
        if getattr(resp, "usage", None):
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.total_tokens,
            }

        return {
            "raw_text": raw_text,
            "parsed": parsed,
            "usage": usage,
        }
