from __future__ import annotations

import contextlib
import io
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.llm import LLMService
from app.web_demo import demo_page


DEMO_API_KEY = "demo_secret_DO_NOT_PRINT"
LEGACY_API_KEY = "legacy_secret_DO_NOT_PRINT"
CUSTOMER_EMAIL = "CUSTOMER_EMAIL_BODY_DO_NOT_PRINT order #12345 jane@example.com"
MODEL_OUTPUT = "MODEL_OUTPUT_DO_NOT_PRINT"


class FakeResponses:
    def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(
            output_text=(
                '{"category":"OTHER",'
                f'"reply":"{MODEL_OUTPUT}",'
                '"next_step":"Review manually."}'
            ),
            usage=SimpleNamespace(input_tokens=11, output_tokens=7, total_tokens=18),
        )


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def _restore_env(previous: dict[str, str | None]) -> None:
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _capture_llm_output() -> str:
    service = LLMService.__new__(LLMService)
    service.client = FakeClient()
    service.model = "security-smoke-model"

    stdout = io.StringIO()
    stderr = io.StringIO()
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)

    logger = logging.getLogger("app.services.llm")
    previous_level = logger.level
    previous_propagate = logger.propagate
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = service.generate_text(
                email=CUSTOMER_EMAIL,
                system=None,
                prompt_template=None,
                temperature=0.2,
                max_tokens=300,
            )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    assert result["parsed"]["reply"] == MODEL_OUTPUT
    return stdout.getvalue() + stderr.getvalue() + log_stream.getvalue()


def main() -> None:
    previous = {
        "DEMO_API_KEY": os.environ.get("DEMO_API_KEY"),
        "API_KEY": os.environ.get("API_KEY"),
    }
    try:
        os.environ["DEMO_API_KEY"] = DEMO_API_KEY
        os.environ["API_KEY"] = LEGACY_API_KEY

        body = demo_page().body.decode("utf-8")
    finally:
        _restore_env(previous)

    assert DEMO_API_KEY not in body, "DEMO_API_KEY was rendered into browser HTML"
    assert LEGACY_API_KEY not in body, "API_KEY was rendered into browser HTML"
    assert "__CLIENT_API_KEY__" not in body, "client API key placeholder remains in HTML"
    assert 'id="apiKey"' in body, "demo API key input is missing"

    captured = _capture_llm_output()
    forbidden = [DEMO_API_KEY, LEGACY_API_KEY, CUSTOMER_EMAIL, MODEL_OUTPUT]
    for value in forbidden:
        assert value not in captured, f"sensitive value was printed or logged: {value}"

    assert "email_chars=" in captured
    assert "output_chars=" in captured
    print("PASS demo security smoke check: secrets and customer content were not printed.")


if __name__ == "__main__":
    main()
