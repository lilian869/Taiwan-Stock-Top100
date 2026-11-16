# Install one-shot 5-minute polling tasks for Taiwan market hours.
# Run from the repository root in Windows PowerShell.
$ErrorActionPreference = "Stop"
$RepoRoot = (Get-Location).Path
$Runner = Join-Path $RepoRoot "tools\run_fugle_intraday_once.ps1"
if (-not (Test-Path $Runner)) {
    throw "Run this installer from the Taiwan-Stock-Top100 repository root."
}
$ApiKey = [Environment]::GetEnvironmentVariable("FUGLE_API_KEY", "User")
if (-not $ApiKey) {
    throw "User-scoped FUGLE_API_KEY is missing. Do not paste the key into this script."
}

$TaskName = "TaiwanStockTop100-FugleIntraday"
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`"" -WorkingDirectory $RepoRoot

$Triggers = @()
foreach ($Day in @("Monday","Tuesday","Wednesday","Thursday","Friday")) {
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At "9:00AM"
    $Trigger.Repetition.Interval = "PT5M"
    $Trigger.Repetition.Duration = "PT4H30M"
    $Triggers += $Trigger
}

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers -Settings $Settings -Principal $Principal -Description "Runs one Fugle Top100 snapshot every 5 minutes on weekdays from 09:00 to 13:30. Local-only; does not publish the website." -Force | Out-Null

Write-Host "Installed one-shot polling schedule."
Write-Host "Runs weekdays every 5 minutes from 09:00 through 13:25."
Write-Host "Each run exits after one snapshot; max runtime 4 minutes."
Write-Host "Working directory: $RepoRoot"
Write-Host "Latest snapshot and logs remain under .\runtime\ (not published)."
