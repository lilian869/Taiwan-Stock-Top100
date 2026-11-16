# Local, zero-additional-cloud-cost Fugle polling runner.
# Run from the repository root. Reads FUGLE_API_KEY from the current user's environment.
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

if (-not $env:FUGLE_API_KEY) {
    Write-Log "ERROR: FUGLE_API_KEY environment variable is missing."
    exit 2
}

Write-Log "Runner started. Polling only during Taiwan market hours."
while ($true) {
    $now = Get-Date
    $weekday = $now.DayOfWeek -ne [DayOfWeek]::Saturday -and $now.DayOfWeek -ne [DayOfWeek]::Sunday
    $marketStart = Get-Date -Hour 9 -Minute 0 -Second 0
    $marketEnd = Get-Date -Hour 13 -Minute 30 -Second 0

    if (-not $weekday -or $now -lt $marketStart -or $now -gt $marketEnd) {
        Write-Log "Market window ended or non-trading weekday. Runner stopped."
        break
    }

    $minute = [int]$now.ToString("mm")
    $nextMinute = ([math]::Floor($minute / 5) + 1) * 5
    $next = $now.Date.AddHours($now.Hour).AddMinutes($nextMinute)
    if ($next -le $now) { $next = $next.AddMinutes(5) }

    Write-Log "Starting 100-symbol snapshot."
    if (Test-Path $Candidate) { Remove-Item $Candidate -Force }
    & python (Join-Path $PSScriptRoot "fugle_intraday_snapshot.py") --output "runtime/fugle_intraday_candidate.json" --delay 1.1 --market-hours-only
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0 -and (Test-Path $Candidate)) {
        Move-Item -Path $Candidate -Destination $Latest -Force
        Write-Log "SUCCESS: replaced latest snapshot with a complete 100-symbol result."
    } else {
        Write-Log "WARNING: snapshot failed (exit=$exitCode); previous valid snapshot retained."
        if (Test-Path $Candidate) { Remove-Item $Candidate -Force }
    }

    $waitSeconds = [int][math]::Ceiling(($next - (Get-Date)).TotalSeconds)
    if ($waitSeconds -gt 0) {
        Start-Sleep -Seconds $waitSeconds
    }
}
