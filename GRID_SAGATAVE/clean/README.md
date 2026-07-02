# Clean Latest Data

This folder is the v0.1.2 clean handoff point. It does not duplicate the full frontend payload; it records where the latest production data lives.

- Latest date: `2026-06-30`
- Date window: `2026-05-02` to `2026-06-30`
- Static grid geometry: `../frontend/data/grid_static`
- Daily values: `../frontend/data/grid_values`
- Daily overview and manifest files: `../frontend/data/dates`
- Browser date index: `../frontend/data/calendar_manifest.json`

The old `../frontend/data/municipality_grids` layout has been removed. New daily automation should append/regenerate values and manifests while reusing `grid_static`.
