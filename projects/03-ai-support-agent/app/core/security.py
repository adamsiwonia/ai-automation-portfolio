import hmac
import hashlib
import secrets

def generate_api_key(prefix: str = "sk_live") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"

def hash_api_key(api_key: str, secret: str) -> str:
    return hmac.new(
        key=secret.encode(),
        msg=api_key.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()