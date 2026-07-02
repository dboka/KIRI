# KIRI-LV v0.1.2 Architecture

This repository now keeps one production frontend data layout. The goal is fast map loading and easy daily updates without regenerating or duplicating grid geometry.

## Current Folder Map

- `GRID_SAGATAVE/frontend`
  - Static GitHub Pages application.
  - `index.html`, `src/main.js`, and `src/styles.css` are the browser app.
  - The browser loads only the active date overview and one municipality grid value file at a time.

- `GRID_SAGATAVE/frontend/data`
  - Production data payload for GitHub Pages.
  - `calendar_manifest.json` is the date index and default date selector.
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

## Data Contract

The frontend never expects per-day grid geometry. For a municipality detail view it loads:

1. `frontend/data/municipality_boundaries/<municipality_code>.geojson`
2. `frontend/data/grid_static/<municipality_code>.geojson`
3. `frontend/data/grid_values/<date>/<municipality_code>.json`

`main.js` merges static geometry with date values in memory. This keeps the grid geometry single-source and avoids repeated downloads.

## Daily Update Flow

1. Add or refresh daily indicator CSV files under `DATA_LAST_60/indicator_grids`.
2. Run `python GRID_SAGATAVE/prepare_frontend_last_60_kiri_data.py`.
3. The script rewrites `frontend/data/dates`, `frontend/data/grid_values`, and `calendar_manifest.json`.
4. `frontend/data/grid_static` is reused. It is rebuilt only if missing, from `GRID_SAGATAVE/outputs/grid_1km_municipalities_centroid.csv`.
5. Commit and push the changed frontend data.

## Removed Legacy Layout

- `GRID_SAGATAVE/frontend/data/municipality_grids` is obsolete.
- Older per-municipality grid geometry copies should not be restored.
- Raw/intermediate folders remain local and ignored unless a future release explicitly changes that rule.
