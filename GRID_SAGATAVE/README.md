# KIRI-LV Grid Sagatave

Šī mape satur KIRI-LV v0.1 telpisko un frontend datu sagatavošanas plūsmu.

## Galvenais frontend prototips

Lokāli:

```powershell
cd C:\Users\deniss.boka\MESLI_PROJECT\KIRI\GRID_SAGATAVE\frontend
python -m http.server 8000
```

Atver:

```text
http://localhost:8000
```

Frontend rāda:

- 60 dienu kalendāru no `2026-05-02` līdz `2026-06-30`;
- pašvaldību sākuma karti katrai dienai;
- klikšķi uz pašvaldību ar 1 km grid detalizēto skatu;
- klikšķi uz grid šūnas ar `P30`, `P90`, `P730`, `H-SAF SSM`, `Copernicus SWI` un v0.1 riska klasēm.

## GitHub Pages datu izkārtojums

Frontend dati ir optimizēti statiskai publicēšanai:

- `frontend/data/dates/<date>/overview.geojson` - dienas pašvaldību overview slānis;
- `frontend/data/dates/<date>/manifest.json` - dienas pašvaldību metadati;
- `frontend/data/grid_static/<municipality_code>.geojson` - pašvaldības grid ģeometrija, glabāta vienu reizi;
- `frontend/data/grid_values/<date>/<municipality_code>.json` - konkrētās dienas grid vērtības bez atkārtotas ģeometrijas.

Šī pieeja samazina Pages datu pakotni no vairākiem GB līdz aptuveni 421 MB.

## Datu sagatavošanas komandas

Grid piesaiste pašvaldībām:

```powershell
python prepare_grid_municipalities.py
```

Pēdējo 60 dienu CLIDATA nokrišņu logi:

```powershell
python prepare_last_60_precip_obs.py
```

P30/P90/P730 interpolācija uz 1 km grid:

```powershell
Rscript run_last_60_precip_interpolation.R
```

H-SAF un SWI pievienošana:

```powershell
python build_last_60_indicator_grids.py
```

Pašvaldību nosaukumu UTF-8 labošana raw CSV izvados:

```powershell
python repair_last_60_municipality_names.py
```

Frontend 60 dienu riska slāņu sagatavošana:

```powershell
python prepare_frontend_last_60_kiri_data.py
python prepare_frontend_compact_pages_data.py
```

## Piezīmes

- v0.1 normalizācija vēl izmanto pagaidu sliekšņus.
- Juridiskie hard-stop noteikumi vēl nav vērtēti.
- Raw un intermediate izvades (`DATA_LAST_60`, `outputs`, `precip_outputs`, `indicator_outputs`) netiek liktas git repozitorijā.
