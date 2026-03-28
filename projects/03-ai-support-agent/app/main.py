from __future__ import annotations

import os
import re
import secrets
import time
import uuid
import traceback
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.admin_panel import router as admin_router
from app.core.auth import require_api_key
from app.core.config import get_settings
from app.database.db import fetch_logs, get_db, init_db, insert_log
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
app.include_router(admin_router)

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


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _get_expected_admin_api_key() -> str:
    expected = (os.getenv("ADMIN_API_KEY") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin panel OAuth flow is disabled because ADMIN_API_KEY is not configured.",
        )
    return expected


def _validate_admin_api_key(candidate: str | None) -> None:
    expected = _get_expected_admin_api_key()
    provided = (candidate or "").strip()
    if not provided:
        raise HTTPException(status_code=401, detail="Missing admin API key")
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid admin API key")


def _sanitize_admin_redirect_path(raw_path: object) -> str | None:
    if not isinstance(raw_path, str):
        return None

    candidate = raw_path.strip()
    if not candidate:
        return None
    if not candidate.startswith("/admin"):
        return None
    if candidate.startswith("//"):
        return None
    return candidate


def _build_admin_notice_redirect(*, path: str, notice: str, is_error: bool = False) -> RedirectResponse:
    payload: dict[str, str | int] = {"notice": notice}
    if is_error:
        payload["error"] = 1

    separator = "&" if "?" in path else "?"
    return RedirectResponse(
        url=f"{path}{separator}{urlencode(payload)}",
        status_code=303,
    )


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
    request: Request,
    client_name: Optional[str] = Query(default=None, min_length=1, max_length=200),
    processed_label: str = Query(default=DEFAULT_PROCESSED_LABEL, min_length=1, max_length=100),
    skipped_label: str = Query(default=DEFAULT_SKIPPED_LABEL, min_length=1, max_length=100),
    post_connect_redirect: Optional[str] = Query(default=None, max_length=200),
    redirect_to_google: bool = Query(default=False),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    admin_api_key: str | None = Cookie(default=None, alias="admin_api_key"),
    db=Depends(get_db),
):
    authenticated_client_name = None
    if redirect_to_google:
        # Browser-based admin flow uses dedicated ADMIN_API_KEY from the admin cookie.
        _validate_admin_api_key(admin_api_key)
        authenticated_client_name = "admin-panel"
    else:
        effective_api_key = (x_api_key or "").strip() or _extract_bearer_token(authorization)
        if not effective_api_key:
            raise HTTPException(status_code=401, detail="Missing API key")

        client = require_api_key(
            request=request,
            x_api_key=effective_api_key,
            authorization=None,
            db=db,
        )
        try:
            authenticated_client_name = client["name"]
        except Exception:
            authenticated_client_name = None

    try:
        config = get_google_oauth_config()
    except GoogleOAuthConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    effective_client_name = (client_name or authenticated_client_name or "oauth-mailbox").strip()
    state_secret = (os.getenv("GOOGLE_OAUTH_STATE_SECRET") or config.client_secret).strip()
    if not state_secret:
        raise HTTPException(status_code=500, detail="OAuth state signing secret is not configured")

    state_payload: dict[str, str] = {
        "client_name": effective_client_name,
        "processed_label": processed_label.strip(),
        "skipped_label": skipped_label.strip(),
    }
    safe_post_connect_redirect = _sanitize_admin_redirect_path(post_connect_redirect)
    if safe_post_connect_redirect:
        state_payload["post_connect_redirect"] = safe_post_connect_redirect

    state = create_oauth_state(
        state_payload,
        state_secret,
    )

    authorization_url = build_google_auth_url(config, state)
    if redirect_to_google:
        return RedirectResponse(url=authorization_url, status_code=303)

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
    def maybe_redirect_admin_error(message: str) -> RedirectResponse | None:
        state_secret_candidate = (os.getenv("GOOGLE_OAUTH_STATE_SECRET") or os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
        if not state or not state_secret_candidate:
            return None
        try:
            payload = parse_oauth_state(state, state_secret_candidate)
        except Exception:
            return None
        redirect_path = _sanitize_admin_redirect_path(payload.get("post_connect_redirect"))
        if not redirect_path:
            return None
        return _build_admin_notice_redirect(path=redirect_path, notice=message, is_error=True)

    if error:
        if error == "access_denied":
            detail = "Google OAuth consent was denied by the user."
        else:
            detail = f"Google OAuth returned an error: {error}"
        if error_description:
            detail = f"{detail} ({error_description})"
        redirect_response = maybe_redirect_admin_error(detail)
        if redirect_response:
            return redirect_response
        raise HTTPException(status_code=400, detail=detail)

    if not code:
        detail = "Missing OAuth code in callback."
        redirect_response = maybe_redirect_admin_error(detail)
        if redirect_response:
            return redirect_response
        raise HTTPException(status_code=400, detail=detail)
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state in callback.")

    try:
        config = get_google_oauth_config()
    except GoogleOAuthConfigError as exc:
        detail = str(exc)
        redirect_response = maybe_redirect_admin_error(detail)
        if redirect_response:
            return redirect_response
        raise HTTPException(status_code=500, detail=detail)

    state_secret = (os.getenv("GOOGLE_OAUTH_STATE_SECRET") or config.client_secret).strip()
    if not state_secret:
        detail = "OAuth state signing secret is not configured"
        redirect_response = maybe_redirect_admin_error(detail)
        if redirect_response:
            return redirect_response
        raise HTTPException(status_code=500, detail=detail)

    try:
        state_payload = parse_oauth_state(state, state_secret)
    except GoogleOAuthStateError as exc:
        detail = f"Invalid OAuth state: {exc}"
        redirect_response = maybe_redirect_admin_error(detail)
        if redirect_response:
            return redirect_response
        raise HTTPException(status_code=400, detail=detail)

    admin_redirect_path = _sanitize_admin_redirect_path(state_payload.get("post_connect_redirect"))

    try:
        token_payload = exchange_google_code(config, code)
    except GoogleOAuthExchangeError as exc:
        detail = str(exc)
        if admin_redirect_path:
            return _build_admin_notice_redirect(path=admin_redirect_path, notice=detail, is_error=True)
        raise HTTPException(status_code=502, detail=detail)

    access_token = (token_payload.get("access_token") or "").strip()
    refresh_token = (token_payload.get("refresh_token") or "").strip() or None
    token_expiry = derive_token_expiry_iso(token_payload.get("expires_in"))
    scopes = _parse_scope_value(token_payload.get("scope"), config.scopes)

    try:
        mailbox_email = fetch_gmail_mailbox_email(access_token)
    except GoogleOAuthExchangeError as exc:
        detail = str(exc)
        if admin_redirect_path:
            return _build_admin_notice_redirect(path=admin_redirect_path, notice=detail, is_error=True)
        raise HTTPException(status_code=502, detail=detail)

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
        detail = str(exc)
        if admin_redirect_path:
            return _build_admin_notice_redirect(path=admin_redirect_path, notice=detail, is_error=True)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as exc:
        detail = f"Failed to persist Gmail mailbox: {exc}"
        if admin_redirect_path:
            return _build_admin_notice_redirect(path=admin_redirect_path, notice=detail, is_error=True)
        raise HTTPException(status_code=500, detail=detail)

    created = bool(upsert_result.get("created"))
    if admin_redirect_path:
        mailbox_email_value = str(upsert_result.get("mailbox_email") or mailbox_email)
        action = "connected" if created else "updated"
        notice = f"Mailbox {mailbox_email_value} {action} successfully."
        return _build_admin_notice_redirect(path=admin_redirect_path, notice=notice, is_error=False)

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
