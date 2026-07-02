# KIRI-LV sapulces apraksts

Šis dokuments ir paredzēts projekta demonstrēšanai sapulcē. Tas apraksta, kas ir KIRI-LV, kā dati tiek sagatavoti, kā tiek aprēķināts risks un kāpēc v0.1.2 arhitektūra ir sakārtota tā, lai nākamais solis varētu būt automātiska dienu pievienošana.

Publiskā demonstrācijas adrese:

```text
https://dboka.github.io/KIRI/
```

## Īsais kopsavilkums

KIRI-LV ir statiska tīmekļa karte kūtsmēslu izkliedes riska novērtēšanai Latvijā. Rīks apvieno nokrišņu uzkrājumus, satelītu augsnes mitruma indikatorus un 1 km režģi, lai katrai pašvaldībai un katrai režģa šūnai parādītu relatīvu riska līmeni no 1 līdz 5.

Pašreizējā versija ir `v0.1.2`. Tā rāda 60 dienu periodu no `2026-05-02` līdz `2026-06-30`, pēc noklusējuma atverot `2026-06-30`. Sistēmā ir 43 pašvaldības, 65 621 1 km režģa šūna vienā dienas snapshotā un 2 580 dienas-pašvaldības vērtību faili.

Svarīgākais arhitektūras lēmums šajā versijā: režģa ģeometrija tiek glabāta tikai vienu reizi. Katru dienu tiek pievienotas tikai vērtības, nevis no jauna ģenerēti un dublēti ģeometrijas faili. Tas padara web lapu ātrāku un sagatavo projektu automātiskai ikdienas atjaunošanai.

## Ko demonstrēt sapulcē

1. Atvērt `https://dboka.github.io/KIRI/`.
2. Parādīt Latvijas pārskata karti ar pašvaldību krāsojumu pēc riska līmeņa.
3. Atvērt datuma izvēlni un parādīt, ka pieejamas 60 dienas.
4. Nomainīt datumu un parādīt, ka karte pārlādē dienas risku.
5. Klikšķināt uz pašvaldības, lai atvērtu detalizēto skatu.
6. Detalizētajā skatā parādīt 1 km režģi, kopējo risku, augsta riska šūnu procentu, aktīvos faktorus, kontekstu un indikatoru kartītes.
7. Klikšķināt uz konkrētas režģa šūnas, lai parādītu P30, P90, P730, H-SAF, SWI un uzticamības informāciju.

Sapulcē projektu var pozicionēt kā operatīvu riska indikatoru, nevis kā gala juridisku lēmumu. v0.1.2 vēl neiekļauj normatīvo “hard stop” slāni; tas ir atstāts kā nākamais modeļa slānis.

## Datu avoti

Projektā tiek apvienoti vairāki datu slāņi:

- VZD pašvaldību robežas: izmanto pašvaldību pārskatam un katras pašvaldības robežas parādīšanai kartē.
- 1 km Latvijas režģis: pamata telpiskais aprēķinu režģis. Tas ir fiksēts un tiek piesaistīts pašvaldībām pēc šūnu centroidiem.
- CLIDATA nokrišņu novērojumi: staciju nokrišņu dati, no kuriem tiek veidoti P30, P90 un P730 nokrišņu logi.
- H-SAF SSM: satelītu virsmas augsnes mitruma indikators.
- Copernicus SWI: augsnes ūdens indekss dziļākam/profila mitruma kontekstam.

CLIDATA savienojuma dati netiek glabāti kodā. Tie ir jāpadod tikai caur environment mainīgajiem:

```powershell
$env:CLIDATA_ORACLE_USER = "..."
$env:CLIDATA_ORACLE_PASSWORD = "..."
$env:CLIDATA_ORACLE_DSN = "..."
$env:CLIDATA_ELEMENT = "..."
```

Tas ir būtiski drošībai: parole, DSN, elementa kods un lokālie piekļuves dati nedrīkst būt Git vēsturē vai publiskā web lapā.

## Datu sagatavošanas plūsma

Pašreizējā lokālā datu plūsma ir šāda:

1. `prepare_grid_municipalities.py` piesaista 1 km režģa šūnas pašvaldībām.
2. `prepare_last_60_precip_obs.py` nolasa CLIDATA nokrišņu datus un sagatavo pēdējo 60 dienu P30/P90/P730 logus.
3. `run_last_60_precip_interpolation.R` interpolē nokrišņu logus uz 1 km režģi.
4. `build_last_60_indicator_grids.py` pievieno H-SAF un SWI satelītu indikatorus.
5. `prepare_frontend_last_60_kiri_data.py` aprēķina riskus un sagatavo frontend datu struktūru.
6. `prepare_frontend_compact_pages_data.py` sakārto kompakto GitHub Pages formātu.
7. GitHub Actions deployē `GRID_SAGATAVE/frontend` uz GitHub Pages.

Svarīgais princips: raw un intermediate dati paliek lokāli, bet web lapā nonāk tikai publicēšanai vajadzīgais kompaktais datu slānis.

## Kā strādā riska modelis

Riska modelis ir `moisture_first_v0.1.2`. Tas ir mitruma prioritātes modelis: primāri skatās, vai zeme ir mitra tagad, un nokrišņu dati tiek izmantoti kā īstermiņa, vidēja termiņa un ilgtermiņa konteksts.

Indikatori:

- `H-SAF SSM`: virsmas augsnes mitrums procentos.
- `SWI010`: Copernicus augsnes ūdens indekss procentos.
- `P30`: nokrišņu summa pēdējās 30 dienās.
- `P90`: nokrišņu summa pēdējās 90 dienās.
- `P730`: nokrišņu fons pēdējās 730 dienās.

Katrs indikators tiek pārvērsts 1-5 riska skalā pēc sliekšņiem.

Sliekšņi:

- P30: 20, 40, 70, 100 mm.
- P90: 80, 140, 220, 320 mm.
- P730: 900, 1100, 1300, 1500 mm.
- H-SAF SSM: 25, 40, 55, 70%.
- SWI: 30, 45, 60, 75%.

Apvienošanas loģika:

- Ja pieejams SWI, aktīvais risks tiek svērts: 40% H-SAF, 25% SWI, 25% P30, 10% P90.
- Ja SWI nav pieejams, modelis strādā bez SWI: 50% H-SAF, 35% P30, 15% P90.
- H-SAF ir obligāts redzamam grid riskam. Šūnas bez H-SAF netiek rādītas kā drošs riska novērtējums.
- P730 netiek izmantots kā tiešs aizlieguma indikators. Tas ir ilgtermiņa fona modifikators: ja ilgtermiņa nokrišņu fons ir augsts un aktīvais risks jau ir vismaz vidējs, gala risks var tikt pacelts par vienu līmeni, bet ne pāri 4 tikai P730 dēļ.
- Modelis izvada arī `confidence`: high, medium vai low, atkarībā no pieejamo indikatoru komplekta un H-SAF datu svaiguma.

Riska skala:

- 1: ļoti zems risks.
- 2: zems risks.
- 3: vidējs risks / piesardzība.
- 4: augsts risks.
- 5: ļoti augsts risks / neizkliedēt.

## Ko rāda pašreizējais snapshot

Pašreizējais noklusējuma datums ir `2026-06-30`.

Šajā datumā:

- Kopējais režģa šūnu skaits: 65 621.
- Redzamās šūnas ar H-SAF datiem: 60 839.
- Šūnas bez H-SAF datiem: 4 782.
- Riska līmenis 1: 0 šūnas.
- Riska līmenis 2: 8 460 šūnas.
- Riska līmenis 3: 38 356 šūnas.
- Riska līmenis 4: 14 023 šūnas.
- Riska līmenis 5: 0 šūnas.

Svarīga piezīme sapulcei: `2026-06-30` snapshotā SWI nav pieejams visām šūnām, tāpēc uzticamība ir `medium`. Modelis joprojām strādā, bet izmanto H-SAF, P30 un P90 bez SWI komponentes.

## Web lapas arhitektūra

Frontend ir statiska Leaflet karte. Nav backend servera. Viss tiek servēts no GitHub Pages.

Datu līgums:

```text
frontend/data/calendar_manifest.json
frontend/data/dates/<date>/overview.geojson
frontend/data/dates/<date>/manifest.json
frontend/data/grid_static/<municipality_code>.geojson
frontend/data/grid_values/<date>/<municipality_code>.json
frontend/data/municipality_boundaries/<municipality_code>.geojson
```

Kā tas strādā pārlūkā:

1. Sākumā tiek ielādēts kalendāra manifests.
2. Izvēlētajam datumam tiek ielādēts pašvaldību pārskats.
3. Kad lietotājs klikšķina uz pašvaldības, tiek ielādēta šīs pašvaldības robeža, statiskā grid ģeometrija un konkrētās dienas vērtību fails.
4. Pārlūks apvieno ģeometriju ar dienas vērtībām atmiņā.

Tādēļ nav jālejupielādē 60 reizes viena un tā pati ģeometrija. Tas ir galvenais v0.1.2 ātrdarbības un arhitektūras ieguvums.

## Kāpēc v0.1.2 sakārtošana bija svarīga

Pirms sakārtošanas projektā bija vecāki grid izkārtojumi un dublēta ģeometrija. Tas nav piemērots automātiskai dienu pievienošanai, jo katra jauna diena nevajadzīgi palielinātu datu apjomu.

Tagad:

- ir viena `grid_static` ģeometrija;
- katrai dienai ir tikai vērtību faili;
- `clean` mape norāda uz aktuālo handoff manifestu;
- vecais `municipality_grids` izkārtojums ir izņemts;
- GitHub Pages deploy process validē datu līgumu pirms publicēšanas.

## Drošības piezīmes

Repozitorijā nedrīkst būt paroles, DSN vai privāti hosti, API tokeni, Oracle wallet faili, `.env` faili vai provideru lokālie piekļuves dati.

CLIDATA konfigurācija tagad ir tikai environment mainīgajos. Pēc jebkuras nejaušas noplūdes parole un piekļuves dati jārotē arī datu avota pusē.

## Ko teikt par ierobežojumiem

Šis ir v0.1.2 prototips un tehniski sakārtots pamats turpmākai attīstībai.

Pašreizējie ierobežojumi:

- juridiskie aizliegumi vēl nav pieslēgti kā “hard stop” slānis;
- dati ir sagatavoti lokālā pipeline, nevis vēl pilnībā automātiskā ikdienas procesā;
- SWI var kavēties atsevišķās dienās;
- risks ir operatīvs indikators, nevis viens pats administratīvs lēmums;
- sliekšņi vēl ir modeļa konfigurācija, ko var kalibrēt kopā ar ekspertiem.

## Nākamais attīstības solis

Nākamais solis ir automātiska jaunas dienas pievienošana:

1. Pārbaudīt jaunākos CLIDATA, H-SAF un SWI datus.
2. Sagatavot jauno dienas indikatoru grid.
3. Aprēķināt risku.
4. Pievienot `grid_values/<date>` un `dates/<date>`.
5. Atjaunot `calendar_manifest.json`.
6. Validēt, commit, push un deploy.

Ar esošo arhitektūru šim procesam nav jāģenerē visa ģeometrija no jauna. Tas ir tieši tas, kas vajadzīgs ātrdarbībai un stabilai ikdienas automatizācijai.
