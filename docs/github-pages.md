# GitHub Pages Deployment

KIRI-LV deploys as a static site from:

```text
GRID_SAGATAVE/frontend
```

The workflow is:

```text
.github/workflows/pages.yml
```

Expected live URL:

```text
https://dboka.github.io/KIRI/
```

## Deployment Contract

- Pushes to `main` trigger the Pages workflow.
- The frontend must work as static files; no backend is required.
- `.nojekyll` is included in `GRID_SAGATAVE/frontend` so GitHub Pages serves all data files directly.
- Large local input/intermediate data folders are not deployed.
- Interaktīvo grafiku vēsture tiek glabāta deterministiski saspiestās pašvaldību datnēs zem
  `frontend/data/indicator_history/<indicator>/<municipality_code>.json.gz`.
- `indicator_history/index.json` fiksē indikatorus, datumu pārklājumu un datņu skaitu;
  ikdienas workflow pārbauda, ka visu piecu indikatoru rindas sakrīt ar arhīva datumiem.

## Daily Data Refresh Contract

The operational data workflow is:

```text
.github/workflows/daily-data.yml
```

It runs on a self-hosted Windows runner every morning and can also be started manually from GitHub Actions. The job executes:

```powershell
python GRID_SAGATAVE\run_daily_v013.py --visible-days 60
```

The runner updates only the missing suffix of the 60-day window, preserves older JSON payloads under `frontend/data/dates` and `frontend/data/grid_values`, updates `archive_manifest.json`, cleans temporary H-SAF/SWI raw files, commits changed frontend data to `main`, and then the existing Pages workflow deploys the pushed static site.

The Windows wrapper is registered or repaired with:

```powershell
powershell -ExecutionPolicy Bypass -File GRID_SAGATAVE\register_windows_daily_task.ps1 -ProjectDir C:\Users\deniss.boka\MESLI_PROJECT\KIRI_PRODUCTION
```

The task synchronizes its dedicated `main` checkout before processing, validates the map payload, all five indicator-history charts, and the fixed SWI climatology payload before publishing. A rejected concurrent push is rebased and retried once. Task Scheduler retries a failed run three times at 20-minute intervals, starts a missed run when the computer becomes available, and wakes the computer when supported.

Expected live URL:

```text
https://dboka.github.io/KIRI/
```

## Quick Checks

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI
git status --short --branch
node --check GRID_SAGATAVE\frontend\src\main.js
python GRID_SAGATAVE\prepare_frontend_compact_pages_data.py
```

Then push:

```powershell
git push origin main
```
