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
    # dzielimy po separatorze --- i czyścimy puste
    parts = [p.strip() for p in text.split("---") if p.strip()]
    return parts

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Brak OPENAI_API_KEY w zmiennych środowiskowych (.env lub system env).")

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

        text = resp.output_text.strip()

        # Remove markdown code fences if present
    if text.startswith("```"):
         text = text.strip("`")
         text = text.replace("json", "", 1).strip()

    try:
     parsed = json.loads(text)
    except json.JSONDecodeError:
     parsed = {
        "category": "OTHER",
        "reply": text,
        "next_step": "Ask the customer for more details."
    }


    results.append({"id": i, "email": email, "result": parsed})

    OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapisano: {OUT_FILE}")

if __name__ == "__main__":
    main()