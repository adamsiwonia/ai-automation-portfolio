# Email Automation (SMTP + Mailtrap)

## Overview
A small Python automation tool that sends personalized emails from a CSV list using a text template.
Includes a safe DRY_RUN mode, SMTP sending mode, and CSV logging for audit/debugging.

## Features
- Loads recipients from `recipients.csv`
- Loads email subject/body from `template.txt`
- Personalizes content using `{name}` and `{email}`
- Two modes:
  - `DRY_RUN` (default): preview + log only
  - `SEND`: sends emails via SMTP (tested with Mailtrap)
- Writes results to `email_log.csv` (runtime file)

## Project Structure
- `main.py` – main script
- `recipients.csv` – recipients list (`email,name`)
- `template.txt` – template starting with `Subject: ...`
- `email_log.csv` – runtime log (ignored by git)
- `email_log_sample.csv` – sample log tracked in repo
- `.env` – SMTP credentials (ignored by git)

## Setup
Install dependency:
```bash
pip install python-dotenv