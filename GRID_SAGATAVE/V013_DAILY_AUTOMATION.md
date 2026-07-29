# KIRI-LV v0.1.3 Daily Automation

This release starts from the clean `v0.1.2` tag and keeps the existing KIRI risk logic unchanged.

## Daily Local Run

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE
.\run_daily_v013.ps1 --commit-and-push
```

The runner keeps a 60-day frontend calendar window, commits the refreshed frontend payload, and pushes to `main` when `--commit-and-push` is used. Older processed dates are listed in:

```text
GRID_SAGATAVE/frontend/data/archive_manifest.json
```

By default the daily runner processes only the newest available H-SAF date, then rolls the frontend JSON window forward. Use `--rebuild-window` only when the full 60-day source/intermediate window must be rebuilt.

## Source Updates

CLIDATA is downloaded by the existing `prepare_last_60_precip_obs.py` script and still requires these environment variables:

```text
CLIDATA_ORACLE_USER
CLIDATA_ORACLE_PASSWORD
CLIDATA_ORACLE_DSN
CLIDATA_ELEMENT
```

H-SAF and SWI source folders are reused from the existing local archives by default. If download commands are available, set:

```text
KIRI_HSAF_UPDATE_COMMAND
KIRI_SWI_UPDATE_COMMAND
```

The runner executes those commands before rebuilding the 60-day data window.

## Windows Task Scheduler

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE
.\register_daily_v013_task.ps1 -Time 08:00
```
