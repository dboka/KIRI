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
