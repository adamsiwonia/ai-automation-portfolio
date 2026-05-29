from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
CONTROL_PATH = BASE_DIR / "control.json"
_LOCK = threading.Lock()
DEFAULT_CONTROL = {"agents_enabled": False, "current_mode": "STOPPED"}


def ensure_control_file() -> None:
    if not CONTROL_PATH.exists():
        write_control(DEFAULT_CONTROL)


def read_control() -> dict[str, Any]:
    ensure_control_file()
    with _LOCK:
        with CONTROL_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)

    return {
        "agents_enabled": bool(data.get("agents_enabled", False)),
        "current_mode": data.get("current_mode", "STOPPED"),
    }


def write_control(data: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "agents_enabled": bool(data.get("agents_enabled", False)),
        "current_mode": data.get("current_mode", "RUNNING" if data.get("agents_enabled") else "STOPPED"),
    }
    with _LOCK:
        CONTROL_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def set_running() -> dict[str, Any]:
    return write_control({"agents_enabled": True, "current_mode": "RUNNING"})


def set_stopped() -> dict[str, Any]:
    return write_control({"agents_enabled": False, "current_mode": "STOPPED"})


def agents_enabled() -> bool:
    return read_control()["agents_enabled"]

