PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  external_id TEXT,
  source_sheet TEXT NOT NULL,
  source_row_number INTEGER NOT NULL,
  company_name TEXT NOT NULL,
  website TEXT,
  notes TEXT,
  segment TEXT,
  angle TEXT,
  human_response TEXT,
  source_status TEXT,
  raw_contact_name TEXT,
  raw_contact_value TEXT,
  last_contacted_at TEXT,
  follow_up_due_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_sheet, source_row_number)
);

CREATE INDEX IF NOT EXISTS idx_leads_source_row
  ON leads(source_sheet, source_row_number);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id INTEGER NOT NULL,
  full_name TEXT,
  raw_value TEXT,
  email TEXT,
  contact_form_url TEXT,
  malformed_value TEXT,
  channel TEXT NOT NULL
    CHECK (channel IN ('EMAIL', 'CONTACT_FORM', 'MALFORMED', 'UNKNOWN')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_lead
  ON contacts(lead_id);

CREATE INDEX IF NOT EXISTS idx_contacts_email
  ON contacts(email);

CREATE TABLE IF NOT EXISTS outreach_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id INTEGER NOT NULL,
  contact_id INTEGER,
  classification TEXT NOT NULL
    CHECK (
      classification IN (
        'FIRST_TOUCH_READY',
        'FOLLOW_UP_READY',
        'FOLLOW_UP_SKIPPED',
        'CONTACT_FORM_REVIEW',
        'EMAIL_NEEDS_REVIEW',
        'DONE'
      )
    ),
  reason TEXT,
  duplicate_flag INTEGER NOT NULL DEFAULT 0
    CHECK (duplicate_flag IN (0, 1)),
  duplicate_type TEXT
    CHECK (duplicate_type IN ('HARD', 'SOFT') OR duplicate_type IS NULL),
  duplicate_of_lead_id INTEGER,
  duplicate_reason TEXT,
  template_variant TEXT,
  opener_variant TEXT,
  personalization_used INTEGER NOT NULL DEFAULT 0
    CHECK (personalization_used IN (0, 1)),
  follow_up_stage INTEGER NOT NULL DEFAULT 0,
  pipeline_state TEXT NOT NULL DEFAULT 'PENDING'
    CHECK (pipeline_state IN ('PENDING', 'DRAFTED', 'REVIEWED', 'DONE')),
  selected_for_sync INTEGER NOT NULL DEFAULT 1,
  gmail_draft_id TEXT,
  gmail_draft_for_draft_id INTEGER,
  gmail_draft_created_at TEXT,
  source_last_synced_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (lead_id),
  FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
  FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE SET NULL,
  FOREIGN KEY (duplicate_of_lead_id) REFERENCES leads(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_outreach_classification
  ON outreach_items(classification);

CREATE INDEX IF NOT EXISTS idx_outreach_selected
  ON outreach_items(selected_for_sync);

CREATE INDEX IF NOT EXISTS idx_outreach_duplicate_flag
  ON outreach_items(duplicate_flag);

CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  outreach_item_id INTEGER NOT NULL,
  version INTEGER NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  generator TEXT NOT NULL DEFAULT 'template-v1',
  selected_for_sync INTEGER NOT NULL DEFAULT 1,
  synced_to_sheet INTEGER NOT NULL DEFAULT 0,
  synced_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (outreach_item_id) REFERENCES outreach_items(id) ON DELETE CASCADE,
  UNIQUE (outreach_item_id, version)
);

CREATE INDEX IF NOT EXISTS idx_drafts_unsynced
  ON drafts(synced_to_sheet, selected_for_sync);
