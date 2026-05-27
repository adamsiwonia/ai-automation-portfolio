from __future__ import annotations

import contextlib
import io
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.auth import require_api_key
from app.core.security import hash_api_key


RAW_API_KEY = "sk_live_smoke_raw_api_key_DO_NOT_PRINT"
HMAC_SECRET = "smoke_hmac_secret_DO_NOT_PRINT"
AUTH_ENV_KEYS = ("API_KEY_HMAC_SECRET", "DEMO_API_KEY", "API_KEY")


class RequestStub:
    def __init__(self) -> None:
        self.state = SimpleNamespace()


def _build_db(key_hash: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE api_keys (
            key_hash TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_used_at TEXT,
            daily_limit INTEGER
        )
        """
    )
    conn.execute(
        """
        INSERT INTO api_keys (key_hash, name, is_active, daily_limit)
        VALUES (?, ?, 1, ?)
        """,
        (key_hash, "smoke-client", 100),
    )
    conn.commit()
    return conn


def _capture_auth_output(
    conn: sqlite3.Connection,
    *,
    x_api_key: str | None,
    authorization: str | None,
) -> str:
    stdout = io.StringIO()
    stderr = io.StringIO()
    request = RequestStub()

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        client = require_api_key(
            request=request,
            x_api_key=x_api_key,
            authorization=authorization,
            db=conn,
        )

    assert client["name"] == "smoke-client"
    return stdout.getvalue() + stderr.getvalue()


def _restore_env(previous: dict[str, str | None]) -> None:
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _assert_secret_free(output: str, *, key_hash: str) -> None:
    assert RAW_API_KEY not in output, "raw API key was printed"
    assert HMAC_SECRET not in output, "HMAC secret was printed"
    assert key_hash not in output, "derived API key hash was printed"


def main() -> None:
    key_hash = hash_api_key(RAW_API_KEY, HMAC_SECRET)
    previous = {name: os.environ.get(name) for name in AUTH_ENV_KEYS}
    try:
        os.environ["API_KEY_HMAC_SECRET"] = HMAC_SECRET
        os.environ.pop("DEMO_API_KEY", None)
        os.environ.pop("API_KEY", None)

        conn = _build_db(key_hash)
        try:
            x_api_key_output = _capture_auth_output(
                conn,
                x_api_key=RAW_API_KEY,
                authorization=None,
            )
            bearer_output = _capture_auth_output(
                conn,
                x_api_key=None,
                authorization=f"Bearer {RAW_API_KEY}",
            )
        finally:
            conn.close()
    finally:
        _restore_env(previous)

    output = f"{x_api_key_output}\n{bearer_output}"
    assert "api_key source: x-api-key" in x_api_key_output
    assert "api_key source: authorization-bearer" in bearer_output
    assert "extracted api_key length:" in output
    _assert_secret_free(output, key_hash=key_hash)

    print("PASS auth logging smoke check: raw keys and derived secrets were not printed.")


if __name__ == "__main__":
    main()
