from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


# =========================
# LLM / GENERATE ENDPOINT
# =========================

class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=1, max_length=50_000)
    source: str = Field(default="api", max_length=100)

    # LLM controls
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=300, ge=1, le=4096)

    # Prompting
    system: Optional[str] = Field(default=None, max_length=10_000)
    prompt_template: Optional[str] = Field(default=None, max_length=50_000)


class GenerateResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    category: str
    reply: str
    next_step: str


class GenerateResponse(BaseModel):
    request_id: str
    result: Dict[str, Any]
    usage: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: int


# =========================
# WEB DEMO / SUPPORT ENDPOINT
# =========================

class SupportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=20_000)
    source: str = Field(default="web", max_length=100)


class SupportResponse(BaseModel):
    request_id: str
    client: str
    reply: str
    category: Optional[str] = None
    next_step: Optional[str] = None
    latency_ms: Optional[int] = None