$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$ProjectDir = Split-Path -Parent $ScriptDir
$LogDir = Join-Path $ProjectDir "DATA_LAST_60\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "daily_v013_$Stamp.log"

try {
  Start-Transcript -Path $LogPath -Force | Out-Null
  python .\run_daily_v013.py @args
  $ExitCode = $LASTEXITCODE
} finally {
  Stop-Transcript | Out-Null
}

exit $ExitCode
