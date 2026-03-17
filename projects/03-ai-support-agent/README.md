# AI Support Agent – FastAPI Backend (Project 03)

## Overview

This project implements a **production-oriented AI-powered customer support backend** designed to automate responses to repetitive customer emails.

Built with:

* FastAPI
* OpenAI API
* SQLite
* Structured JSON validation
* Persistent logging & observability

The system processes incoming customer messages, classifies intent, and generates structured, ready-to-send replies.

This project focuses on:

* backend architecture
* reliability
* real-world automation use cases
* production-ready design patterns

---

## Current Capabilities

* AI-powered email classification
* AI-generated customer support replies
* Structured JSON validation (safe LLM output handling)
* FastAPI backend API
* SQLite request logging
* API key authentication
* Gmail worker (polling + draft generation)

---

## System Architecture

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
│   └── gmail_test.py   # Gmail worker
│
├── data/
│   └── sample_emails.txt
│
└── README.md
```

---

## Architecture Principles

* Clear separation of concerns (API / service / database)
* Strict data contracts using Pydantic
* Defensive handling of LLM output
* Logging-first design
* Environment-based configuration
* Observability by default

---

## End-to-End Flow

```
Customer Email
     ↓
Gmail Worker (polling loop)
     ↓
FastAPI (/generate)
     ↓
LLM Service (OpenAI)
     ↓
Structured JSON validation
     ↓
SQLite logging
     ↓
AI-generated draft reply
     ↓
Gmail Draft created
```

---

## Gmail Integration (Worker)

The project includes a **Gmail worker** that connects the backend to a real inbox.

Script:

```
scripts/gmail_test.py
```

### What it does

* polls Gmail inbox every 60 seconds
* filters non-customer emails (newsletters, promos, alerts)
* detects customer support messages
* sends valid messages to the FastAPI backend
* generates AI replies
* creates **draft replies in Gmail**
* labels processed / skipped emails

### Labels used

* `AI Draft Ready` → processed emails
* `AI Skipped` → filtered emails

This simulates a real-world automation pipeline for small businesses.

---

## Features

### Intent Classification

Example categories:

* RETURN
* REFUND
* SHIPPING
* PRODUCT_QUESTION
* OTHER

---

## Structured JSON Output

All LLM responses are validated against:

```json
{
  "category": "Refund Request",
  "reply": "Customer-facing response text",
  "next_step": "Internal action"
}
```

If parsing fails:

* request is still logged
* `parse_ok = 0`
* fallback response is generated
* API returns HTTP `502`

---

## API Endpoints

### Health Check

```
GET /health
```

---

### Generate AI Response

```
POST /generate
```

Request:

```json
{
  "email": "Customer email text"
}
```

Response:

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

* token usage
* latency tracking
* request tracing

---

### Logs & Observability

```
GET /logs?limit=20
GET /logs?parse_ok=0
GET /logs?category=Refund%20Request
```

Tracks:

* model outputs
* errors
* parsing failures
* categories
* raw responses

---

## Observability Design

Each request is stored with:

* `request_id`
* `created_at`
* `category`
* `reply`
* `parse_ok`
* `error_message`
* `raw_model_output`

This enables:

* debugging LLM issues
* monitoring system quality
* auditing behavior
* building analytics dashboards

---

## Security

* API key authentication (`X-API-Key`)
* HMAC-based hashing
* protected endpoints
* environment-based secrets

---

## Why This Matters

LLM outputs are inherently unreliable in structure.

This project demonstrates how to:

* enforce structured output
* handle malformed responses safely
* log every interaction
* measure latency and usage
* design production-ready AI systems

---

## How to Run

### 1. Install dependencies

```bash
pip install fastapi uvicorn openai python-dotenv
```

---

### 2. Create `.env`

```
OPENAI_API_KEY=your_api_key_here
API_KEY=your_internal_api_key
```

---

### 3. Start backend

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

### 4. Run Gmail worker

```bash
python scripts/gmail_test.py
```

---

### 5. Open API docs

```
http://127.0.0.1:8000/docs
```

---

## Roadmap

* multi-client (multi-tenant) support
* rate limiting
* retry logic for failed parses
* conversation memory
* Docker deployment
* cloud worker deployment
* metrics endpoint (`/stats`)

---

## Purpose

This project demonstrates:

* real-world AI automation
* backend architecture for LLM systems
* production-safe output handling
* full pipeline (email → AI → draft)
* observability-first system design

The goal is to evolve this into a **commercial AI support automation service for small businesses**.
