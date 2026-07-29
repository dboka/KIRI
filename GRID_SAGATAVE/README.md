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

## Current Frontend Data

- 60 daily calendar snapshots from `2026-05-28` to `2026-07-26`.
- Archive index for older processed dates from `2026-05-02` to `2026-05-27`.
- Default date: `2026-07-26`.
- 43 municipality static grid geometry files.
- 2,580 daily municipality value files.
- Grid geometry is stored once and reused by every date.

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

## Daily Automation

```powershell
.\run_daily_v013.ps1 --commit-and-push
```

The default daily path processes only the newest available H-SAF date, adds that JSON layer, and prunes the oldest frontend date outside the 60-day window. Use `--rebuild-window` only for a deliberate full 60-day rebuild.

Register the Windows scheduled task:

```powershell
.\register_daily_v013_task.ps1 -Time 08:00
```

## Notes

- `frontend/data/municipality_grids` was the old duplicated geometry layout and has been removed.
- Raw and intermediate outputs (`DATA_LAST_60`, `outputs`, `precip_outputs`, `indicator_outputs`) stay local and are ignored by git.
- New daily automation should keep complete existing date payloads, add the newest daily JSON layer, prune dates outside the 60-day window, and reuse `frontend/data/grid_static`.
