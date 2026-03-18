import time
import requests

CLOUD_RUN_URL = "https://ai-support-agent-978690358716.europe-west1.run.app"
API_KEY = "twoj_bardzo_dlugi_losowy_klucz_123456654321" 
ENDPOINT = f"{CLOUD_RUN_URL}/support/reply"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}


def test_request():
    payload = {
        "source": "gmail",
        "message": "Hi, where is my order?",
    }

    response = requests.post(ENDPOINT, json=payload, headers=HEADERS, timeout=60)
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)


if __name__ == "__main__":
    while True:
        test_request()
        time.sleep(60)