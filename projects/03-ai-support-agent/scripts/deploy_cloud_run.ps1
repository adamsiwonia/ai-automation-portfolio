#Requires -Version 5.1

[CmdletBinding()]
param(
    [string]$ServiceName = "ai-support-agent-03",
    [string]$Region = "europe-west2",
    [string]$ExpectedProjectId = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Fail {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

function Invoke-Gcloud {
    param([string[]]$Arguments)

    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "gcloud command failed with exit code $LASTEXITCODE. Review the output above and retry."
    }
}

function Test-GcloudSecretExists {
    param([string]$SecretName)

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & gcloud secrets describe $SecretName --project $activeProject --format "none" --quiet *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Fail "gcloud CLI was not found on PATH. Install Google Cloud SDK or run this from the Google Cloud SDK PowerShell."
}

$projectRoot = (Get-Location).Path
if (-not (Test-Path (Join-Path $projectRoot "app\main.py")) -or -not (Test-Path (Join-Path $projectRoot "Dockerfile"))) {
    Fail "This script must be run from the Project 03 root folder. Current folder: $projectRoot"
}

$activeProject = (& gcloud config get-value project --quiet 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($activeProject) -or $activeProject -eq "(unset)") {
    Fail "No active gcloud project is selected. Run: gcloud config set project YOUR_PROJECT_ID"
}

Write-Host "Project folder: $projectRoot"
Write-Host "Active gcloud project: $activeProject"
Write-Host "Cloud Run service: $ServiceName"
Write-Host "Cloud Run region: $Region"
Write-Host "Required secret mappings: OPENAI_API_KEY, DEMO_API_KEY from Secret Manager latest versions."

if (-not [string]::IsNullOrWhiteSpace($ExpectedProjectId) -and $activeProject -ne $ExpectedProjectId) {
    Fail "Wrong gcloud project selected. Active project is '$activeProject', expected '$ExpectedProjectId'. Run: gcloud config set project $ExpectedProjectId"
}

$includeAdminApiKey = Test-GcloudSecretExists -SecretName "ADMIN_API_KEY"
if ($includeAdminApiKey) {
    Write-Host "Optional secret mapping included: ADMIN_API_KEY"
} else {
    Write-Host "Optional secret mapping skipped: ADMIN_API_KEY secret was not found in project '$activeProject'."
}

$confirmation = Read-Host "Type DEPLOY to deploy to project '$activeProject'"
if ($confirmation -ne "DEPLOY") {
    Fail "Deploy cancelled before any changes. If the active project is wrong, run: gcloud config set project YOUR_PROJECT_ID"
}

$deployArgs = @(
    "run", "deploy", $ServiceName,
    "--project", $activeProject,
    "--region", $Region,
    "--source", ".",
    "--allow-unauthenticated",
    "--set-secrets", "OPENAI_API_KEY=OPENAI_API_KEY:latest",
    "--set-secrets", "DEMO_API_KEY=DEMO_API_KEY:latest"
)

if ($includeAdminApiKey) {
    $deployArgs += @("--set-secrets", "ADMIN_API_KEY=ADMIN_API_KEY:latest")
}

Write-Host "Starting Cloud Run deploy..."
Invoke-Gcloud -Arguments $deployArgs

$serviceUrl = (& gcloud run services describe $ServiceName --project $activeProject --region $Region --format "value(status.url)" --quiet).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($serviceUrl)) {
    Fail "Deploy finished, but the service URL could not be read from Cloud Run."
}

$healthUrl = "$($serviceUrl.TrimEnd('/'))/health"
Write-Host "Service URL: $serviceUrl"
Write-Host "Running health check: $healthUrl"

$healthStatusCode = $null
$healthBody = ""
try {
    $healthResponse = Invoke-WebRequest -Uri $healthUrl -Method Get -TimeoutSec 30 -UseBasicParsing
    $healthStatusCode = [int]$healthResponse.StatusCode
    $healthBody = [string]$healthResponse.Content
} catch {
    $errorResponse = $_.Exception.Response
    if ($null -eq $errorResponse) {
        Fail "Deploy finished, but /health check failed at $healthUrl. $($_.Exception.Message)"
    }

    $healthStatusCode = [int]$errorResponse.StatusCode
    $stream = $errorResponse.GetResponseStream()
    if ($null -ne $stream) {
        $reader = New-Object System.IO.StreamReader($stream)
        try {
            $healthBody = $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
    }
}

Write-Host "Health status code: $healthStatusCode"
Write-Host "Health response body:"
Write-Host $healthBody

if ($healthStatusCode -lt 200 -or $healthStatusCode -ge 300) {
    Fail "Deploy finished, but /health returned HTTP $healthStatusCode."
}

Write-Host "Health check passed."
