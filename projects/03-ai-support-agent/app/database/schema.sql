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