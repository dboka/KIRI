# SWI010 klimatoloģija (2015–2024)

## Mērķis

Katram KIRI-LV 1 km grid cell tiek izveidota fiksēta 2015–2024 Copernicus CLMS SWI010 klimatoloģija. Tā ļauj grafikā salīdzināt aktuālo SWI ne tikai ar riska sliekšņiem, bet arī ar konkrētās vietas sezonāli normālo diapazonu.

Avots ir [CLMS Daily Soil Water Index Europe 1 km v1](https://land.copernicus.eu/en/products/soil-moisture/daily-soil-water-index-europe-1km-v1). Atsauces periods apzināti paliek 2015-01-01–2024-12-31, lai klimatoloģija nemainītos līdz ar operatīvo dienu pievienošanu.

## Aprēķins

- SWI slānis: `SWI010` (T=10 dienas).
- Avota produktu skaits: 3653 dienas.
- Kalendāra ass: 366 dienas, ieskaitot 29. februāri.
- Katrai kalendāra dienai izmanto ±7 dienu cirkulāru logu (kopā 15 dienas).
- Katram grid cell un dienai glabā P10, P25, P50, P75, P90, aritmētisko vidējo un derīgo paraugu skaitu.
- Profils netiek publicēts, ja logā ir mazāk par 60 derīgiem paraugiem.
- SWI vērtības tiek glabātas kā `uint8` ar mērogu `0.5`; `255` nozīmē “nav datu”.

15 dienu logs dod pietiekami daudz novērojumu percentilēm, bet saglabā sezonālo struktūru. P10–P90 ir ārējais tipiskais diapazons, P25–P75 ir centrālais diapazons, P50 ir mediāna, bet atsevišķā centrālā līnija rāda 2015–2024 aritmētisko vidējo. Aktuālajam punktam interfeiss aprēķina arī aptuveno percentīli un novirzi no vidējā procentpunktos.

## Atmiņas un tīkla ekonomija

Pilni ikdienas produkti netiek lejupielādēti. Skripts caur CDSE OData `Nodes` adresi atver tikai `SWI010` COG failu un ar HTTP Range pieprasījumiem nolasa tikai Latvijas pikseļu logu. Rezultāts tiek rakstīts diskā kā `numpy.memmap`, tāpēc desmit gadu matrica nav jātur RAM.

Lokālie starprezultāti ārpus repozitorija:

- dienu × grid matrica: apmēram 229 MiB;
- grid × 366 dienas × 7 lauki klimatoloģija: apmēram 161 MiB.

Frontend dati ir sadalīti 43 pašvaldību failos (kopā apmēram 86,6 MiB). Pārlūks ielādē tikai izvēlētās pašvaldības `.bin.gz` failu (lielākais ir apmēram 4,6 MiB saspiestā veidā), nevis visas Latvijas klimatoloģiju.

## Atkārtojama būvēšana

Komandas izpilda no repozitorija saknes. CDSE piekļuves dati tiek lasīti no ārējā `COPERNICUS_SWI/.env`; tie netiek ierakstīti repozitorijā.

```powershell
python GRID_SAGATAVE/build_swi_climatology.py catalog
python GRID_SAGATAVE/build_swi_climatology.py harvest --workers 6
python GRID_SAGATAVE/build_swi_climatology.py build --workers 4 --block-cells 512
python GRID_SAGATAVE/build_swi_climatology.py export
python GRID_SAGATAVE/build_swi_climatology.py validate
```

Visus posmus var palaist arī ar `all`. `harvest` un `build` saglabā atomiskus progresa failus, tāpēc pārtrauktu procesu var turpināt. `--rebuild` nepieciešams tikai tad, ja jāatmet esošais starprezultāts.

## Frontend formāts

`GRID_SAGATAVE/frontend/data/swi_climatology/index.json` satur izcelsmi, shēmu, izmērus un SHA-256 kontrolsummas. Katras pašvaldības binārā faila struktūra pēc gzip atspiešanas ir:

```text
magic[4] = SWIC
version[u8]
field_count[u8]
day_count[u16]
cell_count[u32]
grid_ids[cell_count, u32]
values[cell_count, day_count, field_count, u8]
```

`validate` pārbauda visu failu kontrolsummas, galvenes, izmērus, unikālos grid ID, trūkstošo datu konsekvenci, minimālo paraugu skaitu un nosacījumu `P10 ≤ P25 ≤ P50 ≤ P75 ≤ P90`.
