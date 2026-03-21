import base64
import logging
import os
import re
import time
from email.mime.text import MIMEText

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

FASTAPI_GENERATE_URL = os.getenv("FASTAPI_GENERATE_URL", "http://127.0.0.1:8000/generate")
API_KEY = os.getenv("API_KEY") or os.getenv("DEMO_API_KEY")
PROCESSED_LABEL_NAME = os.getenv("PROCESSED_LABEL_NAME", "AI Draft Ready")
SKIPPED_LABEL_NAME = os.getenv("SKIPPED_LABEL_NAME", "AI Skipped")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
MAX_RESULTS_PER_CYCLE = int(os.getenv("MAX_RESULTS_PER_CYCLE", "10"))
DELAY_BETWEEN_EMAILS_SECONDS = float(os.getenv("DELAY_BETWEEN_EMAILS_SECONDS", "1"))


def gmail_auth():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing Gmail credentials...")
            creds.refresh(Request())
        else:
            logging.info("Starting Gmail OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    logging.info("Gmail authentication successful.")

    return build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False
    )


def get_or_create_label(service, label_name):
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])

    for label in labels:
        if label["name"] == label_name:
            logging.info("Using existing Gmail label: %s", label_name)
            return label["id"]

    new_label = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }

    created_label = service.users().labels().create(
        userId="me",
        body=new_label
    ).execute()

    logging.info("Created Gmail label: %s", label_name)
    return created_label["id"]


def has_label(message, label_id):
    return label_id in message.get("labelIds", [])


def add_label_to_message(service, message_id, label_id):
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": [label_id]}
    ).execute()


def get_candidate_messages(service, max_results=10):
    query = f'in:inbox is:unread -label:"{PROCESSED_LABEL_NAME}" -label:"{SKIPPED_LABEL_NAME}"'

    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results
    ).execute()

    message_refs = results.get("messages", [])
    messages = []

    for msg in message_refs:
        full_message = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="full"
        ).execute()
        messages.append(full_message)

    return messages


def extract_headers(payload):
    headers = payload.get("headers", [])
    subject = ""
    from_email = ""
    message_id_header = ""
    list_unsubscribe = ""

    for header in headers:
        name = header.get("name", "")
        value = header.get("value", "")

        if name.lower() == "subject":
            subject = value
        elif name.lower() == "from":
            from_email = value
        elif name.lower() == "message-id":
            message_id_header = value
        elif name.lower() == "list-unsubscribe":
            list_unsubscribe = value

    return subject, from_email, message_id_header, list_unsubscribe


def decode_base64_message_data(data):
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(data.encode("utf-8"))
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def extract_plain_text_from_part(part):
    data = part.get("body", {}).get("data")
    return decode_base64_message_data(data)


def strip_html(html):
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"(?is)<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_plain_text(payload):
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        return extract_plain_text_from_part(payload)

    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                text = extract_plain_text_from_part(part)
                if text.strip():
                    return text

        for part in payload["parts"]:
            if "parts" in part:
                text = extract_plain_text(part)
                if text.strip():
                    return text

        for part in payload["parts"]:
            if part.get("mimeType") == "text/html":
                html = extract_plain_text_from_part(part)
                if html.strip():
                    return strip_html(html)

    data = payload.get("body", {}).get("data")
    if data:
        text = decode_base64_message_data(data)
        if "<html" in text.lower() or "<body" in text.lower():
            return strip_html(text)
        return text

    return ""


def count_links(text):
    return len(re.findall(r"https?://|www\.", text, flags=re.IGNORECASE))


def looks_like_non_customer_email(from_email, subject, body, list_unsubscribe):
    from_lower = from_email.lower()
    subject_lower = subject.lower()
    body_lower = body.lower()

    blocked_sender_terms = [
        "no-reply",
        "noreply",
        "marketing",
        "newsletter",
        "mailer",
        "notifications",
        "promo",
        "offers",
        "deals",
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
        "celebrate",
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
        "ta wiadomość e-mail została wysłana automatycznie",
        "manage preferences",
        "update your preferences",
        "click here",
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
        "logowanie",
        "potwierdzenie",
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


def looks_like_customer_email(subject, body):
    body_lower = body.lower()
    subject_lower = subject.lower()

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


def generate_ai_reply(email_text):
    if not API_KEY:
        raise ValueError("Missing API_KEY/DEMO_API_KEY environment variable.")

    payload = {
        "email": email_text,
        "source": "gmail_worker"
    }

    headers = {
        "x-api-key": API_KEY
    }

    response = requests.post(
        FASTAPI_GENERATE_URL,
        json=payload,
        headers=headers,
        timeout=60
    )
    response.raise_for_status()

    data = response.json()
    return data["result"]["reply"]


def create_draft_reply(service, original_message, ai_reply_text):
    thread_id = original_message["threadId"]
    payload = original_message["payload"]

    subject, from_email, message_id_header, _ = extract_headers(payload)

    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    elif not subject:
        subject = "Re: Your message"

    message = MIMEText(ai_reply_text, "plain", "utf-8")
    message["to"] = from_email
    message["subject"] = subject

    if message_id_header:
        message["In-Reply-To"] = message_id_header
        message["References"] = message_id_header

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft_body = {
        "message": {
            "raw": raw_message,
            "threadId": thread_id
        }
    }

    draft = service.users().drafts().create(
        userId="me",
        body=draft_body
    ).execute()

    return draft


def process_single_message(service, original_message, processed_label_id, skipped_label_id):
    message_id = original_message["id"]

    if has_label(original_message, processed_label_id):
        logging.info("Skipping message %s: already processed.", message_id)
        return "skipped"

    if has_label(original_message, skipped_label_id):
        logging.info("Skipping message %s: already marked as skipped.", message_id)
        return "skipped"

    payload = original_message["payload"]
    subject, from_email, _, list_unsubscribe = extract_headers(payload)
    email_text = extract_plain_text(payload)

    logging.info("Inspecting message %s", message_id)
    logging.info("From: %s", from_email)
    logging.info("Subject: %s", subject)

    if not email_text.strip():
        logging.info("Skipping message %s: empty body.", message_id)
        add_label_to_message(service, message_id, skipped_label_id)
        logging.info("Added label '%s' to message %s", SKIPPED_LABEL_NAME, message_id)
        return "skipped"

    if looks_like_non_customer_email(from_email, subject, email_text, list_unsubscribe):
        logging.info("Skipping message %s: not a customer support email.", message_id)
        add_label_to_message(service, message_id, skipped_label_id)
        logging.info("Added label '%s' to message %s", SKIPPED_LABEL_NAME, message_id)
        return "skipped"

    if not looks_like_customer_email(subject, email_text):
        logging.info("Skipping message %s: does not look like customer email.", message_id)
        add_label_to_message(service, message_id, skipped_label_id)
        logging.info("Added label '%s' to message %s", SKIPPED_LABEL_NAME, message_id)
        return "skipped"

    logging.info("Accepted message %s for AI processing.", message_id)
    logging.info("Body preview: %s", email_text[:300].replace("\n", " "))

    ai_reply = generate_ai_reply(email_text)
    draft = create_draft_reply(service, original_message, ai_reply)
    add_label_to_message(service, message_id, processed_label_id)

    logging.info("Draft created successfully for message %s. Draft ID: %s", message_id, draft["id"])
    logging.info("Added label '%s' to message %s", PROCESSED_LABEL_NAME, message_id)

    return "processed"


def process_inbox(service, processed_label_id, skipped_label_id):
    logging.info("Checking inbox...")

    messages = get_candidate_messages(service, max_results=MAX_RESULTS_PER_CYCLE)

    if not messages:
        logging.info("No unread messages found.")
        return

    processed_count = 0
    skipped_count = 0
    error_count = 0

    for original_message in messages:
        try:
            result = process_single_message(
                service,
                original_message,
                processed_label_id,
                skipped_label_id
            )

            if result == "processed":
                processed_count += 1
            else:
                skipped_count += 1

            time.sleep(DELAY_BETWEEN_EMAILS_SECONDS)

        except requests.RequestException as e:
            logging.error(
                "Network/API error while processing message %s: %s",
                original_message.get("id"),
                e,
                exc_info=True
            )
            error_count += 1

        except HttpError as e:
            logging.error(
                "Gmail API error while processing message %s: %s",
                original_message.get("id"),
                e,
                exc_info=True
            )
            error_count += 1

        except Exception as e:
            logging.error(
                "Unexpected error while processing message %s: %s",
                original_message.get("id"),
                e,
                exc_info=True
            )
            error_count += 1

    logging.info(
        "Cycle finished. Processed: %s, Skipped: %s, Errors: %s",
        processed_count,
        skipped_count,
        error_count
    )


def run_worker():
    logging.info("Starting Gmail worker...")
    logging.info("FASTAPI_GENERATE_URL=%s", FASTAPI_GENERATE_URL)
    logging.info("PROCESSED_LABEL_NAME=%s", PROCESSED_LABEL_NAME)
    logging.info("POLL_INTERVAL_SECONDS=%s", POLL_INTERVAL_SECONDS)
    logging.info("MAX_RESULTS_PER_CYCLE=%s", MAX_RESULTS_PER_CYCLE)
    logging.info("DELAY_BETWEEN_EMAILS_SECONDS=%s", DELAY_BETWEEN_EMAILS_SECONDS)
    logging.info("SKIPPED_LABEL_NAME=%s", SKIPPED_LABEL_NAME)

    service = gmail_auth()
    processed_label_id = get_or_create_label(service, PROCESSED_LABEL_NAME)
    skipped_label_id = get_or_create_label(service, SKIPPED_LABEL_NAME)

    while True:
        cycle_started_at = time.time()

        try:
            process_inbox(service, processed_label_id, skipped_label_id)
        except HttpError as e:
            logging.error("Worker cycle Gmail API error: %s", e, exc_info=True)

            try:
                logging.info("Re-authenticating Gmail service after API error...")
                service = gmail_auth()
                processed_label_id = get_or_create_label(service, PROCESSED_LABEL_NAME)
                skipped_label_id = get_or_create_label(service, SKIPPED_LABEL_NAME)
            except Exception as reauth_error:
                logging.error("Failed to re-authenticate Gmail service: %s", reauth_error, exc_info=True)

        except Exception as e:
            logging.error("Worker cycle failed: %s", e, exc_info=True)

        elapsed = time.time() - cycle_started_at
        sleep_for = max(0, POLL_INTERVAL_SECONDS - elapsed)

        logging.info("Sleeping for %.2f seconds...", sleep_for)
        time.sleep(sleep_for)


if __name__ == "__main__":
    run_worker()
