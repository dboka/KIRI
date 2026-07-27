param(
  [string]$TaskName = "KIRI-LV v0.1.3 Daily Update",
  [string]$Time = "08:00",
  [switch]$NoGitPush
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ScriptDir "run_daily_v013.ps1"
$RunnerArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
if (-not $NoGitPush) {
  $RunnerArgs = "$RunnerArgs --commit-and-push"
}

$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument $RunnerArgs

$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Description "Runs the clean KIRI-LV v0.1.3 60-day data refresh and frontend archive update." `
  -Force

Write-Host "Registered scheduled task '$TaskName' at $Time"
if ($NoGitPush) {
  Write-Host "Git push is disabled for this task."
} else {
  Write-Host "Git push is enabled for this task."
}
