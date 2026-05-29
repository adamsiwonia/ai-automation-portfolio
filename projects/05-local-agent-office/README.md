# Local Agent Office MVP

A minimal local lead-prep office for discovering business leads, pre-filtering obvious bad matches, qualifying plausible leads with a local Ollama model, and managing the lead review state in Project 05's own SQLite database.

This project never sends emails.

## Architecture Decision

Project 05 is now DB-first. Its SQLite database is the source of truth for discovered, qualified, reviewed, and approved leads.

Project 05 does not read, inspect, migrate, or write the Project 03.5 SQLite database. Google Sheets remains available as an optional/fallback handoff, but Project 05 no longer depends on the Sheet as its source of truth.

## What It Does

- Serves a local control panel at `http://127.0.0.1:8765`
- Discovers structured lead candidates in `mock`, `manual`, or `search` mode
- Clearly labels mock results as `MOCK` and blocks them from real outreach by default
- Uses a `LeadDiscoveryAgent` with provider tools for real discovery paths
- Applies a strict pre-filter before calling Ollama
- Qualifies only plausible leads through the local Ollama API
- Imports real manually researched leads from CSV as review-ready records
- Stores the lead control lifecycle locally in SQLite
- Safely treats Google Sheets as optional/fallback if it is not configured
- Deduplicates against local Project 05 SQLite data
- Deduplicates against existing Google Sheet rows when Sheets is configured
- Lets you mark local leads as `APPROVED_FOR_OUTREACH` or `REJECTED` from the control panel
- Stores leads, logs, and runs in `data/local_agent_office.sqlite`

## Lead Statuses

Project 05 stores lead status locally.

Supported lead lifecycle statuses:

- `DISCOVERED`
- `QUALIFIED`
- `REVIEW`
- `APPROVED_FOR_OUTREACH`
- `REJECTED`
- `DRAFT_CREATED`
- `DONE`

The current UI exposes simple approve/reject actions. Approving a lead marks it `APPROVED_FOR_OUTREACH`. Rejecting a lead marks it `REJECTED`.

Mock/demo leads are for testing only. Project 05 shows a `MOCK` badge for them, disables approval in Lead Control, and the backend rejects direct approval requests for mock/demo leads.

The control panel has three tabs:

- **Home / Dashboard**: current mode, run controls, stats, and the 30 most recent logs
- **Lead Control**: SQLite lead table with approve/reject actions
- **Logs**: full logs table, separate from lead management

## Project 03.5 CSV Export

Project 05 can export approved leads into a CSV that matches the current Project 03.5 Google Sheet columns. This does not send emails and does not modify Project 03.5 directly.

Only non-mock leads with `status = APPROVED_FOR_OUTREACH` and no `exported_at` timestamp are exported. After a successful export, Project 05 sets `exported_at` so the same lead is not exported again.

Mock/demo leads are skipped by default even if they were previously approved. The exporter prints a skipped mock count so test data cannot quietly enter Project 03.5.

Run:

```powershell
python scripts\export_project035_csv.py
```

Testing-only override:

```powershell
python scripts\export_project035_csv.py --include-mock
```

Use `--include-mock` only for test CSVs. Do not use it for real outreach handoff.

Default output:

```text
exports/project035_approved_leads.csv
```

CSV headers, in order:

- `Company`
- `Email`
- `Date Sent`
- `Follow up Date`
- `Response`
- `Notes`
- `Segment`
- `Lead Type`
- `Assistant Status`
- `Selected Contact`
- `Draft Type`
- `Draft Subject`
- `Draft Body`
- `Personalization Note`
- `Last Processed At`
- `Error Flag`
- `Duplicate Type`
- `Duplicate Reason`
- `Duplicate Of`
- `Duplicate Flag`
- `Gmail Draft Status`

Mapping:

- `Company`: Project 05 company
- `Email`: Project 05 email
- `Notes`: compact score and reason
- `Segment`: Project 05 niche
- `Lead Type`: `Project 05`
- `Assistant Status`: `NEW`
- `Selected Contact`: Project 05 email
- `Personalization Note`: recommended angle plus personal note
- `Duplicate Flag`: `FALSE`
- `Gmail Draft Status`: `NOT_CREATED`

The outreach/draft/date/error duplicate columns are intentionally left blank for Project 03.5 to process later.

Core outreach fields stored locally:

- `company_name`
- `normalized_domain`
- `contact_email`
- `niche`
- `score`
- `status`
- `reason`
- `recommended_angle`
- `personal_note`
- `source`
- `exported_at`
- `created_at`
- `updated_at`

## Import Real Leads From CSV

Use this path when you have real leads from manual research, a directory export, or another trusted source. Imported leads are stored in Project 05 SQLite as `REVIEW`, with `lead_source_mode = manual`, so you can approve or reject them in Lead Control before export.

Input CSV headers:

- `company`
- `email`
- `domain`
- `website_url`
- `niche`
- `source`
- `notes`

Run:

```powershell
python scripts\import_real_leads_csv.py path\to\real_leads.csv
```

Import behavior:

- `source` uses the CSV value, or `MANUAL_CSV` if blank
- mock/demo source values are converted to `MANUAL_CSV`
- imported leads are never marked `MOCK`
- imported leads start as `REVIEW`
- local duplicates are skipped by normalized domain, website URL, or email
- no emails are sent

After import, open Lead Control, approve suitable leads, then run the Project 03.5 CSV export command.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional but recommended for local qualification:

```powershell
ollama pull qwen3:8b
ollama serve
```

## Run The Local Panel

```powershell
uvicorn app:app --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

Use **Run Once** for a single manual pass. **Start Agents** enables a small background loop that runs, waits, and runs again until you click **Stop Agents**.

## Local-Only Mode

Local-only mode is the default and is safe.

If Google credentials are missing, Google libraries are not installed, or writing is disabled, Project 05 logs a `WARNING` and continues with local SQLite only. It does not crash and it does not touch Project 03.5.

## Configure Ollama

The default model is `qwen3:8b`.

Set it in `.env`:

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
```

Or edit `config.yaml`:

```yaml
ollama:
  base_url: "http://127.0.0.1:11434"
  default_model: "qwen3:8b"
```

## Configure Lead Source Mode

`lead_source_mode` controls the broad workflow path:

- `mock`: deterministic local mock leads, clearly marked as `MOCK`
- `manual`: reserved for a manual/imported lead input path
- `search`: uses `LeadDiscoveryAgent` and the configured search provider

Important: `mock` mode is for testing the workflow only. Mock leads cannot be approved for outreach in the UI/API and cannot be exported to the Project 03.5 CSV unless you explicitly pass the testing-only `--include-mock` flag.

## Real Lead Discovery Agent

Project 05 has a minimal provider architecture for discovery:

- `LeadDiscoveryAgent` orchestrates discovery providers
- `SearchProvider.search(query, limit)` is the provider interface
- `LeadCandidate` is the shared candidate object providers return
- provider factory names are `mock`, `seed_urls`, `brave`, and `google_places`

Provider status:

- `seed_urls`: free/local provider; reads real URLs from `data/search_seed_urls.txt` and fetches page content
- `mock`: testing-only provider; used only by `lead_source_mode: "mock"`
- `brave`: planned provider scaffold; requires `BRAVE_SEARCH_API_KEY`; no real API call is made yet
- `google_places`: planned provider scaffold; requires `GOOGLE_PLACES_API_KEY`; no real API call is made yet

To use the first real discovery tool:

1. Add one real business website URL per line to `data/search_seed_urls.txt`.
2. Set `lead_source_mode: "search"` in `config.yaml` or `LEAD_SOURCE_MODE=search` in `.env`.
3. Keep `search.provider: "seed_urls"` unless you are developing a future provider.
4. Run the app and click **Run Once**.

Search mode fetches each seed URL and extracts only observed data:

- company from page title, site name, or domain
- domain from the URL
- email only if visibly present in page text
- website URL from the seed URL
- `source = SEARCH`
- `lead_source_mode = search`

Search mode does not use mock templates. If `data/search_seed_urls.txt` has no usable URLs, Project 05 fails clearly instead of fabricating leads.

Default search config:

```yaml
search:
  provider: "seed_urls"
  location: "Inverness, Scotland"
  max_results: 10
  seed_urls_path: "data/search_seed_urls.txt"
```

Environment variables for planned API providers:

```text
BRAVE_SEARCH_API_KEY=
GOOGLE_PLACES_API_KEY=
```

Do not scrape the Google Search or Google Maps browser UI. If Google Maps/Places discovery is added later, use an approved API/provider path with explicit credentials and rate limits.

Default:

```yaml
lead_source_mode: "mock"
```

Or in `.env`:

```text
LEAD_SOURCE_MODE=mock
```

## Configure Minimum Qualification Score

Only leads with:

- `status == QUALIFIED`
- `score >= minimum_score`

are eligible for Google Sheets append.

Default:

```yaml
qualification:
  minimum_score: 7
```

Or in `.env`:

```text
MINIMUM_QUALIFICATION_SCORE=7
```

## Legacy Google Sheets Optional Fallback

Google Sheets code remains in place, but it is optional/fallback. The Project 05 SQLite database is the lead control source of truth.

The preferred Project 05 to Project 03.5 handoff is the CSV export above, because it matches the current Project 03.5 Google Sheet columns exactly. The older optional Sheets writer remains available for experimentation and still expects Project 05-style columns.

Legacy optional writer columns:

- `company_name`
- `website_url`
- `contact_email`
- `niche`
- `score`
- `status`
- `recommended_angle`
- `personal_note`
- `reason`
- `source_query`
- `source`
- `created_at`

`config.yaml` intentionally contains a placeholder spreadsheet ID so real Google Sheet IDs are not committed:

```yaml
google_sheets:
  spreadsheet_id: "YOUR_SPREADSHEET_ID"
  worksheet_name: "Leads"
  write_enabled: false
```

Google Sheets is optional/fallback and is not required for the DB-first flow. If you want to use the legacy Sheets writer locally, set your own `spreadsheet_id` in `config.yaml` or use the `.env` variables below. Keep `write_enabled: false` unless you deliberately want Project 05 to write through the optional fallback.

To enable real reads/writes, install optional Google libraries:

```powershell
pip install google-api-python-client google-auth
```

Then configure `.env`:

```text
GOOGLE_SHEETS_WRITE_ENABLED=true
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account.json
GOOGLE_SHEETS_SPREADSHEET_ID=YOUR_SPREADSHEET_ID
GOOGLE_SHEETS_WORKSHEET_NAME=Leads
```

If the worksheet tab is not named `Leads`, change `GOOGLE_SHEETS_WORKSHEET_NAME`.

## Deduplication

Project 05 deduplicates against:

- Local Project 05 SQLite leads
- Existing Google Sheet rows, if Google Sheets is configured as an optional fallback

It does not deduplicate against the Project 03.5 SQLite database.

Deduplication checks:

- normalized domain
- normalized website URL
- normalized contact email
- company name, only when domain/email are missing

## Pre-Filter

The pre-filter rejects obvious bad leads before Ollama qualification.

It rejects leads with:

- missing website URL
- blocked/social/listing domains such as Facebook, Instagram, LinkedIn, Yelp, Tripadvisor, Google Maps, Amazon, eBay, Etsy, YouTube, and TikTok
- missing or generic company names
- search-intent mismatch
- no clear small/medium business signal
- likely chain or enterprise signal
- no clear outreach/workflow automation fit

Pre-filter results are stored in SQLite and shown in the panel.

## API

- `GET /`
- `GET /api/status`
- `POST /api/start`
- `POST /api/stop`
- `POST /api/run-once`
- `GET /api/logs`
- `GET /api/leads`

POST bodies:

```json
{
  "niche": "local accountants needing workflow automation",
  "limit": 5,
  "model_name": "qwen3:8b"
}
```

## Tests

```powershell
pytest
```

Tests cover:

- domain, URL, and email deduplication
- blocked social/platform domains
- pre-filter rejects bad leads
- pre-filter accepts plausible small business leads
- Google Sheet duplicate matching with mocked rows

## Notes

- No LangChain, CrewAI, AutoGen, Docker, Celery, Redis, Kubernetes, or frontend framework.
- The current lead finder defaults to mock mode on purpose so the MVP remains debuggable.
- The first real discovery path uses seed URLs; richer providers can be added later without changing the rest of the workflow.
