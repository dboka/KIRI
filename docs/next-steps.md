# Next Steps After v0.1.2

The repository is now organized for incremental tool improvements.

## Recommended Work Slices

1. Daily data automation
   - Keep `frontend/data/grid_static` unchanged.
   - Add or regenerate only `frontend/data/grid_values/<date>`, `frontend/data/dates/<date>`, and `calendar_manifest.json`.

2. Frontend interaction
   - Work inside `GRID_SAGATAVE/frontend/src/main.js` and `styles.css`.
   - Keep data loading lazy: overview first, municipality grid only after click.

3. Risk logic
   - Edit `GRID_SAGATAVE/src/normalization/normalize_kiri_v01.py`.
   - Keep thresholds in `GRID_SAGATAVE/config/normalization_v01.yaml`.

4. Release hygiene
   - Validate data contract before pushing.
   - Commit small logical chunks.
   - Tag stable public states as `v0.x.y`.

## Current Data Contract

For one municipality detail view the browser loads:

```text
municipality_boundaries/<municipality_code>.geojson
grid_static/<municipality_code>.geojson
grid_values/<date>/<municipality_code>.json
```

The old `municipality_grids` layout is obsolete.
