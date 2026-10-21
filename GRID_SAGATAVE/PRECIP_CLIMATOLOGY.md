# P30, P90 un P730 nokrišņu norma

KIRI vēstures grafikos P30, P90 un P730 tiek salīdzināti ar 1991.–2020. gada nokrišņu normu. Avots ir `Dienakts_nokrisnu_daudzums.xlsx` diennakts staciju dati. Ievades Excel fails netiek publicēts; GitHub Pages tiek pievienotas tikai iepriekš aprēķinātas references līknes un 1 km režģa telpiskie svari.

Aprēķins katrai stacijai un vēsturiskajam datumam vispirms summē **pilnas, ieskaitot beigu dienu, slīdošās 30, 90 vai 730 dienas**. Ja kāda diena logā nav pieejama, šo summu neizmanto. 1991. gada sākuma P730 logiem tiek izmantoti 1989.–1990. gada avota dati, bet normas sadalījumā ietilpst tikai 1991.–2020. gada mērķa datumi.

Katrai kalendāra dienai izmantots 15 dienu sezonas logs (±7 dienas), tāpat kā SWI grafikā. No tā iegūst P10, P25, P50, P75, P90 un vidējo. Dienas tiek piesaistītas 366 dienu kalendāram, saglabājot 29. februāri. Vērtībai vajag vismaz 60 pilnus vēsturiskos logus; pašreizējā avotā visām 33 stacijām un 366 kalendāra dienām slieksnis ir izpildīts arī P730.

1 km režģa šūnai staciju references līknes pielāgo ar astoņu tuvāko staciju apgrieztā attāluma kvadrāta svariem EPSG:3059 koordinātās. Tas ir telpisks novērtējums no staciju klimatoloģijas, nevis vēsturiskās dienas KIRI interpolācijas atkārtojums. Percentīle grafikā ir aptuvens novērtējums no šīm references kvantilēm. Novērojumu līnija joprojām izmanto esošos KIRI P30/P90/P730 režģa datus. Grafika CSV eksportā ir gan novērojumi, gan normu joslas. Svari aptver visas 64 579 publicētās pašvaldību režģa šūnas; avota režģa 1 042 šūnas bez pašvaldības piesaistes KIRI kartē netiek rādītas.

Vienreizēja datu ģenerēšana:

```powershell
python GRID_SAGATAVE/build_precip_climatology.py `
  --source "<ceļš uz Dienakts_nokrisnu_daudzums.xlsx>" `
  --stations "<ceļš uz stations_precip_ONLY_PLUS_LT_ELEV_from_grid_2025-06-19.gpkg>" `
  --grid "<ceļš uz grid_1km_municipalities_centroid.csv>"
```

Rezultāts atrodas `GRID_SAGATAVE/frontend/data/precip_climatology`. Dienas atjaunināšanas uzdevums šo nemainīgo 1991.–2020. gada normu nepārrēķina. Pēc ģenerēšanas pārbaudiet `index.json` kvalitātes kopsavilkumu un palaidiet `python GRID_SAGATAVE/validate_frontend_payload.py`.
