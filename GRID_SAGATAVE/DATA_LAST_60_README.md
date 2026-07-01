# KIRI-LV DATA_LAST_60 v0.1

This folder pipeline prepares daily raw indicator grids for the last 60 H-SAF days.

Run from:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE
python prepare_last_60_precip_obs.py
Rscript run_last_60_precip_interpolation.R
python build_last_60_indicator_grids.py
```

Outputs:

- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI\DATA_LAST_60\precip_obs` - CLIDATA station P30/P90/P730 windows.
- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI\DATA_LAST_60\precip_grids` - daily precipitation grids.
- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI\DATA_LAST_60\satellite_grids` - daily H-SAF and SWI grid extracts.
- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI\DATA_LAST_60\indicator_grids` - final raw daily indicator grids with `P30_mm`, `P90_mm`, `P730_mm`, `HSAF_SSM_pct`, and `SWI010_pct`.
- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI\DATA_LAST_60\metadata` - QC and metadata.

Current v0.1 run:

- Date range: `2026-05-02` to `2026-06-30`
- Daily indicator files: 60
- Grid rows per file: 65,621
- SWI availability: 58 days
- SWI missing days due to Copernicus delay: `2026-06-29`, `2026-06-30`

Notes:

- This is still raw indicator preparation, not final KIRI risk normalization.
- H-SAF uses daily mean of valid H28 `surface_soil_moisture` samples at grid centroids.
- SWI uses the prepared daily `lv_1x1_swi010_YYYYMMDD.tif` files.
- P30/P90/P730 are rolling inclusive CLIDATA windows ending on each target date.
