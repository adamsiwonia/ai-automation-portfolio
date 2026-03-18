import os
from datetime import datetime, timezone
from app.core.security import generate_api_key, hash_api_key
from app.database.db import get_db

def main():
    name = input("Client name: ")

    secret = os.getenv("API_KEY_HMAC_SECRET")
    if not secret:
        raise RuntimeError("API_KEY_HMAC_SECRET not set")

    api_key = generate_api_key()
    key_hash = hash_api_key(api_key, secret)

    db = next(get_db())

    db.execute(
        "INSERT INTO api_keys (key_hash, name, created_at) VALUES (?, ?, ?)",
        (key_hash, name, datetime.now(timezone.utc).isoformat())
    )
    db.commit()

    print("\nAPI KEY (show only once):")
    print(api_key)


if __name__ == "__main__":
    main()