# KIRI-LV Grid Sagatave

This folder contains the KIRI-LV v0.1.3 spatial and frontend data preparation flow.

## Folder Map

- `frontend` - GitHub Pages app and production frontend data.
- `frontend/data/grid_static` - the only canonical 1 km grid geometry set.
- `frontend/data/grid_values` - daily values by date and municipality, without geometry.
- `frontend/data/dates` - daily municipality overview layers and manifests.
- `frontend/data/municipality_boundaries` - municipality boundary geometry.
- `config` - KIRI normalization configuration.
- `src/normalization` - risk normalization code.
- `clean` - latest v0.1.3 handoff manifest; it points to the production data instead of duplicating it.
- `ARCHITECTURE.md` - current architecture and daily update contract.

## Local Frontend

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE\frontend
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

## Current Frontend Data Contract

- The frontend calendar shows the latest 60 processed dates.
- Older processed JSON payloads are preserved locally in `frontend/data/dates` and `frontend/data/grid_values`.
- `archive_manifest.json` indexes both visible and older processed dates.
- Grid geometry is stored once in `frontend/data/grid_static` and reused by every date.

## Data Preparation

Grid assignment to municipalities:

```powershell
python prepare_grid_municipalities.py
```

Last 60 days CLIDATA precipitation windows:

```powershell
python prepare_last_60_precip_obs.py
```

P30/P90/P730 interpolation to 1 km grid:

```powershell
Rscript run_last_60_precip_interpolation.R
```

H-SAF and SWI extraction:

```powershell
python build_last_60_indicator_grids.py
```

Municipality UTF-8 name repair for raw CSV outputs:

```powershell
python repair_last_60_municipality_names.py
```

Frontend compact data:

```powershell
python prepare_frontend_last_60_kiri_data.py
python prepare_frontend_compact_pages_data.py
```

## One-Command Daily Refresh

```powershell
.\run_kiri_daily_clean.ps1 --keep-server-running
```

The clean runner:

- downloads recent Latvia H-SAF H28 `.nc` files from the local `FTP_TRYING` source project;
- downloads and prepares recent Copernicus SWI daily Latvia grid TIFFs from `COPERNICUS_SWI`;
- detects which dates are missing from the latest 60-day frontend window;
- rebuilds only the needed suffix of CLIDATA precipitation windows, interpolation, and H-SAF/SWI grid indicators;
- writes the latest 60-day frontend calendar while preserving older JSON history;
- removes large H-SAF/SWI raw source files after JSON generation succeeds;
- optionally starts the local frontend server.

## Notes

- `frontend/data/municipality_grids` was the old duplicated geometry layout and has been removed.
- Raw and intermediate outputs (`DATA_LAST_60`, `outputs`, `precip_outputs`, `indicator_outputs`) stay local and are ignored by git.
- The clean daily path should keep complete existing date payloads, add missing daily JSON layers, preserve JSON history outside the visible 60-day calendar, and reuse `frontend/data/grid_static`.
