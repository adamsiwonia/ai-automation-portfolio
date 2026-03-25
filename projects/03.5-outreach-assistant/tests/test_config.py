from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from app.core import config


def _clear_google_env(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GOOGLE_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("GOOGLE_SHEET_NAME", raising=False)


@pytest.fixture
def tmp_path() -> Path:
    base = Path("tests")
    path = base / f".tmp_pytest_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_get_settings_resolves_relative_google_credentials_from_project_root(
    monkeypatch, tmp_path: Path
) -> None:
    test_root = tmp_path
    creds_file = test_root / "credentials.json"
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(config, "PROJECT_ROOT", test_root)
    monkeypatch.setattr(
        config,
        "_DOTENV_VALUES",
        {
            "GOOGLE_APPLICATION_CREDENTIALS": "credentials.json",
            "GOOGLE_SPREADSHEET_ID": "sheet_123",
            "GOOGLE_SHEET_NAME": "TEST",
        },
    )
    _clear_google_env(monkeypatch)

    settings = config.get_settings()

    assert settings.google_credentials_path == creds_file
    assert settings.google_spreadsheet_id == "sheet_123"
    assert settings.google_sheet_name == "TEST"
    assert settings.google_ready is True


def test_get_settings_accepts_absolute_google_credentials_path(
    monkeypatch, tmp_path: Path
) -> None:
    test_root = tmp_path
    creds_file = (test_root / "credentials.json").resolve()
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(config, "PROJECT_ROOT", test_root)
    monkeypatch.setattr(
        config,
        "_DOTENV_VALUES",
        {
            "GOOGLE_APPLICATION_CREDENTIALS": str(creds_file),
            "GOOGLE_SPREADSHEET_ID": "sheet_abs",
        },
    )
    _clear_google_env(monkeypatch)

    settings = config.get_settings()

    assert settings.google_credentials_path == creds_file
    assert settings.google_spreadsheet_id == "sheet_abs"
    assert settings.google_ready is True


def test_google_not_ready_when_spreadsheet_id_missing(monkeypatch) -> None:
    test_root = Path.cwd()
    creds_file = test_root / "credentials.json"

    monkeypatch.setattr(config, "PROJECT_ROOT", test_root)
    monkeypatch.setattr(
        config,
        "_DOTENV_VALUES",
        {"GOOGLE_APPLICATION_CREDENTIALS": "credentials.json"},
    )
    _clear_google_env(monkeypatch)

    settings = config.get_settings()

    assert settings.google_credentials_path == creds_file
    assert settings.google_spreadsheet_id is None
    assert settings.google_ready is False


def test_google_not_ready_when_credentials_path_is_set_but_file_missing(
    monkeypatch, tmp_path: Path
) -> None:
    test_root = tmp_path
    missing_creds_file = test_root / "missing_credentials.json"

    monkeypatch.setattr(config, "PROJECT_ROOT", test_root)
    monkeypatch.setattr(
        config,
        "_DOTENV_VALUES",
        {
            "GOOGLE_APPLICATION_CREDENTIALS": "missing_credentials.json",
            "GOOGLE_SPREADSHEET_ID": "sheet_missing_creds",
        },
    )
    _clear_google_env(monkeypatch)

    settings = config.get_settings()

    assert settings.google_credentials_path == missing_creds_file
    assert settings.google_spreadsheet_id == "sheet_missing_creds"
    assert settings.google_ready is False


def test_validate_sheets_config_distinguishes_missing_values(monkeypatch) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", Path.cwd())
    monkeypatch.setattr(config, "_DOTENV_VALUES", {})
    _clear_google_env(monkeypatch)

    settings = config.get_settings()
    result = config.validate_sheets_config(settings)

    assert result.ok is False
    assert "GOOGLE_SPREADSHEET_ID is missing." in result.errors
    assert "GOOGLE_APPLICATION_CREDENTIALS is missing." in result.errors


def test_validate_sheets_config_distinguishes_empty_values(monkeypatch) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", Path.cwd())
    monkeypatch.setattr(
        config,
        "_DOTENV_VALUES",
        {
            "GOOGLE_SPREADSHEET_ID": "",
            "GOOGLE_APPLICATION_CREDENTIALS": "",
        },
    )
    _clear_google_env(monkeypatch)

    settings = config.get_settings()
    result = config.validate_sheets_config(settings)

    assert result.ok is False
    assert "GOOGLE_SPREADSHEET_ID is empty." in result.errors
    assert "GOOGLE_APPLICATION_CREDENTIALS is empty." in result.errors


def test_validate_sheets_config_reports_invalid_credentials_path(monkeypatch) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", Path.cwd())
    monkeypatch.setattr(
        config,
        "_DOTENV_VALUES",
        {
            "GOOGLE_SPREADSHEET_ID": "sheet123",
            "GOOGLE_APPLICATION_CREDENTIALS": "missing_creds.json",
        },
    )
    _clear_google_env(monkeypatch)

    settings = config.get_settings()
    result = config.validate_sheets_config(settings)

    assert result.ok is False
    assert any("does not exist" in error for error in result.errors)


def test_validate_gmail_config_reports_missing_and_empty(monkeypatch) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", Path.cwd())
    monkeypatch.setattr(config, "_DOTENV_VALUES", {"GMAIL_OAUTH_CLIENT_SECRETS": ""})
    monkeypatch.delenv("GMAIL_OAUTH_CLIENT_SECRETS", raising=False)
    monkeypatch.delenv("GMAIL_TOKEN_PATH", raising=False)

    settings = config.get_settings()
    result = config.validate_gmail_config(settings)

    assert result.ok is False
    assert "GMAIL_OAUTH_CLIENT_SECRETS is empty." in result.errors
    assert any("GMAIL_TOKEN_PATH" in warning for warning in result.warnings)
