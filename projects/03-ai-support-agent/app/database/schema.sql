CREATE TABLE IF NOT EXISTS support_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id TEXT,
  created_at TEXT NOT NULL,
  source TEXT NOT NULL,
  customer_from TEXT,
  subject TEXT,
  category TEXT,
  reply TEXT,
  next_step TEXT,
  raw_email TEXT NOT NULL,
  raw_model_output TEXT,
  parse_ok INTEGER NOT NULL DEFAULT 1,
  error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_support_logs_created_at ON support_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_support_logs_category ON support_logs(category);
CREATE INDEX IF NOT EXISTS idx_support_logs_request_id ON support_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_support_logs_parse_ok ON support_logs(parse_ok);

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    daily_limit INTEGER
);

CREATE TABLE IF NOT EXISTS api_key_usage_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL,
    day TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(key_hash, day)
);