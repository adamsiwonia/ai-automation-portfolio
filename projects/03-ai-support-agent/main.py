import os
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "data" / "sample_emails.txt"
PROMPT_FILE = PROJECT_DIR / "prompts" / "support_prompt.txt"
OUT_FILE = PROJECT_DIR / "data" / "outputs.json"


def load_samples(text: str):
    # Split by --- separator and remove empty chunks
    return [p.strip() for p in text.split("---") if p.strip()]


def strip_code_fences(text: str) -> str:
    """Remove markdown ```json ... ``` wrappers if present."""
    t = text.strip()
    if t.startswith("```"):
        # remove leading/trailing fences
        t = t.strip().strip("`").strip()
        # sometimes first token is 'json'
        if t.lower().startswith("json"):
            t = t[4:].strip()
    return t


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing OPENAI_API_KEY in environment variables (.env or system env)."
        )

    client = OpenAI(api_key=api_key)

    raw = DATA_FILE.read_text(encoding="utf-8")
    samples = load_samples(raw)

    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")

    results = []
    for i, email in enumerate(samples, start=1):
        prompt = prompt_template.replace("{{EMAIL}}", email)

        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        text = strip_code_fences(resp.output_text)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {
                "category": "OTHER",
                "reply": text,
                "next_step": "Ask the customer for more details.",
            }

        results.append({"id": i, "email": email, "result": parsed})

    OUT_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved: {OUT_FILE}")


if __name__ == "__main__":
    main()