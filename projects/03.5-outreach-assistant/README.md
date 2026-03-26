# Outreach Assistant (Project 03.5)

Draft-first outreach assistant that imports leads from Google Sheets into SQLite, processes them locally, generates outreach drafts, and syncs assistant outputs back to your existing sheet columns.

## Architecture

- Google Sheet is the input/review layer.
- SQLite is the system of record.
- Business logic runs in Python + SQLite (not sheet formulas).
- Pipeline: `import -> classify -> generate draft -> sync back`.

## Real Sheet Schema Mapping

### Import mapping

- `Company` -> `company_name` (backward compatible with `Firma`)
- `Email` -> raw contact value (parsed into valid email / contact form / malformed)
- `Date Sent` -> `last_contacted_at`
- `Follow Up Date` -> `follow_up_due_at` (backward compatible with `Follow-up Date`)
- `Response` -> `human_response` (preserved, never overwritten)
- `Notes` -> `notes` (preserved, never overwritten)
- `Segment` -> lead category source of truth
- `Angle` (fallback `Note`) -> optional lightweight personalization input
- `Assistant Status` -> source status used by processing

### Sync mapping

Assistant writes only to these existing columns:

- `Lead Type`
- `Assistant Status`
- `Selected Contact`
- `Draft Type`
- `Draft Subject`
- `Draft Body`
- `Personalization Note`
- `Last Processed At`
- `Error Flag`
- `Duplicate Flag`
- `Duplicate Type`
- `Duplicate Of`
- `Duplicate Reason`

The assistant does not write to `Response` or `Notes`.

### Follow-Up Workflow

- `Response` not empty -> `DONE`
- Email is URL/contact form -> `CONTACT_FORM_REVIEW`
- Email malformed -> `EMAIL_NEEDS_REVIEW`
- `Date Sent` empty -> `FIRST_TOUCH_READY`
- `Date Sent` present and `Follow Up Date` equals today -> `FOLLOW_UP_READY`
- `Follow Up Date` empty -> `DONE` (no follow-up draft)
- `Follow Up Date` not today -> `DONE` (no follow-up draft)
- Follow-up draft stages are limited to two variants:
  - stage 1 -> `follow_up_1`
  - stage 2 -> `follow_up_2`
  - stage > 2 -> no new follow-up draft (`DONE`)

### Draft Variants and Personalization

- First-touch drafts rotate across template styles: `soft`, `direct`, `bold`.
- First-touch drafts also rotate across a small opener set (deterministic from row seed).
- Personalization inserts exactly one short sentence when `Angle` (or fallback `Note`) is present.
- When `Angle` is missing, first-touch drafts are generated normally without personalization.
- Variant tracking is stored in SQLite on `outreach_items`:
  - `template_variant`
  - `opener_variant`
  - `personalization_used`
  - `follow_up_stage`

### Duplicate Handling

- Hard duplicates are detected by same normalized email address, same normalized contact form URL, or same normalized selected contact value.
- Soft duplicates are detected by same email domain with different email addresses.
- Hard duplicates are flagged and blocked from outreach generation (`DONE` instead of outreach-ready).
- Soft duplicates are flagged for manual review and still keep normal outreach classification.
- Duplicate metadata is persisted in SQLite and synced to `Duplicate Flag`, `Duplicate Type`, `Duplicate Of`, and `Duplicate Reason`.
- Gmail draft creation excludes hard duplicates.

## Project Structure

```text
app/
  core/
    config.py
    enums.py
  database/
    db.py
    schema.sql
  repositories/
    leads.py
  services/
    normalization.py
    classification.py
    drafting.py
    gmail.py
    sheets.py
    pipeline.py

scripts/
  import_from_sheet.py
  process_leads.py
  push_drafts_to_gmail.py
  sync_to_sheet.py
  run_pipeline.py

tests/
  test_normalization.py
  test_classification.py
  test_drafting.py
  test_duplicates.py
  test_repository_preserve_fields.py
  test_sync_mapping.py
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set values for:

- `GOOGLE_APPLICATION_CREDENTIALS`
- `GOOGLE_SPREADSHEET_ID`
- optional overrides only if your headers differ
- `GMAIL_OAUTH_CLIENT_SECRETS` (OAuth desktop/client secret JSON)
- `GMAIL_TOKEN_PATH` (where OAuth token will be stored)

## Gmail Draft Setup (No Auto-Send)

1. In Google Cloud Console, enable **Gmail API** for your project.
2. Configure OAuth consent screen (External or Internal depending on account type).
3. Create OAuth client credentials of type **Desktop app**.
4. Download the OAuth client JSON and set `GMAIL_OAUTH_CLIENT_SECRETS` in `.env`.
5. Run the Gmail push script once; browser consent opens and `GMAIL_TOKEN_PATH` token file is saved.

The assistant only creates Gmail drafts and never sends emails automatically.

## Run Commands

Validate local config:

```bash
python scripts/check_config.py
```

Initialize DB schema:

```bash
python scripts/import_from_sheet.py --init-db --sheet-name Leads
```

Import from Google Sheet:

```bash
python scripts/import_from_sheet.py --sheet-name Leads
```

Process (classify + generate drafts):

```bash
python scripts/process_leads.py
```

Push ready drafts to Gmail (draft-only):

```bash
python scripts/push_drafts_to_gmail.py
```

Force create new Gmail drafts even if row already has a Gmail draft ID:

```bash
python scripts/push_drafts_to_gmail.py --force
```

Push drafts and write sheet marker (for example `GMAIL_DRAFT_CREATED`):

```bash
python scripts/push_drafts_to_gmail.py --sync-marker --sheet-name Leads
```

Dry-run sync (no writes):

```bash
python scripts/sync_to_sheet.py --sheet-name Leads --dry-run
```

Real sync:

```bash
python scripts/sync_to_sheet.py --sheet-name Leads
```

Optional full pipeline:

```bash
python scripts/run_pipeline.py --sheet-name Leads
```

## Testing

```bash
pytest -q
```
