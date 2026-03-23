from __future__ import annotations

import os
import re
import time
import uuid
import traceback
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.core.auth import require_api_key
from app.core.config import get_settings
from app.database.db import fetch_logs, init_db, insert_log
from app.schemas import (
    GenerateRequest,
    GenerateResponse,
    SupportRequest,
    SupportResponse,
)
from app.services.google_oauth import (
    GoogleOAuthConfigError,
    GoogleOAuthExchangeError,
    GoogleOAuthStateError,
    build_google_auth_url,
    create_oauth_state,
    derive_token_expiry_iso,
    exchange_google_code,
    fetch_gmail_mailbox_email,
    get_google_oauth_config,
    parse_oauth_state,
)
from app.services.llm import LLMService
from app.services.mailboxes import (
    DEFAULT_PROCESSED_LABEL,
    DEFAULT_SKIPPED_LABEL,
    upsert_gmail_mailbox_oauth,
)
from app.web_demo import router as web_demo_router

app = FastAPI(title="Project 03 - AI Support Agent", version="0.1.0")

app.include_router(web_demo_router)

settings = get_settings()
llm = LLMService(settings)

LANGUAGE_PATTERNS: dict[str, re.Pattern[str]] = {
    "pl": re.compile(r"\b(czy|prosze|dziekuje|zamowienie|zwrot|przesylk|dostaw|witam|pozdrawiam)\b", re.IGNORECASE),
    "de": re.compile(r"\b(und|nicht|bitte|bestellung|lieferung|rueckgabe|rückgabe|danke|hallo)\b", re.IGNORECASE),
    "es": re.compile(r"\b(hola|gracias|pedido|devolucion|devolución|envio|envío|por favor)\b", re.IGNORECASE),
    "fr": re.compile(r"\b(bonjour|merci|commande|retour|livraison|s'il vous plait|s’il vous plait)\b", re.IGNORECASE),
    "it": re.compile(r"\b(ciao|grazie|ordine|reso|spedizione|per favore)\b", re.IGNORECASE),
    "pt": re.compile(r"\b(ola|olá|obrigado|pedido|devolucao|devolução|entrega|por favor)\b", re.IGNORECASE),
    "en": re.compile(r"\b(hello|hi|thanks|please|order|return|delivery|shipping|help)\b", re.IGNORECASE),
}

LANGUAGE_SPECIAL_CHARS: dict[str, str] = {
    "pl": "ąćęłńóśźż",
    "de": "äöüß",
    "es": "áéíóúñ¿¡",
    "fr": "àâçéèêëîïôûùüÿœ",
    "it": "àèéìíîòóù",
    "pt": "áâãàçéêíóôõú",
    "en": "",
}

FALLBACK_BY_LANGUAGE: dict[str, dict[str, str]] = {
    "en": {
        "reply": "Sorry - we couldn't generate a response right now.",
        "next_step": "Please review this message manually.",
    },
    "pl": {
        "reply": "Przepraszamy - nie moglismy teraz wygenerowac odpowiedzi.",
        "next_step": "Prosze sprawdzic te wiadomosc recznie.",
    },
    "de": {
        "reply": "Entschuldigung - wir konnten gerade keine Antwort erzeugen.",
        "next_step": "Bitte pruefen Sie diese Nachricht manuell.",
    },
    "es": {
        "reply": "Lo sentimos - no pudimos generar una respuesta en este momento.",
        "next_step": "Por favor revisa este mensaje manualmente.",
    },
    "fr": {
        "reply": "Desole - nous n'avons pas pu generer une reponse pour le moment.",
        "next_step": "Veuillez verifier ce message manuellement.",
    },
    "it": {
        "reply": "Ci dispiace - non siamo riusciti a generare una risposta in questo momento.",
        "next_step": "Controlla questo messaggio manualmente.",
    },
    "pt": {
        "reply": "Desculpe - nao foi possivel gerar uma resposta agora.",
        "next_step": "Por favor revise esta mensagem manualmente.",
    },
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legacy_get_fallback_result() -> dict[str, str]:
    return {
        "category": "OTHER",
        "reply": "Sorry — we couldn't generate a response right now.",
        "next_step": "Please review this message manually.",
    }


def detect_dominant_language(text: str) -> str:
    sample = (text or "").strip().lower()
    if not sample:
        return "en"

    scores: dict[str, float] = {lang: 0.0 for lang in LANGUAGE_PATTERNS}

    for lang, pattern in LANGUAGE_PATTERNS.items():
        scores[lang] += float(len(pattern.findall(sample)) * 2)

    for lang, chars in LANGUAGE_SPECIAL_CHARS.items():
        if not chars:
            continue
        char_hits = sum(sample.count(ch) for ch in chars)
        scores[lang] += float(char_hits * 3)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_lang, best_score = ranked[0]

    if best_score <= 0.0:
        return "en"

    return best_lang


def get_localized_fallback_result(raw_email: str) -> dict[str, str]:
    lang = detect_dominant_language(raw_email)
    localized = FALLBACK_BY_LANGUAGE.get(lang, FALLBACK_BY_LANGUAGE["en"])
    return {
        "category": "OTHER",
        "reply": localized["reply"],
        "next_step": localized["next_step"],
    }


def get_fallback_result(raw_email: str = "") -> dict[str, str]:
    # Backward-compatible wrapper to keep old helper name usable.
    return get_localized_fallback_result(raw_email)


def is_valid_result(category: object, reply: object, next_step: object) -> bool:
    return (
        isinstance(category, str)
        and isinstance(reply, str)
        and isinstance(next_step, str)
    )


def _parse_scope_value(raw_scope: object, fallback_scopes: list[str]) -> list[str]:
    if isinstance(raw_scope, str):
        cleaned = raw_scope.replace(",", " ")
        scopes = [part.strip() for part in cleaned.split(" ") if part.strip()]
        if scopes:
            return scopes
    return fallback_scopes


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "service": "ai-support-agent"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/support/reply", response_model=SupportResponse)
def generate_reply(request_data: SupportRequest, client=Depends(require_api_key)):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    raw_model_output = None
    parse_ok = 1
    error_message = None

    fallback = get_localized_fallback_result(request_data.message)
    category = fallback["category"]
    reply = fallback["reply"]
    next_step = fallback["next_step"]

    try:
        out = llm.generate_text(
            email=request_data.message,
            system=None,
            prompt_template=None,
            temperature=0.2,
            max_tokens=300,
        )

        raw_model_output = out["raw_text"]
        parsed = out["parsed"]

        category = parsed.get("category", fallback["category"])
        reply = parsed.get("reply", fallback["reply"])
        next_step = parsed.get("next_step", fallback["next_step"])

        if not is_valid_result(category, reply, next_step):
            parse_ok = 0
            error_message = "Model returned invalid schema types."
            category = fallback["category"]
            reply = fallback["reply"]
            next_step = fallback["next_step"]

    except Exception as e:
        parse_ok = 0
        error_message = repr(e)
        print("LLM ERROR /support/reply:", repr(e))
        traceback.print_exc()
        category = fallback["category"]
        reply = fallback["reply"]
        next_step = fallback["next_step"]

    latency_ms = int((time.perf_counter() - start) * 1000)

    insert_log(
        request_id=request_id,
        created_at=now_utc_iso(),
        source=request_data.source,
        customer_from=None,
        subject=None,
        category=category,
        reply=reply,
        next_step=next_step,
        raw_email=request_data.message,
        raw_model_output=raw_model_output,
        parse_ok=parse_ok,
        error_message=error_message,
    )

    return SupportResponse(
        request_id=request_id,
        client=client["name"],
        reply=reply,
        category=category,
        next_step=next_step,
        latency_ms=latency_ms,
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
    usage = {}

    fallback = get_localized_fallback_result(req.email)
    category = fallback["category"]
    reply = fallback["reply"]
    next_step = fallback["next_step"]

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

        category = parsed.get("category", fallback["category"])
        reply = parsed.get("reply", fallback["reply"])
        next_step = parsed.get("next_step", fallback["next_step"])

        if not is_valid_result(category, reply, next_step):
            parse_ok = 0
            error_message = "Model returned invalid schema types."
            category = fallback["category"]
            reply = fallback["reply"]
            next_step = fallback["next_step"]

    except Exception as e:
        parse_ok = 0
        error_message = repr(e)
        print("LLM ERROR /generate:", repr(e))
        traceback.print_exc()
        category = fallback["category"]
        reply = fallback["reply"]
        next_step = fallback["next_step"]

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
        "result": {
            "category": category,
            "reply": reply,
            "next_step": next_step,
        },
        "usage": usage,
        "latency_ms": latency_ms,
    }


@app.get("/auth/google/start")
def auth_google_start(
    client_name: Optional[str] = Query(default=None, min_length=1, max_length=200),
    processed_label: str = Query(default=DEFAULT_PROCESSED_LABEL, min_length=1, max_length=100),
    skipped_label: str = Query(default=DEFAULT_SKIPPED_LABEL, min_length=1, max_length=100),
    client=Depends(require_api_key),
):
    try:
        config = get_google_oauth_config()
    except GoogleOAuthConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    authenticated_client_name = None
    try:
        authenticated_client_name = client["name"]
    except Exception:
        authenticated_client_name = None

    effective_client_name = (client_name or authenticated_client_name or "oauth-mailbox").strip()
    state_secret = (os.getenv("GOOGLE_OAUTH_STATE_SECRET") or config.client_secret).strip()
    if not state_secret:
        raise HTTPException(status_code=500, detail="OAuth state signing secret is not configured")

    state = create_oauth_state(
        {
            "client_name": effective_client_name,
            "processed_label": processed_label.strip(),
            "skipped_label": skipped_label.strip(),
        },
        state_secret,
    )

    authorization_url = build_google_auth_url(config, state)
    return {
        "authorization_url": authorization_url,
        "redirect_uri": config.redirect_uri,
        "scopes": config.scopes,
    }


@app.get("/auth/google/callback")
def auth_google_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
):
    if error:
        if error == "access_denied":
            detail = "Google OAuth consent was denied by the user."
        else:
            detail = f"Google OAuth returned an error: {error}"
        if error_description:
            detail = f"{detail} ({error_description})"
        raise HTTPException(status_code=400, detail=detail)

    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code in callback.")
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state in callback.")

    try:
        config = get_google_oauth_config()
    except GoogleOAuthConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    state_secret = (os.getenv("GOOGLE_OAUTH_STATE_SECRET") or config.client_secret).strip()
    if not state_secret:
        raise HTTPException(status_code=500, detail="OAuth state signing secret is not configured")

    try:
        state_payload = parse_oauth_state(state, state_secret)
    except GoogleOAuthStateError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid OAuth state: {exc}")

    try:
        token_payload = exchange_google_code(config, code)
    except GoogleOAuthExchangeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    access_token = (token_payload.get("access_token") or "").strip()
    refresh_token = (token_payload.get("refresh_token") or "").strip() or None
    token_expiry = derive_token_expiry_iso(token_payload.get("expires_in"))
    scopes = _parse_scope_value(token_payload.get("scope"), config.scopes)

    try:
        mailbox_email = fetch_gmail_mailbox_email(access_token)
    except GoogleOAuthExchangeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    effective_client_name = (str(state_payload.get("client_name") or "") or mailbox_email).strip() or mailbox_email
    effective_processed_label = (
        str(state_payload.get("processed_label") or DEFAULT_PROCESSED_LABEL).strip() or DEFAULT_PROCESSED_LABEL
    )
    effective_skipped_label = (
        str(state_payload.get("skipped_label") or DEFAULT_SKIPPED_LABEL).strip() or DEFAULT_SKIPPED_LABEL
    )

    try:
        upsert_result = upsert_gmail_mailbox_oauth(
            client_name=effective_client_name,
            mailbox_email=mailbox_email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            scopes=scopes,
            processed_label=effective_processed_label,
            skipped_label=effective_skipped_label,
            active=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist Gmail mailbox: {exc}")

    created = bool(upsert_result.get("created"))
    return {
        "status": "connected",
        "mailbox_id": upsert_result.get("id"),
        "mailbox_email": upsert_result.get("mailbox_email"),
        "active": bool(upsert_result.get("active")),
        "connection_result": "created" if created else "updated_existing",
        "duplicate_mailbox_connection": not created,
        "scopes": scopes,
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

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
