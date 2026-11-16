# One-shot runner for Windows Task Scheduler.
# Each scheduled invocation fetches one complete snapshot and exits.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Runtime = Join-Path $Root "runtime"
$Candidate = Join-Path $Runtime "fugle_intraday_candidate.json"
$Latest = Join-Path $Runtime "fugle_intraday_latest.json"
$LogDir = Join-Path $Runtime "logs"
New-Item -ItemType Directory -Force -Path $Runtime, $LogDir | Out-Null
$Log = Join-Path $LogDir ("runner-" + (Get-Date -Format "yyyyMMdd") + ".log")

function Write-Log([string]$Message) {
    Add-Content -Path $Log -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message) -Encoding UTF8
}

# Scheduled tasks do not inherit the environment of an already-open PowerShell window.
$env:FUGLE_API_KEY = [Environment]::GetEnvironmentVariable("FUGLE_API_KEY", "User")
if (-not $env:FUGLE_API_KEY) {
    Write-Log "ERROR: User-scoped FUGLE_API_KEY is missing."
    exit 2
}

$Now = Get-Date
if ($Now.DayOfWeek -eq [DayOfWeek]::Saturday -or $Now.DayOfWeek -eq [DayOfWeek]::Sunday) {
    Write-Log "SKIP: weekend."
    exit 0
}
if ($Now.TimeOfDay -lt [TimeSpan]::FromHours(9) -or $Now.TimeOfDay -ge [TimeSpan]::FromHours(13.5)) {
    Write-Log "SKIP: outside Taiwan market hours."
    exit 0
}

if (Test-Path $Candidate) { Remove-Item $Candidate -Force }
Write-Log "Starting one-shot 100-symbol snapshot."
& python (Join-Path $PSScriptRoot "fugle_intraday_snapshot.py") --output "runtime/fugle_intraday_candidate.json" --delay 1.1 --market-hours-only
$ExitCode = $LASTEXITCODE

if ($ExitCode -eq 0 -and (Test-Path $Candidate)) {
    Move-Item -Path $Candidate -Destination $Latest -Force
    Write-Log "SUCCESS: replaced latest snapshot with a complete 100-symbol result."
    exit 0
}

Write-Log "WARNING: snapshot failed (exit=$ExitCode); previous valid snapshot retained."
if (Test-Path $Candidate) { Remove-Item $Candidate -Force }
exit $(if ($ExitCode -eq 0) { 1 } else { $ExitCode })
