# GitHub Pages Deployment

KIRI-LV deploys as a static site from:

```text
GRID_SAGATAVE/frontend
```

The workflow is:

```text
.github/workflows/pages.yml
```

Expected live URL:

```text
https://dboka.github.io/KIRI/
```

## Deployment Contract

- Pushes to `main` trigger the Pages workflow.
- The frontend must work as static files; no backend is required.
- `.nojekyll` is included in `GRID_SAGATAVE/frontend` so GitHub Pages serves all data files directly.
- Large local input/intermediate data folders are not deployed.

## Quick Checks

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI
git status --short --branch
node --check GRID_SAGATAVE\frontend\src\main.js
python GRID_SAGATAVE\prepare_frontend_compact_pages_data.py
```

Then push:

```powershell
git push origin main
git push origin v0.1.2
```
