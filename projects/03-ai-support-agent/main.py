import os
import json
from pathlib import Path

from datetime import datetime, timezone
from database.db import init_db, insert_log
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

def extract_field(email_block: str, prefix: str) -> str | None:
    for line in email_block.splitlines():
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip() if ":" in line else None
    return None


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing OPENAI_API_KEY in environment variables (.env or system env)."
        )

    client = OpenAI(api_key=api_key)

    init_db()

    raw = DATA_FILE.read_text(encoding="utf-8")
    samples = load_samples(raw)

    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")

    results = []
    for i, email in enumerate(samples, start=1):
        prompt = prompt_template.replace("{{EMAIL}}", email)

        customer_from = extract_field(email, "From")
        subject = extract_field(email, "Subject")

        raw_model_output = None
        parse_ok = 1
        error_message = None

        try:
            resp = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )

            raw_model_output = resp.output_text
            text = strip_code_fences(raw_model_output)

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parse_ok = 0
                parsed = {
                    "category": "OTHER",
                    "reply": text,
                    "next_step": "Ask the customer for more details.",
                }

        except Exception as e:
            parse_ok = 0
            error_message = str(e)
            parsed = {
                "category": "OTHER",
                "reply": "Sorry — we couldn't generate a response right now.",
                "next_step": "Please try again later or handle this message manually.",
            }

        results.append({"id": i, "email": email, "result": parsed})

        insert_log(
            created_at=now_utc_iso(),
            source="sample_file",
            customer_from=customer_from,
            subject=subject,
            category=parsed.get("category"),
            reply=parsed.get("reply"),
            next_step=parsed.get("next_step"),
            raw_email=email,
            raw_model_output=raw_model_output,
            parse_ok=parse_ok,
            error_message=error_message,
        )

    OUT_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved: {OUT_FILE}")


if __name__ == "__main__":
    main()