# KIRI-LV Grid Sagatave

Sis solis sagatavo telpisko pamatu KIRI-LV risku kartem:

1. nolasa Latvijas 1x1 km grid centroidus no `1x1_LV_grid_2024_xy2.csv`;
2. nolasa pasvaldibu robezas no `Novadi.shp`;
3. pieliek valstspilsetas no `Pilsetas.shp`, izmantojot tikai `CITY_TYPE=2`;
4. katru grid sunu piesaista tai pasvaldibai, kura atrodas sunas centrs.

Metode: centroid method. Suna netiek dalita starp pasvaldibam.

## Palaisana

```powershell
python prepare_grid_municipalities.py
```

Ja izmanto Codex komplekteto Python:

```powershell
C:\Users\deniss.boka\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe prepare_grid_municipalities.py
```

## Izvades faili

Skripts raksta rezultatus mapē `outputs/`:

- `grid_1km_municipalities_centroid.csv` - pilnais grids ar pasvaldibas laukiem.
- `municipality_grid_summary.csv` - sunu skaits katrai pasvaldibai.
- `grid_unassigned_centroids.csv` - centroidi, kas neiekrita pasvaldibu robezas.
- `municipality_grid_fragments/` - atsevisks CSV fragments katrai pasvaldibai.
- `grid_assignment_metadata.json` - metodes un izvades metadati.

Galvenie pievienotie lauki:

- `grid_id`
- `centroid_x`
- `centroid_y`
- `cell_size_m`
- `municipality_code`
- `municipality_atvk`
- `municipality_name`
- `municipality_source`
- `cell_polygon_lks92_wkt`

## Piezimes

- Koordinates ir LKS-92 Latvia TM metros, tapat ka avota shapefile.
- Parastas pilsetas netiek izmantotas ka pasvaldibas; no `Pilsetas.shp` tiek nemtas tikai valstspilsetas.
- Sis solis vel nerekinas SSM, SWI, P30 vai `risk_level`; tas tikai sagatavo grid-pasvaldibu pamatu nakamajai datu pipeline dalai.

## Frontend prototips

Papildu skripts sagatavo Leaflet prototipa datus:

```powershell
python prepare_frontend_data.py
```

Tas izveido:

- `frontend/data/municipalities.geojson` - viegls Latvijas pasvaldibu parskata slanis.
- `frontend/data/municipality_manifest.json` - pasvaldibu kopsavilkumi un saites uz detalizetajiem failiem.
- `frontend/data/municipality_boundaries/<municipality_code>.geojson` - detalizeta robeza klikskinatai pasvaldibai.
- `frontend/data/municipality_grids/<municipality_code>.geojson` - tikai konkretas pasvaldibas 1 km grid sunas.

Lokala palaisana:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE\frontend
python -m http.server 8000
```

Pec tam atver:

```text
http://localhost:8000
```

Svarigi: frontend dati satur deterministiskus demo `risk_level` laukus tikai UI testesanai. Tie nav KIRI-LV zinatniskais riska indekss.

## Nokrisnu indikatori P30/P90/P730

Sis posms sagatavo CLIDATA nokrisnu summas un interpolaciju uz KIRI 1 km gridu.

Periodi:

- `P30`: 2026-05-17 lidz 2026-06-15
- `P90`: 2026-03-18 lidz 2026-06-15
- `P730`: 2024-06-16 lidz 2026-06-15

1. Lejupieladet un sasummet CLIDATA staciju datus:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE
python download_clidata_precip_windows.py
```

2. Interpolet P30/P90/P730 uz KIRI gridu ar `uk_elev_contpr.R` metodiku:

```powershell
Rscript run_precip_interpolation.R
```

Galvenais rezultats:

```text
precip_outputs/interpolated/grid_precip_P30_P90_P730_mm.csv
```

Papildu QC faili:

- `precip_outputs/obs/obs_precip_windows_long.csv`
- `precip_outputs/obs/obs_precip_windows_wide.csv`
- `precip_outputs/interpolated/station_precip_windows_used.csv`

Piezime: sis posms rada tikai nokrisnu mm indikatorus. Tas vel neveido percentiles, SPI, riska limenus vai KIRI-LV finalo risku.

## Satelitu indikatori H-SAF un SWI

Pec nokrisnu interpolacijas var pievienot H-SAF H28 SSM un Copernicus SWI vertibas uz ta pasa grid:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE
python extract_satellite_indicators.py
```

Ievade:

- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI\DEMO_STUFFS\HSAF_15062026`
- `C:\Users\deniss.boka\MESLI_PROJECT\KIRI\DEMO_STUFFS\SWI_15062026`
- `precip_outputs/interpolated/grid_precip_P30_P90_P730_mm.csv`

Galvenais rezultats:

```text
indicator_outputs/grid_indicators_P30_P90_P730_HSAF_SWI_2026-06-15.csv
```

Galvenie lauki:

- `P30_mm`
- `P90_mm`
- `P730_mm`
- `HSAF_SSM_pct` - videjais no derigajiem 2026-06-15 H-SAF H28 pargajieniem
- `SWI010_pct` - Copernicus SWI010 ar pielietotu `scale_factor = 0.5`

Papildu QC lauki:

- `HSAF_SSM_max_pct`
- `HSAF_SSM_min_pct`
- `HSAF_SSM_std_pct`
- `HSAF_SSM_valid_overpasses`
- `SWI010_raw`

Piezime: sis vel ir raw indikatoru fails. Normalizecija, percentiles un KIRI-LV riska limeni nak nakamaja soli.

## KIRI-LV v0.1 provizoriska normalizacija

Sis solis parvers raw indikatorus riska klasēs `1..5` ar pagaidu slieksniem no:

```text
config/normalization_v01.yaml
```

Palaisana:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE
python src\normalization\normalize_kiri_v01.py
```

Ievade:

```text
indicator_outputs/grid_indicators_P30_P90_P730_HSAF_SWI_2026-06-15.csv
```

Galvenie rezultati:

- `outputs/kiri_normalized/kiri_grid_2026_06_15.csv`
- `outputs/kiri_normalized/kiri_grid_2026_06_15.geojson`
- `outputs/kiri_normalized/kiri_grid_2026_06_15.gpkg`
- `outputs/kiri_normalized/municipality_summary_2026_06_15.csv`
- `outputs/kiri_normalized/normalization_metadata_2026_06_15.json`

Izveidotie lauki:

- `p30_risk`
- `p90_risk`
- `p730_risk`
- `hsaf_ssm_risk`
- `swi_risk`
- `kiri_risk_level`
- `kiri_risk_label_lv`
- `main_reasons`
- `normalization_method`
- `confidence`
- `legal_status`
- `hard_stop_active`
- `block_reason`

Svarigi: si ir v0.1 pagaidu normalizacija ar konfigurējamiem slieksniem. Ta vel nav sezonala percentile/SPI klimatologija. Velak `normalization_method` var nomainit uz `seasonal_percentile`, nemainot frontend shēmu.

## Frontend dati no KIRI normalizeta slana

Pec normalizacijas pargeneret web kartes datus no ista `kiri_risk_level` slana:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE
python prepare_frontend_kiri_data.py
```

Tas atjauno:

- `frontend/data/municipalities.geojson`
- `frontend/data/municipality_manifest.json`
- `frontend/data/municipality_grids/<municipality_code>.geojson`

Veiktspējas princips:

- Latvijas sakuma skata lādē tikai pasvaldibu robezas.
- Klikskis uz pasvaldibu lade tikai tas pasvaldibas grid failu.
- Grid sunam nav hover popupu; statistika paradas tikai pec klikskja uz konkreto sunu.
- Frontend GeoJSON jau ir sagatavots `EPSG:4326`, lai Leaflet neveic projekciju parrekinus browseri.
