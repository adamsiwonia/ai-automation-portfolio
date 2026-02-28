# AI Support Agent – FastAPI Backend (Project 03)
## Overview

This project implements a production-style AI-powered customer support backend built with:

-FastAPI

-OpenAI API

-SQLite

-Structured JSON response validation

-Persistent request and model-response logging

-The system classifies incoming customer emails, generates structured replies, and stores all interactions for monitoring, debugging, and future analytics.

-The focus of this project is backend architecture, reliability, and observability rather than UI.

## Architecture

03-ai-support-agent/
│
├── app/
│   ├── main.py              # FastAPI routing layer
│   ├── schemas.py           # Pydantic request/response contracts
│   ├── core/
│   │   └── config.py        # Environment & configuration management
│   ├── services/
│   │   └── llm.py           # LLM integration layer
│   └── database/
│       ├── db.py            # SQLite access layer
│       └── schema.sql       # Database schema
│
├── prompts/
│   └── support_prompt.txt
│
├── data/
│   └── sample_emails.txt
│
└── README.md

## Architectural Principles

-Clear separation of concerns (routing / service / persistence)

-Strict data contracts via Pydantic

-Defensive handling of LLM output

-Logging-first design

-Environment-based configuration

-Request Processing Flow

-Request validated via Pydantic schema

-LLM service invoked

-Raw model output parsed and validated

-Fallback triggered if parsing fails

-Request logged to SQLite

-Response returned with request_id and metrics

## Features

-Intent Classification

-upported categories:

-RETURN

-REFUND

-SHIPPING

-PRODUCT_QUESTION

-OTHER

Note: Category values are model-generated and may not be restricted to strict enums depending on prompt configuration.

# Structured JSON Output

-All model responses are parsed and validated against a fixed schema:

{
  "category": "Refund Request",
  "reply": "Customer-facing response text",
  "next_step": "Operational follow-up action"
}

-If parsing fails:

The request is still logged

parse_ok is set to 0

A fallback response is generated

The API returns HTTP 502

API Endpoints
Health Check
GET /health
Generate AI Response
POST /generate

-Request body:

{
  "email": "Customer email text"
}

-Response:

{
  "request_id": "uuid",
  "result": {
    "category": "...",
    "reply": "...",
    "next_step": "..."
  },
  "usage": {
    "input_tokens": 65,
    "output_tokens": 64,
    "total_tokens": 129
  },
  "latency_ms": 2191
}

### Includes:

-Token usage tracking

-Latency measurement

-Request ID for traceability

-Retrieve Logs
GET /logs?limit=20
GET /logs?parse_ok=0
GET /logs?category=Refund%20Request

### Allows inspection of:

-Successful responses

-Failed parses

-Error messages

-Raw model outputs

-Logging & Observability

### All requests are stored in SQLite with:

-request_id

-created_at

-category

-reply

-parse_ok

-error_message

-raw_model_output

### This enables:

-Debugging malformed LLM responses

-Monitoring error rates

-Auditing model behavior

-Building analytics dashboards

The system is designed with observability in mind from the start.

# How to Run

1. Install dependencies
pip install fastapi uvicorn openai python-dotenv
2. Create .env
OPENAI_API_KEY=your_api_key_here
3. Start the server

## From the project directory:

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
4. Interactive API docs
http://127.0.0.1:8000/docs
Design Decisions

-JSON schema validation before returning model output

-Defensive fallback logic for malformed responses

-Logging occurs even if generation fails

-Separation between LLM integration and HTTP layer

-SQLite chosen for lightweight persistence in MVP phase

-Latency and token usage exposed for monitoring

# Roadmap

-API key authentication

-Rate limiting

-Retry logic for malformed JSON responses

-Conversation history support

-Docker containerization

-Cloud deployment

-Metrics endpoint (/stats)

# Purpose

This project demonstrates:

-LLM integration in backend systems

-Production-style API architecture

-Structured output enforcement

-Error handling and resilience strategies

-Persistent logging for AI systems

-Observability-first backend thinking

The system is designed to be extended into a multi-tenant, rate-limited production service.