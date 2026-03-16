import os.path
import base64
import requests
import os


from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service


def extract_plain_text(payload):
    mime_type = payload.get("mimeType")
    body = payload.get("body", {})
    data = body.get("data")

    if mime_type == "text/plain" and data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    for part in payload.get("parts", []):
        text = extract_plain_text(part)
        if text:
            return text

    return ""


def get_message_details(service, message_id):
    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    email_headers = msg["payload"].get("headers", [])

    subject = next((h["value"] for h in email_headers if h["name"].lower() == "subject"), "")
    sender = next((h["value"] for h in email_headers if h["name"].lower() == "from"), "")
    thread_id = msg.get("threadId")
    body_text = extract_plain_text(msg["payload"])

    return {
        "id": msg["id"],
        "thread_id": thread_id,
        "subject": subject,
        "from": sender,
        "body_text": body_text,
    }



def generate_reply_via_project03(email_text):
    api_key = os.getenv("DEMO_API_KEY")

    if not api_key:
        raise ValueError("No DEMO_API_KEY in .env")

    response = requests.post(
        "http://127.0.0.1:8000/support/reply",
        json={
            "message": email_text,
            "source": "gmail"
        },
        headers={"X-API-Key": api_key},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()
    data = response.json()
    return data.get("reply", "No reply generated")

def main():
    service = get_gmail_service()

    results = service.users().messages().list(
        userId="me",
        maxResults=5
    ).execute()

    messages = results.get("messages", [])

    if not messages:
        print("Brak wiadomości.")
        return

    first_id = messages[0]["id"]
    details = get_message_details(service, first_id)

    print("SUBJECT:", details["subject"])
    print("FROM:", details["from"])
    print("THREAD ID:", details["thread_id"])
    print("\nBODY:\n")
    print(details["body_text"][:1500])

    print("\n--- SENDING TO PROJECT 03 ---\n")
    ai_result = generate_reply_via_project03(details["body_text"])

    print("AI RESULT:\n")
    print(ai_result)


if __name__ == "__main__":
    main()