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

$MesliDir = Split-Path -Parent $ProjectDir
$HsafProject = Join-Path $MesliDir "FTP_TRYING"
$HsafRoot = Join-Path $HsafProject "data\h28_latvia_nc"
$SwiProject = Join-Path $MesliDir "COPERNICUS_SWI"
$SwiDailyDir = Join-Path $SwiProject "data\grid_tiffs\daily_swi"
$RequiredFiles = @(
  (Join-Path $HsafProject "h28_downloader.py"),
  (Join-Path $HsafProject ".env"),
  (Join-Path $SwiProject "copernicus_swi_flow.py"),
  (Join-Path $SwiProject "make_lv_grid_swi_tiffs.py"),
  (Join-Path $SwiProject ".env")
)
foreach ($RequiredFile in $RequiredFiles) {
  if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
    throw "Required daily source file not found: $RequiredFile"
  }
}

$PowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$ActionArguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Runner`" --commit-and-push --hsaf-project `"$HsafProject`" --hsaf-root `"$HsafRoot`" --swi-project `"$SwiProject`" --swi-daily-dir `"$SwiDailyDir`""
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
