# AGENTS.md

## Project
This repo contains Project 03: AI Support Agent.
Current state: single-mailbox Gmail demo with FastAPI backend and worker loop.

## Goal
Refactor toward a multi-client foundation with Google OAuth, while preserving the current email-processing behavior.

## Rules
- Keep changes minimal and production-oriented.
- Preserve current draft-generation flow unless a change is strictly required.
- Do not add frontend UI.
- Do not commit secrets, credentials, tokens, or .env values.
- Prefer small, reviewable diffs.
- Update README when behavior or setup changes.

## Important files
- app/main.py
- scripts/worker_loop.py
- database/models-related files
- config/env-related files
- README.md

## Validation
Before finishing:
- run the existing app locally if possible
- verify imports and startup
- verify worker logic still has a clear execution path
- document new environment variables
- summarize changed files and remaining risks