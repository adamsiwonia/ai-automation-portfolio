from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.security import hash_api_key
from app.database.db import get_db


def _extract_api_key(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()

    if authorization and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()

    return None


def _auth_via_demo_key(api_key: str, request: Request) -> dict[str, Any] | None:
    """Stateless fallback for Render free tier: validates against DEMO_API_KEY env var."""
    demo_key = os.getenv("DEMO_API_KEY")
    if demo_key and api_key == demo_key:
        request.state.client_name = "demo-env-key"
        return {"name": "demo-env-key", "is_active": 1, "mode": "env"}
    return None


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db=Depends(get_db),
):
    api_key = _extract_api_key(x_api_key, authorization)

    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    # 1) Try DB-based auth (production mode)
    secret = os.getenv("API_KEY_HMAC_SECRET")
    if secret:
        try:
            key_hash = hash_api_key(api_key, secret)

            row = db.execute(
                "SELECT key_hash, name, is_active, daily_limit FROM api_keys WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()

            if row and row["is_active"] == 1:
                # update last_used_at (best-effort)
                try:
                    db.execute(
                        "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
                        (datetime.now(timezone.utc).isoformat(), key_hash),
                    )
                    db.commit()
                except Exception:
                    # Don't block requests if last_used_at update fails
                    pass

                request.state.client_name = row["name"]
                return row

        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            # DB missing / reset / table not present → fall back to demo key
            pass
        except Exception:
            # Any unexpected auth error → fall back to demo key (demo friendliness)
            pass

    # 2) Fallback: DEMO_API_KEY (stateless) — perfect for Render free plan
    demo_row = _auth_via_demo_key(api_key, request)
    if demo_row:
        return demo_row

    # 3) No valid auth
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")