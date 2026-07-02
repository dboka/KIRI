# KIRI-LV

KIRI-LV is a static GitHub Pages prototype for manure spreading risk mapping in Latvia.

## Current Release

- Release: `v0.1.2`
- Default frontend date: `2026-06-30`
- Daily snapshots: `2026-05-02` to `2026-06-30`
- Municipality count: 43
- Frontend deploy path: `GRID_SAGATAVE/frontend`
- Data layout: one static 1 km grid geometry set plus daily value files

## Root Folder Map

- `.github/workflows/pages.yml` - GitHub Pages deployment workflow.
- `GRID_SAGATAVE` - main product, frontend, data preparation scripts, static data, and architecture notes.
- `GRID_SAGATAVE/frontend` - deployed static web tool.
- `GRID_SAGATAVE/frontend/data/grid_static` - canonical grid geometry stored once.
- `GRID_SAGATAVE/frontend/data/grid_values` - daily grid values by date and municipality.
- `GRID_SAGATAVE/frontend/data/dates` - daily overview and manifest files.
- `GRID_SAGATAVE/clean` - latest clean data handoff manifest.
- `docs` - planning and project documentation.
- `docs/meeting-brief-lv.md` - Latvian meeting brief for explaining the data flow, risk logic, architecture, and demo.
- `docs/demo-script-lv.md` - short Latvian script for presenting the website in a meeting.
- `DATA_LAST_60` - local raw/intermediate latest data source; ignored by git.

## GitHub Pages

On every push to `main`, GitHub Actions deploys:

```text
GRID_SAGATAVE/frontend
```

The expected public URL is:

```text
https://dboka.github.io/KIRI/
```

Manual local run:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE\frontend
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

## Development Order

1. Frontend improvements: edit `GRID_SAGATAVE/frontend`.
2. Risk logic changes: edit `GRID_SAGATAVE/src/normalization` and `GRID_SAGATAVE/config`.
3. Data generation changes: edit `GRID_SAGATAVE/prepare_frontend_last_60_kiri_data.py`.
4. Daily automation: build around the existing `grid_static` plus `grid_values/<date>` contract.

Do not restore old per-day grid geometry. The frontend must keep loading one static geometry file and one daily values file per municipality.
