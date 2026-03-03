from __future__ import annotations

import time
import uuid
import traceback
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.responses import JSONResponse

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.database.db import init_db, insert_log, fetch_logs
from app.schemas import (
    GenerateRequest,
    GenerateResponse,
    SupportRequest,
    SupportResponse,
)
from app.services.llm import LLMService
from app.web_demo import router as web_demo_router

app = FastAPI(title="Project 03 - AI Support Agent", version="0.1.0")

app.include_router(web_demo_router)

settings = get_settings()
llm = LLMService(settings)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.on_event("startup")
def _startup() -> None:
    init_db()


# Public endpoint for Render healthcheck
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/support/reply", response_model=SupportResponse)
def generate_reply(request_data: SupportRequest, client=Depends(require_api_key)):
    """
    Web demo endpoint (MVP).
    For now returns an echo response that proves:
    - request parsing works
    - API key auth works
    - Swagger/OpenAPI works
    """
    request_id = str(uuid.uuid4())

    return SupportResponse(
        request_id=request_id,
        client=client["name"],
        reply=f"Echo: {request_data.message[:500]}",
        category="OTHER",
        next_step="N/A",
        latency_ms=0,
    )


@app.get("/logs", dependencies=[Depends(require_api_key)])
def logs(
    limit: int = Query(50, ge=1, le=500),
    parse_ok: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
):
    return {"items": fetch_logs(limit=limit, parse_ok=parse_ok, category=category)}


@app.post(
    "/generate",
    response_model=GenerateResponse,
    dependencies=[Depends(require_api_key)],
)
async def generate(req: GenerateRequest, request: Request):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()

    raw_model_output = None
    parse_ok = 1
    error_message = None
    category = reply = next_step = None
    usage = {}

    try:
        out = llm.generate_text(
            email=req.email,
            system=req.system,
            prompt_template=req.prompt_template,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        raw_model_output = out["raw_text"]
        parsed = out["parsed"]
        usage = out.get("usage", {}) or {}

        category = parsed.get("category")
        reply = parsed.get("reply")
        next_step = parsed.get("next_step")

        if not isinstance(category, str) or not isinstance(reply, str) or not isinstance(next_step, str):
            parse_ok = 0
            error_message = "Model returned invalid schema types."

    except Exception as e:
        parse_ok = 0
        error_message = str(e)
        parsed = {
            "category": "OTHER",
            "reply": "Sorry — we couldn't generate a response right now.",
            "next_step": "Please try again later or handle this message manually.",
        }
        category, reply, next_step = parsed["category"], parsed["reply"], parsed["next_step"]

    latency_ms = int((time.perf_counter() - start) * 1000)

    insert_log(
        request_id=request_id,
        created_at=now_utc_iso(),
        source=req.source,
        customer_from=None,
        subject=None,
        category=category,
        reply=reply,
        next_step=next_step,
        raw_email=req.email,
        raw_model_output=raw_model_output,
        parse_ok=parse_ok,
        error_message=error_message,
    )

    if parse_ok == 0 and error_message:
        raise HTTPException(status_code=502, detail=error_message or "Generation failed")

    return {
        "request_id": request_id,
        "result": {"category": category, "reply": reply, "next_step": next_step},
        "usage": usage,
        "latency_ms": latency_ms,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    # Helpful in dev + Render logs (doesn't leak secrets unless you print them elsewhere)
    print("UNHANDLED EXCEPTION:", request.method, request.url.path)
    traceback.print_exc()

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": request_id,
            "path": str(request.url.path),
        },
    )