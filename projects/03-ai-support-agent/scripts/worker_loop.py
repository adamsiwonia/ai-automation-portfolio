import base64
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import parseaddr

import requests
from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.services.mailboxes import GmailMailbox, load_active_gmail_mailboxes, update_mailbox_tokens

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_SUPPORT_REPLY_ENDPOINT = "http://127.0.0.1:8000/support/reply"


def _resolve_support_reply_endpoint() -> str:
    explicit_endpoint = (os.getenv("SUPPORT_REPLY_ENDPOINT") or "").strip()
    if explicit_endpoint:
        return explicit_endpoint

    base_url = (os.getenv("SUPPORT_BASE_URL") or "").strip()
    if base_url:
        return f"{base_url.rstrip('/')}/support/reply"

    return DEFAULT_SUPPORT_REPLY_ENDPOINT


SUPPORT_REPLY_ENDPOINT = _resolve_support_reply_endpoint()

DEMO_API_KEY = (os.getenv("DEMO_API_KEY") or os.getenv("API_KEY") or "").strip()
POLL_INTERVAL_SECONDS = 60
MAX_RESULTS_PER_CYCLE = 10
DELAY_BETWEEN_EMAILS_SECONDS = 1.0

PROCESSED_LABEL_NAME = "AI_PROCESSED"
SKIPPED_LABEL_NAME = "AI_SKIPPED"

MAX_MESSAGE_CHARS = 12000
MY_EMAIL = os.getenv("MY_EMAIL", "adam.pawel.siwonia@gmail.com")


def log_message_event(action: str, message_data: dict | None = None, **extra) -> None:
    parts = [action]

    if message_data:
        message_id = message_data.get("id", "-")
        from_email = message_data.get("from_email", "-") or "-"
        subject = message_data.get("subject", "-") or "-"
        parts.append(f"id={message_id}")
        parts.append(f"from={from_email}")
        parts.append(f"subject={subject!r}")

    for key, value in extra.items():
        parts.append(f"{key}={value!r}")

    logger.info(" | ".join(parts))


def get_legacy_gmail_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds:
        raise RuntimeError("Missing token.json. Re-run Gmail auth first.")

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _parse_token_expiry(raw_expiry: str | None) -> datetime | None:
    if not raw_expiry:
        return None

    try:
        parsed = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Invalid token_expiry format, ignoring: %r", raw_expiry)
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    # google-auth compares expiry against naive UTC datetimes.
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def get_db_mailbox_gmail_service(mailbox: GmailMailbox):
    if not mailbox.refresh_token:
        raise RuntimeError(f"Mailbox {mailbox.id} missing refresh_token")

    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Missing GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET for DB mailbox auth")

    creds = Credentials(
        token=mailbox.access_token or None,
        refresh_token=mailbox.refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=mailbox.scopes or SCOPES,
    )

    expiry = _parse_token_expiry(mailbox.token_expiry)
    if expiry:
        creds.expiry = expiry

    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        updated_expiry = creds.expiry.isoformat() if creds.expiry else None
        update_mailbox_tokens(
            mailbox_id=mailbox.id,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_expiry=updated_expiry,
        )

    if not creds.valid:
        raise RuntimeError(f"Mailbox {mailbox.id} credentials are invalid and could not be refreshed")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def ensure_label(service, label_name: str) -> str:
    labels_response = service.users().labels().list(userId="me").execute()
    labels = labels_response.get("labels", [])

    for label in labels:
        if label["name"] == label_name:
            return label["id"]

    created = service.users().labels().create(
        userId="me",
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()

    return created["id"]


def has_label(message: dict, label_id: str) -> bool:
    return label_id in message.get("labelIds", [])


def add_label_to_message(service, message_id: str, label_id: str):
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": [label_id]},
    ).execute()


def get_candidate_messages(
    service,
    processed_label_name: str,
    skipped_label_name: str,
    max_results: int = 10,
) -> list[dict]:
    query = (
        f'in:inbox is:unread '
        f'-category:promotions '
        f'-category:social '
        f'-category:updates '
        f'-category:forums '
        f'-label:"{processed_label_name}" '
        f'-label:"{skipped_label_name}"'
    )

    response = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results,
    ).execute()

    message_refs = response.get("messages", [])
    messages = []

    for msg in message_refs:
        full_message = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="full",
        ).execute()
        messages.append(full_message)

    return messages


def _decode_base64url(data: str) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="ignore")


def get_header(headers: list[dict], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def decode_part_body(part: dict) -> str:
    data = part.get("body", {}).get("data")
    return _decode_base64url(data) if data else ""


def strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"(?is)</div>", "\n", text)
    text = re.sub(r"(?is)<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_plain_text(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        text = decode_part_body(payload)
        if text.strip():
            return text

    parts = payload.get("parts", [])
    if parts:
        for part in parts:
            if part.get("mimeType") == "text/plain":
                text = decode_part_body(part)
                if text.strip():
                    return text

        for part in parts:
            nested = extract_plain_text(part)
            if nested.strip():
                return nested

        for part in parts:
            if part.get("mimeType") == "text/html":
                html = decode_part_body(part)
                if html.strip():
                    return strip_html(html)

    data = payload.get("body", {}).get("data")
    if data:
        text = _decode_base64url(data)
        if "<html" in text.lower() or "<body" in text.lower():
            return strip_html(text)
        return text

    return ""


def count_links(text: str) -> int:
    return len(re.findall(r"https?://|www\.", text, flags=re.IGNORECASE))


def looks_like_non_customer_email(from_email: str, subject: str, body: str, list_unsubscribe: str) -> bool:
    from_lower = (from_email or "").lower()
    subject_lower = (subject or "").lower()
    body_lower = (body or "").lower()

    blocked_sender_terms = [
        "no-reply",
        "noreply",
        "marketing",
        "newsletter",
        "mailer",
        "notifications",
        "promo",
        "offers",
        "news",
    ]

    blocked_subject_terms = [
        "sale",
        "offer",
        "discount",
        "gift card",
        "newsletter",
        "promotion",
        "promo",
        "special offer",
        "flash sale",
        "free",
        "last chance",
        "limited time",
        "new jobs",
        "job alert",
        "oferty tygodnia",
        "oferta specjalna",
        "happy hour",
        "clubcard",
    ]

    blocked_body_terms = [
        "unsubscribe",
        "view online",
        "privacy policy",
        "terms and conditions",
        "gift card",
        "buy now",
        "limited time",
        "shop now",
        "special offer",
        "flash sale",
        "automatically generated",
        "manage preferences",
        "update your preferences",
        "click here",
        "clubcard",
    ]

    transactional_sender_terms = [
        "invoice",
        "receipt",
        "statements",
        "billing",
    ]

    transactional_subject_terms = [
        "invoice",
        "receipt",
        "your receipt",
        "payment confirmation",
        "order confirmation",
        "statement",
        "transaction",
        "security alert",
        "password reset",
        "verification code",
        "one-time code",
        "faktura",
        "rachunek",
    ]

    if any(term in from_lower for term in blocked_sender_terms):
        return True

    if any(term in subject_lower for term in blocked_subject_terms):
        return True

    if list_unsubscribe.strip():
        return True

    if any(term in body_lower for term in blocked_body_terms):
        return True

    if count_links(body) > 5:
        return True

    if len(body) > 3000:
        return True

    if any(term in from_lower for term in transactional_sender_terms):
        return True

    if any(term in subject_lower for term in transactional_subject_terms):
        return True

    return False


def looks_like_customer_email(subject: str, body: str) -> bool:
    body_lower = (body or "").lower()
    subject_lower = (subject or "").lower()

    customer_signals = [
        "return",
        "refund",
        "exchange",
        "shipping",
        "delivery",
        "order",
        "size",
        "sizing",
        "wrong item",
        "help",
        "can i",
        "where is",
        "when will",
        "my parcel",
        "my package",
        "not arrived",
        "damaged",
        "broken",
        "missing",
        "cancel my order",
        "track my order",
        "zwrot",
        "wymiana",
        "rozmiar",
        "przesyłka",
        "dostawa",
        "zamówienie",
        "nie dotarł",
        "nie dotarły",
        "uszkodzony",
        "brakuje",
        "gdzie jest moje zamówienie",
    ]

    blocked_non_customer_terms = [
        "unsubscribe",
        "view online",
        "privacy policy",
        "terms and conditions",
        "special offer",
        "oferta specjalna",
        "promo",
        "promotion",
        "newsletter",
        "sale",
        "flash sale",
        "free",
        "discount",
        "oferty tygodnia",
        "limited time",
        "buy now",
        "clubcard",
    ]

    if len(body.strip()) < 20:
        return False

    if count_links(body) > 3:
        return False

    if any(term in body_lower for term in blocked_non_customer_terms):
        return False

    if any(term in subject_lower for term in blocked_non_customer_terms):
        return False

    if any(term in body_lower for term in customer_signals):
        return True

    if any(term in subject_lower for term in customer_signals):
        return True

    return False


def normalize_message_body(body: str) -> str:
    if not body:
        return ""

    cleaned = body.strip()

    if "<html" in cleaned.lower() or "<body" in cleaned.lower() or "</div>" in cleaned.lower():
        cleaned = strip_html(cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) > MAX_MESSAGE_CHARS:
        cleaned = cleaned[:MAX_MESSAGE_CHARS]

    return cleaned.strip()


def read_message(service, original_message: dict) -> dict:
    payload = original_message.get("payload", {})
    headers = payload.get("headers", [])

    subject = get_header(headers, "Subject")
    from_header = get_header(headers, "From")
    list_unsubscribe = get_header(headers, "List-Unsubscribe")
    message_id_header = get_header(headers, "Message-Id")

    thread_id = original_message.get("threadId", "")
    body_text = extract_plain_text(payload).strip()

    return {
        "id": original_message["id"],
        "thread_id": thread_id,
        "subject": subject,
        "from_header": from_header,
        "from_email": parseaddr(from_header)[1],
        "list_unsubscribe": list_unsubscribe,
        "message_id_header": message_id_header,
        "body": body_text,
        "labelIds": original_message.get("labelIds", []),
    }


def call_support_agent(message_text: str, source: str) -> dict:
    headers = {
        "X-API-Key": DEMO_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "source": source,
        "message": message_text,
    }

    response = requests.post(
        SUPPORT_REPLY_ENDPOINT,
        json=payload,
        headers=headers,
        timeout=90,
    )
    response.raise_for_status()
    return response.json()


def create_gmail_draft(
    service,
    to_email: str,
    subject: str,
    reply_text: str,
    thread_id: str | None = None,
    message_id_header: str | None = None,
):
    subject_line = subject if subject and subject.lower().startswith("re:") else f"Re: {subject or 'Your message'}"

    message = MIMEText(reply_text, "plain", "utf-8")
    message["to"] = to_email
    message["subject"] = subject_line

    if message_id_header:
        message["In-Reply-To"] = message_id_header
        message["References"] = message_id_header

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    body = {
        "message": {
            "raw": raw_message,
        }
    }

    if thread_id:
        body["message"]["threadId"] = thread_id

    return service.users().drafts().create(userId="me", body=body).execute()


def process_single_message(
    service,
    original_message: dict,
    processed_label_id: str,
    skipped_label_id: str,
    mailbox_email: str,
    source: str,
):
    message_id = original_message["id"]

    if has_label(original_message, processed_label_id):
        logger.info("Skipping message already processed | id=%s", message_id)
        return "skipped"

    if has_label(original_message, skipped_label_id):
        logger.info("Skipping message already marked as skipped | id=%s", message_id)
        return "skipped"

    message_data = read_message(service, original_message)
    log_message_event("Inspecting message", message_data)

    if mailbox_email and message_data["from_email"].lower() == mailbox_email.lower():
        log_message_event("Skipping own email", message_data)
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    if not message_data["from_email"]:
        log_message_event("Skipping missing sender", message_data)
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    body = normalize_message_body(message_data["body"])
    if not body:
        log_message_event("Skipping empty body after normalization", message_data)
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    if looks_like_non_customer_email(
        message_data["from_email"],
        message_data["subject"],
        body,
        message_data["list_unsubscribe"],
    ):
        log_message_event("Skipping marketing / transactional / automated email", message_data)
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    if not looks_like_customer_email(message_data["subject"], body):
        log_message_event("Skipping non-customer-support email", message_data)
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    log_message_event("Accepted for AI processing", message_data, body_chars=len(body))

    enriched_message = f"Subject: {message_data['subject']}\n\n{body}"
    result = call_support_agent(enriched_message, source=source)

    reply_text = result.get("reply", "").strip()
    category = result.get("category", "")
    next_step = result.get("next_step", "")

    log_message_event(
        "Support agent response",
        message_data,
        category=category,
        next_step=next_step,
        reply_chars=len(reply_text),
    )

    if not reply_text:
        log_message_event("No reply returned, marking as skipped", message_data)
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    create_gmail_draft(
        service=service,
        to_email=message_data["from_email"],
        subject=message_data["subject"],
        reply_text=reply_text,
        thread_id=message_data["thread_id"],
        message_id_header=message_data["message_id_header"],
    )

    add_label_to_message(service, message_id, processed_label_id)
    log_message_event("Draft created and message marked as processed", message_data)
    return "processed"


def process_inbox(
    service,
    processed_label_id: str,
    skipped_label_id: str,
    *,
    processed_label_name: str,
    skipped_label_name: str,
    mailbox_email: str,
    source: str,
):
    logger.info("Checking inbox | mailbox=%s", mailbox_email or "-")

    messages = get_candidate_messages(
        service,
        processed_label_name=processed_label_name,
        skipped_label_name=skipped_label_name,
        max_results=MAX_RESULTS_PER_CYCLE,
    )

    if not messages:
        logger.info("No unread candidate messages found")
        return

    processed_count = 0
    skipped_count = 0
    error_count = 0

    logger.info("Found %s message(s) | mailbox=%s", len(messages), mailbox_email or "-")

    for original_message in messages:
        message_id = original_message.get("id")

        try:
            result = process_single_message(
                service,
                original_message,
                processed_label_id,
                skipped_label_id,
                mailbox_email=mailbox_email,
                source=source,
            )

            if result == "processed":
                processed_count += 1
            else:
                skipped_count += 1

            time.sleep(DELAY_BETWEEN_EMAILS_SECONDS)

        except requests.HTTPError as e:
            response_body = e.response.text if e.response is not None else ""
            logger.exception(
                "HTTP error while processing message | id=%s | response_body=%r",
                message_id,
                response_body,
            )
            error_count += 1

        except HttpError as e:
            logger.exception("Gmail API error while processing message | id=%s | error=%r", message_id, e)
            error_count += 1

        except Exception as e:
            logger.exception("Unexpected error while processing message | id=%s | error=%r", message_id, e)
            error_count += 1

    logger.info(
        "Cycle finished | mailbox=%s | processed=%s | skipped=%s | errors=%s",
        mailbox_email or "-",
        processed_count,
        skipped_count,
        error_count,
    )


def _build_support_source(client_name: str, mailbox_email: str) -> str:
    candidate = (client_name or mailbox_email or "unknown").strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "_", candidate).strip("_")
    return f"gmail:{normalized or 'unknown'}"


def process_db_mailbox(mailbox: GmailMailbox) -> None:
    label_processed = mailbox.processed_label or PROCESSED_LABEL_NAME
    label_skipped = mailbox.skipped_label or SKIPPED_LABEL_NAME
    source = _build_support_source(mailbox.client_name, mailbox.mailbox_email)

    service = get_db_mailbox_gmail_service(mailbox)
    processed_label_id = ensure_label(service, label_processed)
    skipped_label_id = ensure_label(service, label_skipped)

    process_inbox(
        service,
        processed_label_id,
        skipped_label_id,
        processed_label_name=label_processed,
        skipped_label_name=label_skipped,
        mailbox_email=mailbox.mailbox_email,
        source=source,
    )


def main():
    if not DEMO_API_KEY:
        raise RuntimeError("Missing DEMO_API_KEY in .env")

    legacy_service = None
    legacy_processed_label_id = None
    legacy_skipped_label_id = None
    legacy_token_error_logged = False

    logger.info(
        "Worker started | default_processed_label=%s | default_skipped_label=%s | poll_interval=%ss",
        PROCESSED_LABEL_NAME,
        SKIPPED_LABEL_NAME,
        POLL_INTERVAL_SECONDS,
    )
    logger.info("Support reply endpoint | url=%s", SUPPORT_REPLY_ENDPOINT)

    while True:
        cycle_started_at = time.time()

        try:
            active_mailboxes = load_active_gmail_mailboxes()

            if active_mailboxes:
                logger.info("Loaded %s active mailbox(es) from DB", len(active_mailboxes))
                for mailbox in active_mailboxes:
                    try:
                        process_db_mailbox(mailbox)
                    except HttpError as e:
                        logger.exception(
                            "Gmail API error for DB mailbox | id=%s | mailbox=%s | error=%r",
                            mailbox.id,
                            mailbox.mailbox_email,
                            e,
                        )
                    except Exception as e:
                        logger.exception(
                            "Failed DB mailbox cycle | id=%s | mailbox=%s | error=%r",
                            mailbox.id,
                            mailbox.mailbox_email,
                            e,
                        )
            else:
                try:
                    if legacy_service is None:
                        logger.info("No active DB mailboxes found; using legacy token.json fallback")
                        legacy_service = get_legacy_gmail_service()
                        legacy_processed_label_id = ensure_label(legacy_service, PROCESSED_LABEL_NAME)
                        legacy_skipped_label_id = ensure_label(legacy_service, SKIPPED_LABEL_NAME)
                        legacy_token_error_logged = False

                    process_inbox(
                        legacy_service,
                        legacy_processed_label_id,
                        legacy_skipped_label_id,
                        processed_label_name=PROCESSED_LABEL_NAME,
                        skipped_label_name=SKIPPED_LABEL_NAME,
                        mailbox_email=MY_EMAIL,
                        source="gmail",
                    )
                except RefreshError:
                    legacy_service = None
                    legacy_processed_label_id = None
                    legacy_skipped_label_id = None
                    if not legacy_token_error_logged:
                        logger.error(
                            "Legacy Gmail token.json is expired or revoked. Re-run Gmail auth to recreate token.json."
                        )
                        legacy_token_error_logged = True

        except HttpError as e:
            logger.exception("Worker cycle Gmail API error: %r", e)

            # Legacy fallback session can expire; force re-auth for next cycle.
            legacy_service = None
            legacy_processed_label_id = None
            legacy_skipped_label_id = None

        except Exception as e:
            logger.exception("Worker loop error: %r", e)

            # Keep legacy fallback resilient if its local session failed.
            legacy_service = None
            legacy_processed_label_id = None
            legacy_skipped_label_id = None

        elapsed = time.time() - cycle_started_at
        sleep_for = max(0, POLL_INTERVAL_SECONDS - elapsed)
        logger.info("Cycle complete | sleeping_for=%.2fs", sleep_for)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
