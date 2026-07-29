# Clean Latest Data

This folder is the v0.1.3 clean handoff point. It does not duplicate the full frontend payload; it records where the latest production data lives.

- Latest date: `2026-07-27`
- Date window: `2026-05-29` to `2026-07-27`
- Static grid geometry: `../frontend/data/grid_static`
- Daily values: `../frontend/data/grid_values`
- Daily overview and manifest files: `../frontend/data/dates`
- Browser date index: `../frontend/data/calendar_manifest.json`

The old `../frontend/data/municipality_grids` layout has been removed. New daily automation should add the newest daily JSON layer, prune dates outside the 60-day window, and reuse `grid_static`.
