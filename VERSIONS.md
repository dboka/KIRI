# KIRI-LV Versions

This repository keeps clean Git restore points so the project can return to a known version.

## Restore Points

- `v0.1.2` - clean GitHub baseline before the automatic daily update work.
- `v0.1.3` - operational 60-day calendar, archive index, Windows/GitHub daily data workflow, source raw cleanup, commit/push handoff, and GitHub Pages payload.

## Local Commands

```powershell
git switch main
git status --short --branch
```

Return to a version for inspection:

```powershell
git switch --detach v0.1.2
git switch --detach v0.1.3
```

Return to active work:

```powershell
git switch main
```

## Data Policy

Tracked frontend data contains the GitHub Pages payload. Local raw and intermediate data remains in `DATA_LAST_60` and is ignored by git.
