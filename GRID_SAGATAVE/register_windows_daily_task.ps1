param(
  [string]$ProjectDir = (Split-Path -Parent $PSScriptRoot),
  [string]$TaskName = "KIRI-LV v0.1.3 Daily Update",
  [string]$DailyAt = "08:00"
)

$ErrorActionPreference = "Stop"
$ProjectDir = (Resolve-Path -LiteralPath $ProjectDir).Path
$Runner = Join-Path $ProjectDir "GRID_SAGATAVE\run_daily_v013.ps1"
if (-not (Test-Path -LiteralPath $Runner -PathType Leaf)) {
  throw "Daily runner not found: $Runner"
}

$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$ActionArguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Runner`" --commit-and-push"
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $ActionArguments -WorkingDirectory (Split-Path -Parent $Runner)
$Trigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet `
  -StartWhenAvailable `
  -WakeToRun `
  -RestartCount 3 `
  -RestartInterval (New-TimeSpan -Minutes 20) `
  -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
  -MultipleInstances IgnoreNew `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Principal $Principal `
  -Settings $Settings `
  -Description "KIRI-LV daily data, all indicator histories, SWI climatology validation, and GitHub Pages publish." `
  -Force | Out-Null

$Task = Get-ScheduledTask -TaskName $TaskName
$Info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
  TaskName = $Task.TaskName
  State = $Task.State
  NextRunTime = $Info.NextRunTime
  StartWhenAvailable = $Task.Settings.StartWhenAvailable
  WakeToRun = $Task.Settings.WakeToRun
  RestartCount = $Task.Settings.RestartCount
  RestartInterval = $Task.Settings.RestartInterval
  Action = "$($Task.Actions.Execute) $($Task.Actions.Arguments)"
} | Format-List
