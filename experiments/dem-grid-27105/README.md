# 1 m DEM pilots — KIRI režģa šūna 27105

Šis eksperiments KIRI lokālajam rīkam pievieno detalizētu reljefa skatu vienai
1 × 1 km režģa šūnai Ogres novadā.

## Kas ir iekļauts zarā

- OSM pamatkarte detalizētam pietuvinājumam;
- precīzi pēc režģa šūnas izgriezts 1 m DTM;
- trīs attēlojumi: reljefs, augstums un ēnojums;
- caurspīdīguma vadība;
- maska, kas paslēpj DEM ārpus izvēlētās šūnas;
- šūnas KIRI riska informācija arī detalizētajā skatā;
- atgriešanās uz Ogres novada un Latvijas interaktīvo skatu.

Pilota tiešā lokālā adrese:

```text
http://127.0.0.1:8765/?grid=27105
```

## Dati

- Avots: LĢIA atvērtie LiDAR LAS dati.
- Horizontālā koordinātu sistēma: LKS-92 TM (`EPSG:3059`).
- Vertikālā atskaites sistēma: LAS-2000,5.
- Aprēķina solis: 1 m.
- Apstrādes buferis: 300 m ap 1 × 1 km šūnu.
- Izmantotas deviņas LAS lapas; avotu URL un statistika atrodas
  `GRID_SAGATAVE/frontend/data/dem/27105/metadata.json`.

Git zarā atrodas tikai tīmekļa lietotnei vajadzīgie PNG un metadati. Aptuveni
1,22 GB neapstrādāto LAS failu un starprezultātu paliek lokālajā
`C:\Users\deniss.boka\MESLI_PROJECT\test_DEM` mapē un netiek publicēti GitHub.

## Statuss un ierobežojumi

Tas ir tehnisks pilots, nevis vēl pilns virszemes noteces modelis. DEM apraksta
reljefu, bet kūtsmēslu izkliedes riskam papildus būs vajadzīgi nokrišņi, augsnes
mitrums, infiltrācija, sniegs/sasalums, lauka robežas un hidroloģiskā
savienojamība.
