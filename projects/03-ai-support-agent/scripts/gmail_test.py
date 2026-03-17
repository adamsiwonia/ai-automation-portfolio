import base64
import os
import re
import requests
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]

FASTAPI_GENERATE_URL = "http://127.0.0.1:8000/generate"
PROCESSED_LABEL_NAME = "AI Draft Ready"


def gmail_auth():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_or_create_label(service, label_name):
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])

    for label in labels:
        if label["name"] == label_name:
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

    return created_label["id"]


def has_label(message, label_id):
    label_ids = message.get("labelIds", [])
    return label_id in label_ids


def add_label_to_message(service, message_id, label_id):
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": [label_id]}
    ).execute()


def get_candidate_messages(service, max_results=10):
    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
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


def extract_plain_text_from_part(part):
    data = part.get("body", {}).get("data")
    if not data:
        return ""

    decoded = base64.urlsafe_b64decode(data.encode("UTF-8"))
    return decoded.decode("utf-8", errors="ignore")


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
                return strip_html(html)

    data = payload.get("body", {}).get("data")
    if data:
        decoded = base64.urlsafe_b64decode(data.encode("UTF-8"))
        text = decoded.decode("utf-8", errors="ignore")
        if "<html" in text.lower() or "<body" in text.lower():
            return strip_html(text)
        return text

    return ""


def count_links(text):
    return len(re.findall(r"https?://|www\.", text, flags=re.IGNORECASE))


def looks_like_newsletter(from_email, subject, body, list_unsubscribe):
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
    ]

    blocked_subject_terms = [
        "sale",
        "offer",
        "discount",
        "gift card",
        "newsletter",
        "promotion",
        "promo",
        "missed mother",
    ]

    blocked_body_terms = [
        "unsubscribe",
        "view online",
        "privacy policy",
        "terms and conditions",
        "gift card",
        "buy now",
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
        "zwrot",
        "refund",
        "wymiana",
        "rozmiar",
        "przesyłka",
        "dostawa",
        "zamówienie",
        "nie dotarł",
        "nie dotarły",
    ]

    if len(body.strip()) < 20:
        return False

    if count_links(body) > 3:
        return False

    if "unsubscribe" in body_lower or "view online" in body_lower:
        return False

    if any(term in body_lower for term in customer_signals):
        return True

    if any(term in subject_lower for term in customer_signals):
        return True

    if len(body) < 1200:
        return True

    return False


def generate_ai_reply(email_text):
    payload = {
        "email": email_text,
        "source": "gmail_test"
    }

    api_key = os.getenv("API_KEY")
    if not api_key:
        raise ValueError("Missing API_KEY environment variable.")

    headers = {
        "x-api-key": api_key
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

    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    message = MIMEText(ai_reply_text)
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


def main():
    service = gmail_auth()
    processed_label_id = get_or_create_label(service, PROCESSED_LABEL_NAME)
    messages = get_candidate_messages(service, max_results=10)

    if not messages:
        print("No unread messages found.")
        return

    processed_count = 0
    skipped_count = 0

    for original_message in messages:
        if has_label(original_message, processed_label_id):
            print("\n==============================")
            print("Skipped: already processed.")
            skipped_count += 1
            continue

        payload = original_message["payload"]
        subject, from_email, _, list_unsubscribe = extract_headers(payload)
        email_text = extract_plain_text(payload)

        print("\n==============================")
        print(f"From: {from_email}")
        print(f"Subject: {subject}")

        if not email_text.strip():
            print("Skipped: empty body.")
            skipped_count += 1
            continue

        if looks_like_newsletter(from_email, subject, email_text, list_unsubscribe):
            print("Skipped: looks like newsletter / marketing email.")
            skipped_count += 1
            continue

        if not looks_like_customer_email(subject, email_text):
            print("Skipped: does not look like customer email.")
            skipped_count += 1
            continue

        print("Accepted for AI processing.")
        print(f"Body preview: {email_text[:300]}")

        try:
            ai_reply = generate_ai_reply(email_text)
            print("\n--- AI REPLY ---")
            print(ai_reply)

            draft = create_draft_reply(service, original_message, ai_reply)
            print(f"Draft created successfully. Draft ID: {draft['id']}")

            add_label_to_message(service, original_message["id"], processed_label_id)
            print(f"Added label: {PROCESSED_LABEL_NAME}")

            processed_count += 1

        except Exception as e:
            print(f"Error while processing message: {e}")

    print("\n==============================")
    print(f"Done. Processed: {processed_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
    main()