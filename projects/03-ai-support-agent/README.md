# AI Support Agent – FastAPI Backend (Project 03)

## Overview

This project implements a production-oriented AI-powered customer support backend built with:

- FastAPI
- OpenAI API
- SQLite
- Structured JSON response validation
- Persistent request and model-response logging

The system analyzes incoming customer emails, classifies support intent, and generates structured replies suitable for customer support workflows.

The focus of this project is **backend architecture, reliability, and observability**, rather than UI.

---

## Current Capabilities

- AI email classification
- AI support reply generation
- Structured JSON response validation
- FastAPI backend API
- SQLite request logging
- API key authentication
- Local Gmail integration test

---

## Architecture

```
03-ai-support-agent/
│
├── app/
│   ├── main.py
│   ├── schemas.py
│   ├── web_demo.py
│
│   ├── core/
│   │   ├── auth.py
│   │   └── config.py
│
│   ├── services/
│   │   └── llm.py
│
│   └── database/
│       ├── db.py
│       └── schema.sql
│
├── prompts/
│   └── support_prompt.txt
│
├── scripts/
│   └── gmail_test.py
│
├── data/
│   └── sample_emails.txt
│
└── README.md
```

---

## Architectural Principles

- Clear separation of concerns (routing / service / persistence)
- Strict data contracts via Pydantic
- Defensive handling of LLM output
- Logging-first design
- Environment-based configuration
- Observability by default

---

## Request Processing Flow

```
Client Request
     ↓
FastAPI Endpoint
     ↓
Pydantic Validation
     ↓
LLM Service (OpenAI)
     ↓
JSON Parsing & Validation
     ↓
SQLite Logging
     ↓
Structured Response
```

---

## Gmail Integration (Experimental)

The repository includes a **local Gmail integration test** demonstrating how the backend can be connected to a real support inbox.

Script used for testing:

```
scripts/gmail_test.py
```

Pipeline:

```
Customer Email
     ↓
Gmail API
     ↓
gmail_test.py
     ↓
POST /support/reply
     ↓
LLMService (OpenAI)
     ↓
AI Support Reply
```

This simulates how the system could integrate with real support inboxes.

Currently this integration:

- reads the latest email from Gmail
- sends the email content to the AI backend
- receives an AI-generated support response

Future iterations will automatically create **Gmail draft replies**.

---

## Features

### Intent Classification

Supported categories:

- RETURN
- REFUND
- SHIPPING
- PRODUCT_QUESTION
- OTHER

Note: Category values are model-generated and may vary depending on prompt configuration.

---

## Structured JSON Output

All model responses are parsed and validated against a fixed schema:

```json
{
  "category": "Refund Request",
  "reply": "Customer-facing response text",
  "next_step": "Operational follow-up action"
}
```

If parsing fails:

- the request is still logged
- `parse_ok` is set to `0`
- a fallback response is generated
- the API returns HTTP `502`

---

## API Endpoints

### Health Check

```
GET /health
```

### Generate AI Response

```
POST /generate
```

Request body example:

```json
{
  "email": "Customer email text"
}
```

Response example:

```json
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
```

Includes:

- token usage tracking
- latency measurement
- request ID for traceability

### Retrieve Logs

```
GET /logs?limit=20
GET /logs?parse_ok=0
GET /logs?category=Refund%20Request
```

Allows inspection of:

- successful responses
- failed parses
- error messages
- raw model outputs

---

## Logging & Observability

All requests are stored in SQLite with:

- `request_id`
- `created_at`
- `category`
- `reply`
- `parse_ok`
- `error_message`
- `raw_model_output`

This enables:

- debugging malformed LLM responses
- monitoring error rates
- auditing model behavior
- building analytics dashboards

The system is designed with **observability in mind from the start**.

---

## Security

- HMAC-based API key hashing
- `X-API-Key` header authentication
- protected `/generate` and `/logs` endpoints
- SQLite storage

---

## Why This Matters

In production AI systems, model outputs are **not guaranteed to follow strict schemas**.

This project demonstrates how to:

- enforce structured output validation
- handle malformed responses defensively
- log all interactions for traceability
- measure latency and token usage
- build observability into AI systems from day one

---

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn openai python-dotenv
```

### 2. Create `.env`

```
OPENAI_API_KEY=your_api_key_here
```

### 3. Start the server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4. Open API docs

```
http://127.0.0.1:8000/docs
```

---

## Roadmap

- Gmail draft creation
- rate limiting
- retry logic for malformed JSON responses
- conversation history support
- Docker containerization
- cloud deployment
- metrics endpoint (`/stats`)

---

## Purpose

This project demonstrates:

- LLM integration in backend systems
- production-style API architecture
- structured output enforcement
- error handling and resilience strategies
- persistent logging for AI systems
- observability-first backend design

The system is designed to be extended into a **multi-tenant, rate-limited production AI service**.