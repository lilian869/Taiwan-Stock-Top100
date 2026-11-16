# Install one-shot 5-minute polling tasks for Taiwan market hours.
# Run from the repository root in Windows PowerShell 5.1.
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
$UserId = "$env:USERDOMAIN\$env:USERNAME"
$StartDate = (Get-Date).Date.AddDays(1)
while ($StartDate.DayOfWeek -eq [DayOfWeek]::Saturday -or $StartDate.DayOfWeek -eq [DayOfWeek]::Sunday) {
    $StartDate = $StartDate.AddDays(1)
}
$StartBoundary = $StartDate.ToString("yyyy-MM-dd") + "T09:00:00"

$ActionArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
$DaysXml = @"
<ScheduleByWeek>
  <WeeksInterval>1</WeeksInterval>
  <DaysOfWeek>
    <Monday />
    <Tuesday />
    <Wednesday />
    <Thursday />
    <Friday />
  </DaysOfWeek>
</ScheduleByWeek>
"@
$Xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Runs one Fugle Top100 snapshot every 5 minutes on weekdays from 09:00 to 13:30. Local-only; does not publish the website.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$StartBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <Repetition>
        <Interval>PT5M</Interval>
        <Duration>PT4H30M</Duration>
        <StopAtDurationEnd>true</StopAtDurationEnd>
      </Repetition>
      $DaysXml
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$UserId</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT4M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>$ActionArgs</Arguments>
      <WorkingDirectory>$RepoRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

Register-ScheduledTask -TaskName $TaskName -Xml $Xml -Force | Out-Null
Write-Host "Installed one-shot polling schedule."
Write-Host "Runs weekdays every 5 minutes from 09:00 through 13:25."
Write-Host "Each run exits after one snapshot; max runtime 4 minutes."
Write-Host "Working directory: $RepoRoot"
Write-Host "Latest snapshot and logs remain under .\runtime\ (not published)."
