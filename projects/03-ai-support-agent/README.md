# AI Email Support Assistant (Project 03)

Automate 60–80% of customer emails (shipping, returns, order status)
→ Save hours every week
→ Respond faster to customers

---

## 🚀 Demo

Try the demo: https://ai-automation-portfolio-tyou.onrender.com/demo
Example:

* Paste a customer email
* Generate a reply in seconds
* Review before sending

---

## 💡 What This Project Does

This project is a production-oriented AI customer support backend + demo interface designed to automate repetitive customer emails.

It:

* reads incoming messages
* classifies intent (returns, shipping, etc.)
* generates a ready-to-send reply
* suggests the next internal step

All responses are draft-only — nothing is sent automatically.

---

## ✨ Key Features

* AI-generated draft replies for common customer inquiries
* Multilingual replies (responds in the same language as the customer)
* EN / PL interface in demo
* Structured output validation (safe LLM usage)
* Gmail integration with automatic draft creation
* Full request logging and observability

---

## ⚙️ How It Works

1. Customer sends an email
2. AI analyzes the message
3. A reply draft is generated
4. You review and send

---

## 📦 Example Use Cases

* “Where is my order?”
* “I want to return this item”
* “Do you have this product in stock?”

---

## 🧠 Why This Matters

Customer support is repetitive and time-consuming.

This project shows how to:

* automate common responses
* reduce workload for small businesses
* maintain control with draft-only replies
* safely use AI with structured validation

---

## 🏗️ System Architecture

```
Customer Email
     ↓
Gmail Worker (polling)
     ↓
FastAPI (/generate)
     ↓
LLM Service (OpenAI)
     ↓
Structured validation
     ↓
SQLite logging
     ↓
Draft reply created
```

---

## 🧩 Tech Stack

* FastAPI
* OpenAI API
* SQLite
* Gmail API
* Pydantic

---

## 📁 Project Structure

```
app/
  main.py          # API endpoints
  schemas.py       # data validation
  web_demo.py      # demo UI

  core/
    auth.py
    config.py

  services/
    llm.py         # AI logic

  database/
    db.py
    schema.sql

scripts/
  worker_loop.py   # Gmail worker (polling)
```

---

## 🔌 Gmail Integration

The system includes a Gmail worker that:

* polls inbox every 60 seconds
* filters non-customer emails
* detects support messages
* generates AI replies
* creates draft replies in Gmail
* labels processed emails
* loads active Gmail mailbox connections from `gmail_mailboxes` (DB-backed foundation)
* falls back to legacy single-mailbox `token.json` mode when no active DB mailbox is configured

Labels:

* AI_PROCESSED
* AI_SKIPPED

Google OAuth mailbox connect endpoints:

* `GET /auth/google/start` (returns authorization URL)
* `GET /auth/google/callback` (handles code exchange and upserts `gmail_mailboxes`)

---

## 📊 Observability

Each request logs:

* request_id
* category
* reply
* parse status
* raw model output
* latency
* token usage

This allows:

* debugging
* monitoring
* auditing AI behavior

---

## 🔐 Security

* API key authentication (X-API-Key)
* environment-based secrets
* protected endpoints

---

## 🧪 API Example

### POST /generate

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
    "total_tokens": 129
  },
  "latency_ms": 2191
}
```

---

## ▶️ How to Run

```bash
pip install fastapi uvicorn openai python-dotenv
```

Create `.env`:

```
OPENAI_API_KEY=your_api_key_here
API_KEY=your_internal_api_key
DEMO_API_KEY=your_internal_api_key

# Required for Google OAuth mailbox connection flow
GOOGLE_CLIENT_ID=your_google_oauth_client_id
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/auth/google/callback

# Optional
# Comma or space-separated. Defaults to Gmail modify+compose scopes.
GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.compose
# Optional custom state-signing secret (falls back to GOOGLE_CLIENT_SECRET)
GOOGLE_OAUTH_STATE_SECRET=change_me
```

Run backend:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run Gmail worker:

```bash
python scripts/worker_loop.py
```

Connect a Gmail mailbox via OAuth (backend-only):

```bash
# 1) Get authorization URL (requires API key)
curl -H "X-API-Key: your_internal_api_key" "http://127.0.0.1:8000/auth/google/start"

# 2) Open returned authorization_url in browser, complete consent.
# 3) Google redirects to /auth/google/callback and mailbox is upserted into gmail_mailboxes.
```

---

## 🛣️ Roadmap

* multi-client support
* retry logic
* conversation memory
* Docker deployment
* cloud deployment
* metrics dashboard

---

## 🎯 Purpose

This project demonstrates:

* real-world AI automation
* production-safe LLM usage
* full pipeline (email → AI → draft)
* backend architecture for AI systems

The goal is to evolve this into a commercial AI support automation service for small businesses.
