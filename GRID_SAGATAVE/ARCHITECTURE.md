# KIRI-LV v0.1.3 Operational Architecture

This repository keeps one production frontend data layout and one operational daily update contract. The goal is fast map loading, a rolling latest 60-day product, preserved JSON history, and source/raw cleanup after each successful run.

## Current Folder Map

- `GRID_SAGATAVE/frontend`
  - Static GitHub Pages application.
  - `index.html`, `src/main.js`, and `src/styles.css` are the browser app.
  - The browser loads only the active date overview and one municipality grid value file at a time.

- `GRID_SAGATAVE/frontend/data`
  - Production data payload for GitHub Pages.
  - `calendar_manifest.json` is the latest 60-day date index and default date selector.
  - `archive_manifest.json` lists older processed dates outside the latest 60-day calendar window.
  - `data_metadata.json` is the compact data release metadata.
  - `municipalities.geojson` and `municipality_boundaries` are municipality overview/boundary geometry.
  - `grid_static` is the only canonical 1 km grid geometry folder.
  - `grid_values/<date>/<municipality_code>.json` stores daily values only.
  - `dates/<date>/overview.geojson` stores the daily municipality overview layer.
  - `dates/<date>/manifest.json` connects one date, one municipality, static geometry, and daily values.

- `GRID_SAGATAVE/config`
  - Normalization and risk method configuration.

- `GRID_SAGATAVE/src/normalization`
  - Shared KIRI risk normalization code.

- `GRID_SAGATAVE/clean`
  - Human-readable latest data manifest. It points to the production data layout instead of duplicating hundreds of MB.

- `DATA_LAST_60`
  - Local latest input/intermediate data source for regeneration. Ignored by git.

- External local source projects
  - `FTP_TRYING` stores temporary H-SAF H28 `.nc` files downloaded from the H-SAF FTP.
  - `COPERNICUS_SWI` stores temporary Copernicus SWI raw/extracted files and generated daily Latvia SWI TIFFs.
  - These folders are not deployed to GitHub Pages.

## Data Contract

The frontend never expects per-day grid geometry. For a municipality detail view it loads:

1. `frontend/data/municipality_boundaries/<municipality_code>.geojson`
2. `frontend/data/grid_static/<municipality_code>.geojson`
3. `frontend/data/grid_values/<date>/<municipality_code>.json`

`main.js` merges static geometry with date values in memory. This keeps the grid geometry single-source and avoids repeated downloads.

## Operational Daily Chain

The canonical operational command is:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI
python GRID_SAGATAVE\run_daily_v013.py --visible-days 60 --commit-and-push
```

Internally this delegates to `GRID_SAGATAVE/run_kiri_daily_clean.py`:

1. Download latest H-SAF H28 Latvia tiles from FTP for the missing suffix of the source window.
2. Download latest Copernicus SWI products and build daily Latvia SWI TIFFs.
3. Query CLIDATA precipitation windows for only the missing/new suffix, not the whole 60-day window.
4. Interpolate P30/P90/P730 to the 1 km grid.
5. Sample H-SAF and SWI onto the grid and write daily indicator CSVs.
6. Run KIRI risk normalization and frontend JSON generation.
7. Validate the compact frontend data contract.
8. Remove old temporary H-SAF `.nc`/PNG and Copernicus raw/extracted files after JSON generation succeeds.
9. Commit and push the frontend data payload when requested; the Pages deploy workflow runs on that push.

The operational chain is:

```text
H-SAF + SWI + CLIDATA -> KIRI calculation -> QC -> manifest -> commit -> Pages deploy
```

The scheduled GitHub workflow is `.github/workflows/daily-data.yml`. It runs on a self-hosted Windows runner every morning and can also be started manually with `workflow_dispatch`.

The static deploy workflow is `.github/workflows/pages.yml`. It deploys `GRID_SAGATAVE/frontend` after a push to `main`.

## Rolling Window And History

- `calendar_manifest.json` always exposes exactly the newest 60 processed dates.
- Daily operation is suffix-based: normally one old date leaves the visible calendar and one new complete date enters it.
- Older generated JSON payloads are preserved locally and in the Pages payload:
  - `frontend/data/dates/<date>/...`
  - `frontend/data/grid_values/<date>/...`
- `archive_manifest.json` indexes both visible and older processed dates, so climatology/history can be built from the retained JSON.
- Raw source files are not the archive. H-SAF `.nc`, H-SAF quicklooks, Copernicus raw COGs, and extracted SWI folders are temporary working inputs and are cleaned after successful JSON generation.
- `frontend/data/grid_static` is reused. It is rebuilt only if missing, from `GRID_SAGATAVE/outputs/grid_1km_municipalities_centroid.csv`.

## GitHub Secrets And Variables

The scheduled data workflow expects these repository secrets:

- `HSAF_USER`
- `HSAF_PASS`
- `CLIDATA_USER`
- `CLIDATA_PASSWORD`
- `CLIDATA_DSN`
- Copernicus Data Space credentials, either `CDSE_CLIENT_ID`/`CDSE_CLIENT_SECRET` or `CDSE_USERNAME`/`CDSE_PASSWORD`, depending on the local SWI script configuration.

Optional repository variables:

- `CLIDATA_ELEMENT`
- `CLIDATA_ORACLE_INSTANTCLIENT`
- `KIRI_HSAF_PROJECT`
- `KIRI_SWI_PROJECT`

## Removed Legacy Layout

- `GRID_SAGATAVE/frontend/data/municipality_grids` is obsolete.
- Older per-municipality grid geometry copies should not be restored.
- Raw/intermediate folders remain local and ignored unless a future release explicitly changes that rule.
