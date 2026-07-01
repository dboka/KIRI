# KIRI-LV

KIRI-LV is a prototype for a manure spreading risk map for Latvia.

Current v0.1 frontend:

- 60 daily risk snapshots from `2026-05-02` to `2026-06-30`
- Latvia municipality overview map
- click a municipality to load only that municipality grid
- click a 1 km grid cell to show P30, P90, P730, H-SAF SSM, and Copernicus SWI values
- compact GitHub Pages data layout: grid geometry is stored once, daily risk values are stored separately

## Local Run

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE\frontend
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

## GitHub Pages

The repository includes a GitHub Actions workflow:

```text
.github/workflows/pages.yml
```

On push to `main`, it deploys:

```text
GRID_SAGATAVE/frontend
```

as the GitHub Pages site.

## Data Notes

The tracked frontend data is optimized for static hosting:

- `GRID_SAGATAVE/frontend/data/grid_static` stores municipality grid geometry once.
- `GRID_SAGATAVE/frontend/data/grid_values` stores daily values by date and municipality.
- `GRID_SAGATAVE/frontend/data/dates` stores daily overview and manifest files.

Large raw/intermediate outputs are ignored by git and stay local.
