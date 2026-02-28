from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict

class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=1, max_length=50_000)
    source: str = Field(default="api", max_length=100)

    # LLM controls (opcjonalnie)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=300, ge=1, le=4096)

    # Prompting (opcjonalnie)
    system: Optional[str] = Field(default=None, max_length=10_000)
    prompt_template: Optional[str] = Field(default=None, max_length=50_000)

class GenerateResult(BaseModel):
    model_config = ConfigDict(extra="allow")  # wynik z LLM (JSON) może mieć extra pola

    category: str
    reply: str
    next_step: str

class GenerateResponse(BaseModel):
    request_id: str
    result: Dict[str, Any]
    usage: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: int