import base64
import os
import re
import time
from email.mime.text import MIMEText
from email.utils import parseaddr

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

CLOUD_RUN_URL = "https://ai-support-agent-978690358716.europe-west1.run.app"
SUPPORT_REPLY_ENDPOINT = f"{CLOUD_RUN_URL}/support/reply"

DEMO_API_KEY = "twoj_bardzo_dlugi_losowy_klucz_123456654321"
POLL_INTERVAL_SECONDS = 60
MAX_RESULTS_PER_CYCLE = 10
DELAY_BETWEEN_EMAILS_SECONDS = 1.0

PROCESSED_LABEL_NAME = "AI_PROCESSED"
SKIPPED_LABEL_NAME = "AI_SKIPPED"

MAX_MESSAGE_CHARS = 12000


def get_gmail_service():
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds:
        raise RuntimeError("Missing token.json. Re-run Gmail auth first.")

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

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


def get_candidate_messages(service, max_results: int = 10) -> list[dict]:
    query = (
        f'in:inbox is:unread '
        f'-label:"{PROCESSED_LABEL_NAME}" '
        f'-label:"{SKIPPED_LABEL_NAME}"'
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


def call_support_agent(message_text: str) -> dict:
    headers = {
        "X-API-Key": DEMO_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "source": "gmail",
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
):
    message_id = original_message["id"]

    if has_label(original_message, processed_label_id):
        print(f"Skipping message {message_id}: already processed.")
        return "skipped"

    if has_label(original_message, skipped_label_id):
        print(f"Skipping message {message_id}: already marked as skipped.")
        return "skipped"

    message_data = read_message(service, original_message)

    print(f"\n--- Inspecting message {message_data['id']} ---")
    print("From:", message_data["from_email"])
    print("Subject:", message_data["subject"])

    if not message_data["from_email"]:
        print("Skipping: missing sender.")
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    body = normalize_message_body(message_data["body"])
    if not body:
        print("Skipping: empty body after normalization.")
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    if looks_like_non_customer_email(
        message_data["from_email"],
        message_data["subject"],
        body,
        message_data["list_unsubscribe"],
    ):
        print("Skipping: looks like marketing / transactional / automated email.")
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    if not looks_like_customer_email(message_data["subject"], body):
        print("Skipping: does not look like customer support email.")
        add_label_to_message(service, message_id, skipped_label_id)
        return "skipped"

    print("Accepted for AI processing.")
    print("Body preview:", body[:300])

    result = call_support_agent(body)

    reply_text = result.get("reply", "").strip()
    category = result.get("category", "")
    next_step = result.get("next_step", "")

    print("Category:", category)
    print("Next step:", next_step)
    print("Reply:", reply_text)

    if not reply_text:
        print("No reply returned, marking as skipped.")
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
    print("Draft created and message marked as processed.")
    return "processed"


def process_inbox(service, processed_label_id: str, skipped_label_id: str):
    print("Checking inbox...")

    messages = get_candidate_messages(service, max_results=MAX_RESULTS_PER_CYCLE)

    if not messages:
        print("No unread candidate messages found.")
        return

    processed_count = 0
    skipped_count = 0
    error_count = 0

    print(f"Found {len(messages)} message(s).")

    for original_message in messages:
        try:
            result = process_single_message(
                service,
                original_message,
                processed_label_id,
                skipped_label_id,
            )

            if result == "processed":
                processed_count += 1
            else:
                skipped_count += 1

            time.sleep(DELAY_BETWEEN_EMAILS_SECONDS)

        except requests.HTTPError as e:
            print(f"HTTP error while processing message {original_message.get('id')}: {e}")
            if e.response is not None:
                print("Response body:", e.response.text)
            error_count += 1

        except HttpError as e:
            print(f"Gmail API error while processing message {original_message.get('id')}: {repr(e)}")
            error_count += 1

        except Exception as e:
            print(f"Unexpected error while processing message {original_message.get('id')}: {repr(e)}")
            error_count += 1

    print(
        f"Cycle finished. Processed: {processed_count}, "
        f"Skipped: {skipped_count}, Errors: {error_count}"
    )


def main():
    service = get_gmail_service()
    processed_label_id = ensure_label(service, PROCESSED_LABEL_NAME)
    skipped_label_id = ensure_label(service, SKIPPED_LABEL_NAME)

    print("Worker started.")
    print("Processed label ID:", processed_label_id)
    print("Skipped label ID:", skipped_label_id)
    print("Poll interval:", POLL_INTERVAL_SECONDS)

    while True:
        cycle_started_at = time.time()

        try:
            process_inbox(service, processed_label_id, skipped_label_id)
        except HttpError as e:
            print(f"Worker cycle Gmail API error: {repr(e)}")
            try:
                print("Re-authenticating Gmail service after API error...")
                service = get_gmail_service()
                processed_label_id = ensure_label(service, PROCESSED_LABEL_NAME)
                skipped_label_id = ensure_label(service, SKIPPED_LABEL_NAME)
            except Exception as reauth_error:
                print(f"Failed to re-authenticate Gmail service: {repr(reauth_error)}")
        except Exception as e:
            print(f"Worker loop error: {repr(e)}")

        elapsed = time.time() - cycle_started_at
        sleep_for = max(0, POLL_INTERVAL_SECONDS - elapsed)
        print(f"Sleeping for {sleep_for:.2f} seconds...")
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()