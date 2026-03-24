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
    """Stateless fallback for demo/local mode via env keys."""
    demo_key = (os.getenv("DEMO_API_KEY") or "").strip() or None
    legacy_key = (os.getenv("API_KEY") or "").strip() or None
    print("DEBUG auth -> DEMO_API_KEY loaded:", bool(demo_key))
    print("DEBUG auth -> API_KEY loaded:", bool(legacy_key))

    if demo_key and api_key == demo_key:
        print("DEBUG auth -> DEMO fallback matched")
        request.state.client_name = "demo-env-key"
        return {"name": "demo-env-key", "is_active": 1, "mode": "env"}

    if legacy_key and api_key == legacy_key:
        print("DEBUG auth -> API_KEY fallback matched")
        request.state.client_name = "legacy-env-key"
        return {"name": "legacy-env-key", "is_active": 1, "mode": "env"}

    print("DEBUG auth -> DEMO fallback did not match")
    return None


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    db=Depends(get_db),
):
    api_key = _extract_api_key(x_api_key, authorization)

    print("DEBUG auth -> extracted api_key present:", bool(api_key))
    print("DEBUG auth -> extracted api_key value:", api_key)
    print("DEBUG auth -> API_KEY_HMAC_SECRET loaded:", bool(os.getenv("API_KEY_HMAC_SECRET")))
    print("DEBUG auth -> DEMO_API_KEY loaded:", bool(os.getenv("DEMO_API_KEY")))
    print("DEBUG auth -> API_KEY loaded:", bool(os.getenv("API_KEY")))

    if not api_key:
        print("DEBUG auth -> missing API key")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    # 1) Try DB-based auth (production mode)
    secret = os.getenv("API_KEY_HMAC_SECRET")
    if secret:
        try:
            key_hash = hash_api_key(api_key, secret)
            print("DEBUG auth -> computed key_hash:", key_hash)

            row = db.execute(
                "SELECT key_hash, name, is_active, daily_limit FROM api_keys WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()

            print("DEBUG auth -> db row found:", row is not None)
            if row:
                print("DEBUG auth -> row name:", row["name"])
                print("DEBUG auth -> row is_active:", row["is_active"])
                print("DEBUG auth -> row daily_limit:", row["daily_limit"])

            if row and row["is_active"] == 1:
                # update last_used_at (best-effort)
                try:
                    db.execute(
                        "UPDATE api_keys SET last_used_at = ? WHERE key_hash = ?",
                        (datetime.now(timezone.utc).isoformat(), key_hash),
                    )
                    db.commit()
                    print("DEBUG auth -> last_used_at updated")
                except Exception as update_exc:
                    print("DEBUG auth -> last_used_at update failed:", repr(update_exc))
                    # Don't block requests if last_used_at update fails
                    pass

                request.state.client_name = row["name"]
                print("DEBUG auth -> DB auth matched")
                return row

            if row and row["is_active"] != 1:
                print("DEBUG auth -> row found but inactive")

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as db_exc:
            print("DEBUG auth -> sqlite error during DB auth:", repr(db_exc))
            # DB missing / reset / table not present → fall back to demo key
            pass
        except Exception as exc:
            print("DEBUG auth -> unexpected error during DB auth:", repr(exc))
            # Any unexpected auth error → fall back to demo key (demo friendliness)
            pass
    else:
        print("DEBUG auth -> API_KEY_HMAC_SECRET missing, skipping DB auth")

    # 2) Fallback: DEMO_API_KEY (stateless) — perfect for Render free plan
    print("DEBUG auth -> trying DEMO fallback")
    demo_row = _auth_via_demo_key(api_key, request)
    if demo_row:
        return demo_row

    # 3) No valid auth
    print("DEBUG auth -> auth failed")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
