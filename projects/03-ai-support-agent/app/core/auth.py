import os
from datetime import datetime, timezone
from fastapi import Depends, Header, HTTPException, status, Request
from app.database.db import get_db
from app.core.security import hash_api_key


def _extract_api_key(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

    return None


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db = Depends(get_db),
):
    api_key = _extract_api_key(x_api_key, authorization)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key"
        )

    secret = os.getenv("API_KEY_HMAC_SECRET")
    if not secret:
        raise RuntimeError("API_KEY_HMAC_SECRET not set")

    key_hash = hash_api_key(api_key, secret)

    row = db.execute(
        "SELECT key_hash, name, is_active, daily_limit FROM api_keys WHERE key_hash = ?",
        (key_hash,)
    ).fetchone()

    if not row or row["is_active"] != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # update last_used_at
    db.execute(
        "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
        (datetime.now(timezone.utc).isoformat(), key_hash)
    )
    db.commit()

    request.state.client_name = row["name"]

    return row