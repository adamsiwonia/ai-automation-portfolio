# AI Support Agent (Project 03)

## Overview

This project implements a minimal AI-powered customer support agent using the OpenAI API.

### The system:

-Classifies incoming customer messages

-Generates structured responses

-Returns standardized JSON output

-Logs results for further processing

### The goal of this project is to build a production-oriented AI automation component that can later be deployed in real-world business environments.

## Current Features (MVP v1)

### Prompt-based intent classification:

-RETURN

-REFUND

-SHIPPING

-PRODUCT_QUESTION

-OTHER

### Structured JSON output:

{
  "category": "...",
  "reply": "...",
  "next_step": "..."
}

### Markdown-safe JSON parsing

File-based logging (outputs.json)

Secure API key handling via .env

### Project Structure
03-ai-support-agent/
│
├── main.py
├── .env (ignored by git)
│
├── prompts/
│   └── support_prompt.txt
│
├── data/
│   ├── sample_emails.txt
│   └── outputs.json
│
└── README.md
# How to Run

Install dependencies:

pip install openai python-dotenv

Create a .env file inside the project folder:

OPENAI_API_KEY=your_api_key_here

Run the agent:

python projects/03-ai-support-agent/main.py

Generated responses will be saved to:

data/outputs.json
Technical Notes

The system removes Markdown code fences before parsing JSON.

Fallback handling ensures the pipeline does not crash on malformed model responses.

Designed as a backend-first architecture (frontend layer not yet implemented).

# Roadmap

Planned improvements:

SQLite logging

Conversation history support

REST API interface (FastAPI)

Web demo frontend

Deployment to cloud environment

Rate limiting and request validation

Production-ready error handling

# Purpose

This project is part of a broader portfolio focused on AI Automation and Data Analytics.

It demonstrates:

LLM integration

Structured response design

Error handling

Secure configuration management

Real-world automation architecture thinking