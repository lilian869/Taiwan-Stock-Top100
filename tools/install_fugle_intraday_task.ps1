# Run once in Windows PowerShell from the repository root.
# Requires Python 3.10+ and a user-scoped FUGLE_API_KEY environment variable.
$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Location).Path
$Runner = Join-Path $RepoRoot "tools\run_fugle_intraday_local.ps1"
if (-not (Test-Path $Runner)) {
    throw "Run this installer from the Taiwan-Stock-Top100 repository root."
}
if (-not $env:FUGLE_API_KEY) {
    Write-Host "Set the Fugle key first (do not put it in this script):"
    Write-Host '  [Environment]::SetEnvironmentVariable("FUGLE_API_KEY", "YOUR_KEY", "User")'
    throw "FUGLE_API_KEY is not available in this PowerShell session. Set it, reopen PowerShell, then rerun."
}
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 8:55AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "TaiwanStockTop100-FugleIntraday" -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Fetches Fugle Top100 quotes every 5 minutes during Taiwan market hours. Local-only; does not publish the website." -Force | Out-Null
Write-Host "Installed. The task starts at 08:55 on weekdays when this Windows user is logged in."
Write-Host "Keep the PC awake and connected from 08:55 to 13:30."
Write-Host "Logs and latest snapshot are saved under .\runtime\ (not docs/ and not published)."
