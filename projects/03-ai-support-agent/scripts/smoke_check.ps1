param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = "",
    [string]$DbPath = "",
    [string]$EnvFile = ".env",
    [switch]$Strict
)

$ErrorActionPreference = "Stop"

$failures = @()
$warnings = @()

function Write-Section([string]$message) {
    Write-Host ""
    Write-Host "== $message =="
}

function Add-Pass([string]$message) {
    Write-Host "[PASS] $message" -ForegroundColor Green
}

function Add-Warn([string]$message) {
    $script:warnings += $message
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

function Add-Fail([string]$message) {
    $script:failures += $message
    Write-Host "[FAIL] $message" -ForegroundColor Red
}

function Get-DotEnvMap([string]$path) {
    $map = @{}
    if (-not (Test-Path -LiteralPath $path)) {
        return $map
    }

    foreach ($line in Get-Content -LiteralPath $path) {
        if ($line -match '^\s*#') { continue }
        if (-not ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$')) { continue }

        $key = $matches[1]
        $value = $matches[2].Trim()

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        $map[$key] = $value
    }

    return $map
}

function Get-StatusCodeFromError([System.Management.Automation.ErrorRecord]$errorRecord) {
    $statusCode = $null
    try {
        if ($errorRecord.Exception.Response -and $errorRecord.Exception.Response.StatusCode) {
            $statusCode = [int]$errorRecord.Exception.Response.StatusCode
        }
    } catch {
        $statusCode = $null
    }
    return $statusCode
}

function Invoke-SqliteQuery([string]$databasePath, [string]$query) {
    $pythonScript = @'
import json
import sqlite3
import sys

db_path = sys.argv[1]
query = sys.argv[2]

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
rows = conn.execute(query).fetchall()
print(json.dumps([dict(r) for r in rows], ensure_ascii=True))
'@

    $raw = $pythonScript | python - $databasePath $query
    if ($LASTEXITCODE -ne 0) {
        throw "Python sqlite query command failed."
    }

    if (-not $raw) {
        return @()
    }

    $parsed = $raw | ConvertFrom-Json
    if ($null -eq $parsed) {
        return @()
    }
    if ($parsed -is [System.Array]) {
        return $parsed
    }
    return @($parsed)
}

Write-Section "Input resolution"

$dotenv = Get-DotEnvMap -path $EnvFile
if (-not $ApiKey) {
    $ApiKey = (
        $env:DEMO_API_KEY,
        $env:API_KEY,
        $dotenv["DEMO_API_KEY"],
        $dotenv["API_KEY"]
    ) | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1
}

if (-not $DbPath) {
    $DbPath = (
        $env:DB_PATH,
        $dotenv["DB_PATH"]
    ) | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1
}

if (-not $DbPath) {
    $DbPath = "app/database/support_agent.sqlite"
}

Write-Host "Base URL: $BaseUrl"
Write-Host "DB path: $DbPath"
if ($ApiKey) {
    Add-Pass "API key resolved (value hidden)."
} else {
    Add-Warn "API key not found in params/env/.env; authorized OAuth start check will fail."
}

Write-Section "HTTP smoke checks"

try {
    $health = Invoke-RestMethod -Method GET -Uri "$BaseUrl/health" -TimeoutSec 15
    if ($health.status -eq "ok") {
        Add-Pass "GET /health returned status=ok."
    } else {
        Add-Fail "GET /health succeeded but payload is unexpected."
    }
} catch {
    Add-Fail "GET /health failed: $($_.Exception.Message)"
}

try {
    Invoke-WebRequest -Method GET -Uri "$BaseUrl/auth/google/start" -TimeoutSec 15 | Out-Null
    Add-Fail "GET /auth/google/start without auth should return 401, but returned success."
} catch {
    $statusCode = Get-StatusCodeFromError -errorRecord $_
    if ($statusCode -eq 401) {
        Add-Pass "GET /auth/google/start without key returns 401."
    } else {
        Add-Fail "GET /auth/google/start without key returned unexpected status: $statusCode"
    }
}

if ($ApiKey) {
    try {
        $oauthStart = Invoke-RestMethod -Method GET -Uri "$BaseUrl/auth/google/start" -Headers @{ "X-API-Key" = $ApiKey } -TimeoutSec 20
        if ($oauthStart.authorization_url -and $oauthStart.redirect_uri -and $oauthStart.scopes) {
            Add-Pass "GET /auth/google/start with API key returned authorization payload."
        } else {
            Add-Fail "GET /auth/google/start with API key returned incomplete payload."
        }
    } catch {
        Add-Fail "Authorized GET /auth/google/start failed: $($_.Exception.Message)"
    }
} else {
    Add-Fail "Missing API key for authorized GET /auth/google/start check."
}

Write-Section "Database checks"

if (-not (Test-Path -LiteralPath $DbPath)) {
    Add-Fail "SQLite DB not found at '$DbPath'."
} else {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Add-Fail "Python is not available in PATH; cannot run sqlite checks."
    } else {
        try {
            $mailboxRows = Invoke-SqliteQuery -databasePath $DbPath -query @"
SELECT
  id,
  mailbox_email,
  active,
  CASE
    WHEN refresh_token IS NOT NULL AND TRIM(refresh_token) <> '' THEN 1
    ELSE 0
  END AS has_refresh_token
FROM gmail_mailboxes
ORDER BY updated_at DESC
LIMIT 10
"@
            if (-not $mailboxRows -or $mailboxRows.Count -eq 0) {
                Add-Fail "No rows in gmail_mailboxes. OAuth callback probably did not persist mailbox."
            } else {
                $activeWithRefresh = @($mailboxRows | Where-Object { $_.active -eq 1 -and $_.has_refresh_token -eq 1 })
                if ($activeWithRefresh.Count -gt 0) {
                    Add-Pass "gmail_mailboxes has active mailbox with refresh_token."
                } else {
                    Add-Fail "gmail_mailboxes has no active mailbox with refresh_token."
                }
            }
        } catch {
            Add-Fail "Failed querying gmail_mailboxes: $($_.Exception.Message)"
        }

        try {
            $workerRows = Invoke-SqliteQuery -databasePath $DbPath -query @"
SELECT component, status, details, last_heartbeat_at
FROM runtime_status
WHERE component = 'worker'
LIMIT 1
"@
            if (-not $workerRows -or $workerRows.Count -eq 0) {
                Add-Fail "No worker heartbeat row in runtime_status."
            } else {
                $worker = $workerRows[0]
                if ((($worker.status) -as [string]).ToLowerInvariant() -eq "running") {
                    Add-Pass "Worker heartbeat status is running."
                } else {
                    Add-Warn "Worker heartbeat status is '$($worker.status)'."
                }

                try {
                    $hbAt = [DateTimeOffset]::Parse([string]$worker.last_heartbeat_at).UtcDateTime
                    $age = (Get-Date).ToUniversalTime() - $hbAt
                    if ($age.TotalMinutes -le 5) {
                        Add-Pass "Worker heartbeat is fresh (<=5 min)."
                    } else {
                        Add-Warn ("Worker heartbeat is stale: {0:N1} min old." -f $age.TotalMinutes)
                    }
                } catch {
                    Add-Warn "Could not parse worker heartbeat timestamp."
                }
            }
        } catch {
            Add-Fail "Failed querying runtime_status: $($_.Exception.Message)"
        }

        try {
            $supportRows = Invoke-SqliteQuery -databasePath $DbPath -query @"
SELECT id, created_at, source, category, parse_ok, error_message
FROM support_logs
ORDER BY id DESC
LIMIT 5
"@
            if (-not $supportRows -or $supportRows.Count -eq 0) {
                Add-Warn "No rows in support_logs yet."
            } else {
                Add-Pass "support_logs has recent rows."
                $failedRows = @($supportRows | Where-Object { $_.parse_ok -eq 0 -or ($_.error_message -as [string]) })
                if ($failedRows.Count -gt 0) {
                    Add-Warn "Recent support_logs include parse errors."
                } else {
                    Add-Pass "Recent support_logs have no parse errors."
                }
            }
        } catch {
            Add-Fail "Failed querying support_logs: $($_.Exception.Message)"
        }
    }
}

Write-Section "Summary"
Write-Host "Failures: $($failures.Count)"
Write-Host "Warnings: $($warnings.Count)"

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Failure details:" -ForegroundColor Red
    foreach ($item in $failures) {
        Write-Host " - $item"
    }
}

if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Warning details:" -ForegroundColor Yellow
    foreach ($item in $warnings) {
        Write-Host " - $item"
    }
}

if ($failures.Count -gt 0 -or ($Strict -and $warnings.Count -gt 0)) {
    exit 1
}

exit 0
