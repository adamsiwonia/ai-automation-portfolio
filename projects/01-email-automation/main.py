# Email Automation Project
# Entry point
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
RECIPIENTS_PATH = PROJECT_DIR / "recipients.csv"
TEMPLATE_PATH = PROJECT_DIR / "template.txt"
LOG_PATH = PROJECT_DIR / "email_log.csv"


@dataclass
class EmailMessage:
    to_email: str
    to_name: str
    subject: str
    body: str


def load_recipients(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing recipients file: {path}")

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"email", "name"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"recipients.csv must contain headers: {sorted(required)}")

        rows = []
        for i, row in enumerate(reader, start=2):  # header is line 1
            email = (row.get("email") or "").strip()
            name = (row.get("name") or "").strip()
            if not email or not name:
                raise ValueError(f"Invalid row at line {i}: email/name cannot be empty")
            rows.append({"email": email, "name": name})
        return rows


def load_template(path: Path) -> tuple[str, str]:
    """
    Expected template format:
    First line:  Subject: <subject text>
    Blank line(s) allowed after.
    Rest: body (may contain placeholders like {name})
    """
    if not path.exists():
        raise FileNotFoundError(f"Missing template file: {path}")

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines or not lines[0].lower().startswith("subject:"):
        raise ValueError("template.txt must start with a line like: Subject: ...")

    subject = lines[0].split(":", 1)[1].strip()
    if not subject:
        raise ValueError("Subject cannot be empty in template.txt")

    # body: everything after the first line (preserve newlines nicely)
    body = "\n".join(lines[1:]).lstrip("\n").rstrip()
    return subject, body


def render_message(subject_tmpl: str, body_tmpl: str, *, name: str, email: str) -> EmailMessage:
    # Very small, safe placeholder set:
    # {name} and {email}
    subject = subject_tmpl.format(name=name, email=email)
    body = body_tmpl.format(name=name, email=email)

    # Avoid accidental double-spaces or leading junk
    subject = re.sub(r"\s+", " ", subject).strip()
    body = body.strip()

    return EmailMessage(to_email=email, to_name=name, subject=subject, body=body)


def ensure_log_header(path: Path) -> None:
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_utc", "email", "status", "error_message"])


def append_log(path: Path, *, email: str, status: str, error_message: str = "") -> None:
    ensure_log_header(path)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([ts, email, status, error_message])


def main() -> None:
    # DRY RUN: does not send emails yet — just generates a preview + logs.
    recipients = load_recipients(RECIPIENTS_PATH)
    subject_tmpl, body_tmpl = load_template(TEMPLATE_PATH)

    print(f"Loaded recipients: {len(recipients)}")
    print("Mode: DRY RUN (no emails will be sent)\n")

    for r in recipients:
        try:
            msg = render_message(subject_tmpl, body_tmpl, name=r["name"], email=r["email"])

            # Preview to console (first recipient fully, others minimal)
            print("----- EMAIL PREVIEW -----")
            print(f"To: {msg.to_email} ({msg.to_name})")
            print(f"Subject: {msg.subject}\n")
            print(msg.body)
            print("-------------------------\n")

            append_log(LOG_PATH, email=msg.to_email, status="DRY_RUN_OK")
        except Exception as e:
            append_log(LOG_PATH, email=r.get("email", ""), status="DRY_RUN_ERROR", error_message=str(e))
            print(f"[ERROR] Failed to render for {r.get('email','')}: {e}")


if __name__ == "__main__":
    main()